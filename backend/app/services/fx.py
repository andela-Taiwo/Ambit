"""Exchange-rate storage and resolution.

Stored rates are append-only observations. Nothing here ever invents a rate:
when no observation covers a pair at the requested instant, `MissingRateError`
is raised and the caller surfaces a 422-level failure rather than silently
substituting a guessed or stale value (plan Section 14).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.db.models import ExchangeRate
from app.domain.fx import (
    MissingRateError,
    RateBook,
    RateObservation,
    ResolvedRate,
    invert_rate,
    validate_rate,
)
from app.domain.money import Currency
from app.schemas.fx import ExchangeRateCreate

MANUAL_SOURCE = "manual"


def _visible(user_id: uuid.UUID) -> Select[tuple[ExchangeRate]]:
    """A user sees shared provider rates plus their own manual overrides."""
    return select(ExchangeRate).where(
        or_(ExchangeRate.user_id.is_(None), ExchangeRate.user_id == user_id)
    )


async def record_manual_rate(
    session: AsyncSession, user_id: uuid.UUID, payload: ExchangeRateCreate
) -> ExchangeRate:
    """Persist a user-scoped rate.

    Manual rates are deliberately private: one user must not be able to change
    the numbers another user's net worth is reported with.
    """
    validate_rate(payload.rate)

    duplicate = await session.scalar(
        _visible(user_id).where(
            ExchangeRate.user_id == user_id,
            ExchangeRate.base_currency == payload.base_currency,
            ExchangeRate.quote_currency == payload.quote_currency,
            ExchangeRate.as_of == payload.as_of,
            ExchangeRate.source == MANUAL_SOURCE,
        )
    )
    if duplicate is not None:
        raise ConflictError("A manual rate for that pair and timestamp already exists")

    rate = ExchangeRate(
        user_id=user_id,
        base_currency=payload.base_currency,
        quote_currency=payload.quote_currency,
        rate=payload.rate,
        as_of=payload.as_of,
        source=MANUAL_SOURCE,
    )
    session.add(rate)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A manual rate for that pair and timestamp already exists") from exc
    await session.refresh(rate)
    return rate


async def list_rates(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    base_currency: str | None = None,
    quote_currency: str | None = None,
    as_of: datetime | None = None,
) -> tuple[list[ExchangeRate], int]:
    query = _visible(user_id)
    if base_currency is not None:
        query = query.where(ExchangeRate.base_currency == Currency(base_currency).code)
    if quote_currency is not None:
        query = query.where(ExchangeRate.quote_currency == Currency(quote_currency).code)
    if as_of is not None:
        query = query.where(ExchangeRate.as_of <= as_of)

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(ExchangeRate.as_of.desc(), ExchangeRate.fetched_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def _latest_observation(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    base_currency: str,
    quote_currency: str,
    as_of: datetime,
) -> RateObservation | None:
    """Newest user-owned observation, falling back to the newest shared one."""
    for owner_filter in (
        ExchangeRate.user_id == user_id,
        ExchangeRate.user_id.is_(None),
    ):
        row = await session.scalar(
            select(ExchangeRate)
            .where(
                owner_filter,
                ExchangeRate.base_currency == base_currency,
                ExchangeRate.quote_currency == quote_currency,
                ExchangeRate.as_of <= as_of,
            )
            .order_by(ExchangeRate.as_of.desc(), ExchangeRate.fetched_at.desc())
            .limit(1)
        )
        if row is not None:
            return RateObservation(
                base_currency=row.base_currency,
                quote_currency=row.quote_currency,
                rate=row.rate,
                as_of=row.as_of,
                source=row.source,
            )
    return None


async def resolve_rate(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    from_currency: str,
    to_currency: str,
    as_of: datetime,
) -> ResolvedRate:
    """Resolve the effective rate, trying the stored pair then its inverse."""
    source = Currency(from_currency)
    target = Currency(to_currency)

    if source.code == target.code:
        return ResolvedRate(
            base_currency=source.code,
            quote_currency=target.code,
            rate=Decimal(1),
            as_of=as_of,
            source="identity",
        )

    observation = await _latest_observation(
        session,
        user_id,
        base_currency=source.code,
        quote_currency=target.code,
        as_of=as_of,
    )
    if observation is not None:
        return ResolvedRate(
            base_currency=source.code,
            quote_currency=target.code,
            rate=observation.rate,
            as_of=observation.as_of,
            source=observation.source,
        )

    inverse = await _latest_observation(
        session,
        user_id,
        base_currency=target.code,
        quote_currency=source.code,
        as_of=as_of,
    )
    if inverse is not None:
        return ResolvedRate(
            base_currency=source.code,
            quote_currency=target.code,
            rate=invert_rate(inverse.rate),
            as_of=inverse.as_of,
            source=inverse.source,
            is_inverse=True,
        )

    raise MissingRateError(
        f"No exchange rate from {source.code} to {target.code} on or before {as_of.isoformat()}"
    )


async def load_rate_book(session: AsyncSession, user_id: uuid.UUID, *, as_of: datetime) -> RateBook:
    """Load every visible observation up to `as_of` for batch conversion.

    Reports and budget status resolve many amounts at different dates; loading
    once and resolving in memory avoids an N+1 query per transaction. The upper
    bound keeps the result set proportional to the report window, not to the
    whole history.
    """
    rows = await session.scalars(
        _visible(user_id)
        .where(ExchangeRate.as_of <= as_of)
        .order_by(ExchangeRate.as_of.asc(), ExchangeRate.fetched_at.asc())
    )

    user_observations: list[RateObservation] = []
    global_observations: list[RateObservation] = []
    for row in rows:
        observation = RateObservation(
            base_currency=row.base_currency,
            quote_currency=row.quote_currency,
            rate=row.rate,
            as_of=row.as_of,
            source=row.source,
        )
        if row.user_id is None:
            global_observations.append(observation)
        else:
            user_observations.append(observation)

    return RateBook(
        user_observations=user_observations,
        global_observations=global_observations,
    )


async def get_resolved_rate_or_404(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    from_currency: str,
    to_currency: str,
    as_of: datetime,
) -> ResolvedRate:
    try:
        return await resolve_rate(
            session,
            user_id,
            from_currency=from_currency,
            to_currency=to_currency,
            as_of=as_of,
        )
    except MissingRateError as exc:
        raise NotFoundError(str(exc)) from exc
