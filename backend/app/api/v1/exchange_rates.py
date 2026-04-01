"""Exchange-rate routes."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import ValidationError
from app.domain.fx import MissingRateError, convert_minor_units
from app.domain.money import Currency, InvalidAmountError, to_minor_units
from app.schemas.common import CONFLICT, NOT_FOUND, UNAUTHORISED, CurrencyCode, Page
from app.schemas.fx import (
    ConversionResponse,
    ExchangeRateCreate,
    ExchangeRateResponse,
    ResolvedRateResponse,
)
from app.services import fx as fx_service

router = APIRouter(prefix="/exchange-rates", tags=["exchange rates"], responses=UNAUTHORISED)


def _as_of(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


@router.post(
    "",
    response_model=ExchangeRateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a manual exchange rate",
    responses=CONFLICT,
)
async def create_exchange_rate(
    session: SessionDep, current_user: CurrentUser, payload: ExchangeRateCreate
) -> ExchangeRateResponse:
    """Manual rates are private to the caller.

    Provider-fetched rates are shared and written only by the scheduled job, so
    a user cannot alter the rates another user's reports are based on.
    """
    rate = await fx_service.record_manual_rate(session, current_user.id, payload)
    return ExchangeRateResponse.model_validate(rate)


@router.get("", response_model=Page[ExchangeRateResponse], summary="List exchange rates")
async def list_exchange_rates(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    base_currency: CurrencyCode | None = None,
    quote_currency: CurrencyCode | None = None,
    as_of: datetime | None = None,
) -> Page[ExchangeRateResponse]:
    rows, total = await fx_service.list_rates(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
        base_currency=base_currency,
        quote_currency=quote_currency,
        as_of=_as_of(as_of) if as_of is not None else None,
    )
    return Page(
        items=[ExchangeRateResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/latest",
    response_model=ResolvedRateResponse,
    summary="Get the effective rate for a pair",
    responses=NOT_FOUND,
)
async def latest_exchange_rate(
    session: SessionDep,
    current_user: CurrentUser,
    base_currency: CurrencyCode,
    quote_currency: CurrencyCode,
    as_of: datetime | None = None,
) -> ResolvedRateResponse:
    resolved = await fx_service.get_resolved_rate_or_404(
        session,
        current_user.id,
        from_currency=base_currency,
        to_currency=quote_currency,
        as_of=_as_of(as_of),
    )
    return ResolvedRateResponse.from_domain(resolved)


@router.get(
    "/convert",
    response_model=ConversionResponse,
    summary="Preview a currency conversion",
    responses=NOT_FOUND,
)
async def convert(
    session: SessionDep,
    current_user: CurrentUser,
    from_currency: CurrencyCode,
    to_currency: CurrencyCode,
    amount: Annotated[Decimal, Query(gt=0, examples=["100.00"])],
    as_of: datetime | None = None,
) -> ConversionResponse:
    """Convert an exact decimal amount at the effective rate."""
    source = Currency(from_currency)
    try:
        amount_minor = to_minor_units(amount, source)
    except InvalidAmountError as exc:
        raise ValidationError(str(exc)) from exc

    instant = _as_of(as_of)
    try:
        resolved = await fx_service.resolve_rate(
            session,
            current_user.id,
            from_currency=source.code,
            to_currency=to_currency,
            as_of=instant,
        )
    except MissingRateError as exc:
        raise ValidationError(str(exc)) from exc

    converted_minor = convert_minor_units(
        amount_minor,
        from_currency=source.code,
        to_currency=resolved.quote_currency,
        rate=resolved.rate,
    )
    return ConversionResponse(
        from_currency=source.code,
        to_currency=resolved.quote_currency,
        amount_minor=amount_minor,
        converted_minor=converted_minor,
        rate=resolved.rate,
        rate_as_of=resolved.as_of,
        rate_source=resolved.source,
        rate_is_inverse=resolved.is_inverse,
    )
