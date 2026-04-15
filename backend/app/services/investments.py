"""Investment CRUD, valuation snapshots and return calculation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import Account, Investment, InvestmentValuation
from app.domain.accounts import AccountType
from app.domain.investments import (
    AccrualResult,
    InvestmentMathError,
    InvestmentType,
    RatePeriod,
    accrued_interest,
    project_interest,
    validate_rate,
)
from app.domain.money import Currency, InvalidAmountError, to_minor_units
from app.schemas.investments import (
    InvestmentCreate,
    InvestmentReturnsResponse,
    InvestmentUpdate,
    ValuationCreate,
    ValueSource,
)
from app.services import audit
from app.services.accounts import get_account

MANUAL_VALUE_SOURCE = "manual"


@dataclass(frozen=True, slots=True)
class InvestmentValue:
    value_minor: int
    source: ValueSource
    valuation_as_of: date | None
    accrued_interest_minor: int


def _owned(user_id: uuid.UUID) -> Select[tuple[Investment]]:
    return select(Investment).where(Investment.user_id == user_id)


def _owned_valuations(user_id: uuid.UUID) -> Select[tuple[InvestmentValuation]]:
    return select(InvestmentValuation).where(InvestmentValuation.user_id == user_id)


async def get_investment(
    session: AsyncSession, user_id: uuid.UUID, investment_id: uuid.UUID
) -> Investment:
    investment = await session.scalar(_owned(user_id).where(Investment.id == investment_id))
    if investment is None:
        raise NotFoundError("Investment not found")
    return investment


async def list_investments(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    account_id: uuid.UUID | None = None,
    investment_type: InvestmentType | None = None,
    include_archived: bool = False,
) -> tuple[list[Investment], int]:
    query = _owned(user_id)
    if account_id is not None:
        query = query.where(Investment.account_id == account_id)
    if investment_type is not None:
        query = query.where(Investment.investment_type == investment_type)
    if not include_archived:
        query = query.where(Investment.is_archived.is_(False))

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(query.order_by(Investment.name).limit(limit).offset(offset))
    return list(rows), int(total or 0)


async def _investment_account(
    session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> Account:
    account = await get_account(session, user_id, account_id)
    if account.account_type is not AccountType.INVESTMENT:
        raise ValidationError("Investments must be held in an investment account")
    if account.is_archived:
        raise ValidationError("Cannot add investments to an archived account")
    return account


async def _assert_name_is_free(
    session: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    query = _owned(user_id).where(Investment.name == name)
    if exclude_id is not None:
        query = query.where(Investment.id != exclude_id)
    if await session.scalar(query) is not None:
        raise ConflictError("An investment with that name already exists")


def _validate_terms(
    *,
    investment_type: InvestmentType,
    rate: Decimal | None,
    rate_period: RatePeriod | None,
    start_date: date,
    maturity_date: date | None,
) -> None:
    if maturity_date is not None and maturity_date < start_date:
        raise ValidationError("maturity_date cannot be before start_date")

    if investment_type is InvestmentType.FIXED_RATE:
        if rate is None or rate_period is None:
            raise ValidationError("A fixed-rate investment requires rate and rate_period")
        try:
            validate_rate(rate)
        except InvestmentMathError as exc:
            raise ValidationError(str(exc)) from exc
    elif rate is not None or rate_period is not None:
        raise ValidationError("A market-priced investment must not set rate or rate_period")


async def create_investment(
    session: AsyncSession, user_id: uuid.UUID, payload: InvestmentCreate
) -> Investment:
    account = await _investment_account(session, user_id, payload.account_id)

    if payload.currency != account.currency:
        raise ValidationError(
            f"Investment currency {payload.currency} does not match "
            f"account currency {account.currency}"
        )

    _validate_terms(
        investment_type=payload.investment_type,
        rate=payload.rate,
        rate_period=payload.rate_period,
        start_date=payload.start_date,
        maturity_date=payload.maturity_date,
    )
    await _assert_name_is_free(session, user_id, payload.name)

    currency = Currency(payload.currency)
    try:
        principal_minor = to_minor_units(payload.principal, currency)
    except InvalidAmountError as exc:
        raise ValidationError(str(exc)) from exc

    investment = Investment(
        user_id=user_id,
        account_id=account.id,
        name=payload.name,
        investment_type=payload.investment_type,
        principal_minor=principal_minor,
        currency=currency.code,
        rate=payload.rate,
        rate_period=payload.rate_period,
        compounding=payload.compounding,
        start_date=payload.start_date,
        maturity_date=payload.maturity_date,
        notes=payload.notes,
    )
    session.add(investment)
    try:
        await session.flush()
        audit.record(
            session,
            user_id=user_id,
            entity_type="investment",
            entity_id=investment.id,
            action="created",
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("An investment with that name already exists") from exc
    await session.refresh(investment)
    return investment


async def update_investment(
    session: AsyncSession,
    user_id: uuid.UUID,
    investment_id: uuid.UUID,
    payload: InvestmentUpdate,
) -> Investment:
    investment = await get_investment(session, user_id, investment_id)

    if payload.name is not None and payload.name != investment.name:
        await _assert_name_is_free(session, user_id, payload.name, exclude_id=investment.id)
        investment.name = payload.name

    if payload.principal is not None:
        currency = Currency(investment.currency)
        try:
            investment.principal_minor = to_minor_units(payload.principal, currency)
        except InvalidAmountError as exc:
            raise ValidationError(str(exc)) from exc

    if "rate" in payload.model_fields_set or "rate_period" in payload.model_fields_set:
        if investment.investment_type is not InvestmentType.FIXED_RATE:
            raise ValidationError("A market-priced investment has no stated rate")
        investment.rate = payload.rate
        investment.rate_period = payload.rate_period

    if payload.compounding is not None:
        investment.compounding = payload.compounding

    if "maturity_date" in payload.model_fields_set:
        investment.maturity_date = payload.maturity_date

    if "notes" in payload.model_fields_set:
        investment.notes = payload.notes

    if payload.is_archived is not None:
        investment.is_archived = payload.is_archived

    _validate_terms(
        investment_type=investment.investment_type,
        rate=investment.rate,
        rate_period=investment.rate_period,
        start_date=investment.start_date,
        maturity_date=investment.maturity_date,
    )

    audit.record(
        session,
        user_id=user_id,
        entity_type="investment",
        entity_id=investment.id,
        action="updated",
    )
    await session.commit()
    await session.refresh(investment)
    return investment


async def delete_investment(
    session: AsyncSession, user_id: uuid.UUID, investment_id: uuid.UUID
) -> None:
    investment = await get_investment(session, user_id, investment_id)
    await session.delete(investment)
    audit.record(
        session,
        user_id=user_id,
        entity_type="investment",
        entity_id=investment.id,
        action="deleted",
    )
    await session.commit()


async def get_valuation(
    session: AsyncSession,
    user_id: uuid.UUID,
    investment_id: uuid.UUID,
    valuation_id: uuid.UUID,
) -> InvestmentValuation:
    valuation = await session.scalar(
        _owned_valuations(user_id).where(
            InvestmentValuation.id == valuation_id,
            InvestmentValuation.investment_id == investment_id,
        )
    )
    if valuation is None:
        raise NotFoundError("Valuation not found")
    return valuation


async def list_valuations(
    session: AsyncSession,
    user_id: uuid.UUID,
    investment_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
) -> tuple[list[InvestmentValuation], int]:
    await get_investment(session, user_id, investment_id)
    query = _owned_valuations(user_id).where(InvestmentValuation.investment_id == investment_id)
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(InvestmentValuation.as_of.desc()).limit(limit).offset(offset)
    )
    return list(rows), int(total or 0)


async def create_valuation(
    session: AsyncSession,
    user_id: uuid.UUID,
    investment_id: uuid.UUID,
    payload: ValuationCreate,
) -> InvestmentValuation:
    investment = await get_investment(session, user_id, investment_id)
    if payload.as_of < investment.start_date:
        raise ValidationError("A valuation cannot predate the investment's start date")

    currency = Currency(investment.currency)
    try:
        value_minor = to_minor_units(payload.value, currency)
    except InvalidAmountError as exc:
        raise ValidationError(str(exc)) from exc

    duplicate = await session.scalar(
        _owned_valuations(user_id).where(
            InvestmentValuation.investment_id == investment.id,
            InvestmentValuation.as_of == payload.as_of,
        )
    )
    if duplicate is not None:
        raise ConflictError("A valuation for that investment and date already exists")

    valuation = InvestmentValuation(
        investment_id=investment.id,
        user_id=user_id,
        as_of=payload.as_of,
        value_minor=value_minor,
        source=MANUAL_VALUE_SOURCE,
        notes=payload.notes,
    )
    session.add(valuation)
    try:
        await session.flush()
        audit.record(
            session,
            user_id=user_id,
            entity_type="investment_valuation",
            entity_id=valuation.id,
            action="created",
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A valuation for that investment and date already exists") from exc
    await session.refresh(valuation)
    return valuation


async def delete_valuation(
    session: AsyncSession,
    user_id: uuid.UUID,
    investment_id: uuid.UUID,
    valuation_id: uuid.UUID,
) -> None:
    valuation = await get_valuation(session, user_id, investment_id, valuation_id)
    await session.delete(valuation)
    audit.record(
        session,
        user_id=user_id,
        entity_type="investment_valuation",
        entity_id=valuation.id,
        action="deleted",
    )
    await session.commit()


def _accrual(investment: Investment, as_of: date) -> AccrualResult:
    if investment.rate is None or investment.rate_period is None:
        return AccrualResult(
            months_elapsed=0,
            day_fraction=Decimal(0),
            interest_minor=0,
            value_minor=investment.principal_minor,
        )
    return accrued_interest(
        principal_minor=investment.principal_minor,
        rate_percent=investment.rate,
        rate_period=investment.rate_period,
        start_date=investment.start_date,
        as_of=as_of,
        maturity_date=investment.maturity_date,
        compounding=investment.compounding,
    )


async def _latest_valuation(
    session: AsyncSession, user_id: uuid.UUID, investment_id: uuid.UUID, as_of: date
) -> InvestmentValuation | None:
    valuation = await session.scalar(
        _owned_valuations(user_id)
        .where(
            InvestmentValuation.investment_id == investment_id,
            InvestmentValuation.as_of <= as_of,
        )
        .order_by(InvestmentValuation.as_of.desc())
        .limit(1)
    )
    return valuation


def evaluate_value(
    investment: Investment,
    valuation: InvestmentValuation | None,
    as_of: date,
) -> InvestmentValue:
    """Value a holding at `as_of`, preferring an observed snapshot."""
    accrual = _accrual(investment, as_of)
    if valuation is not None:
        return InvestmentValue(
            value_minor=valuation.value_minor,
            source="valuation",
            valuation_as_of=valuation.as_of,
            accrued_interest_minor=accrual.interest_minor,
        )
    if investment.investment_type is InvestmentType.FIXED_RATE:
        return InvestmentValue(
            value_minor=accrual.value_minor,
            source="accrual",
            valuation_as_of=None,
            accrued_interest_minor=accrual.interest_minor,
        )
    return InvestmentValue(
        value_minor=investment.principal_minor,
        source="principal",
        valuation_as_of=None,
        accrued_interest_minor=0,
    )


async def investment_returns(
    session: AsyncSession,
    user_id: uuid.UUID,
    investment: Investment,
    *,
    as_of: date | None = None,
) -> InvestmentReturnsResponse:
    """Value the holding on `as_of`, preferring an observed valuation.

    A fixed-rate holding with no snapshot uses accrued value; a market-priced
    holding with no snapshot falls back to cost. `value_source` always says
    which basis was used, so a report never presents an estimate as market data.
    """
    requested = as_of or datetime.now(UTC).date()
    valuation = await _latest_valuation(session, user_id, investment.id, requested)
    evaluated = evaluate_value(investment, valuation, requested)
    value_minor = evaluated.value_minor

    gain_minor = value_minor - investment.principal_minor
    gain_percent = (
        (Decimal(gain_minor) / Decimal(investment.principal_minor) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if investment.principal_minor
        else Decimal("0.00")
    )

    monthly_projection: int | None = None
    annual_projection: int | None = None
    if (
        investment.investment_type is InvestmentType.FIXED_RATE
        and investment.rate is not None
        and investment.rate_period is not None
    ):
        monthly_projection = project_interest(
            principal_minor=investment.principal_minor,
            rate_percent=investment.rate,
            rate_period=investment.rate_period,
            months=1,
            compounding=investment.compounding,
        )
        annual_projection = project_interest(
            principal_minor=investment.principal_minor,
            rate_percent=investment.rate,
            rate_period=investment.rate_period,
            months=12,
            compounding=investment.compounding,
        )

    return InvestmentReturnsResponse(
        investment_id=investment.id,
        name=investment.name,
        currency=investment.currency,
        as_of=requested,
        principal_minor=investment.principal_minor,
        value_minor=value_minor,
        value_source=evaluated.source,
        valuation_as_of=evaluated.valuation_as_of,
        accrued_interest_minor=evaluated.accrued_interest_minor,
        gain_minor=gain_minor,
        gain_percent=gain_percent,
        projected_monthly_interest_minor=monthly_projection,
        projected_annual_interest_minor=annual_projection,
        start_date=investment.start_date,
        maturity_date=investment.maturity_date,
    )
