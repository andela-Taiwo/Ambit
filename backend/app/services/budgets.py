"""Budget CRUD and budget-vs-actual calculation."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import Budget, Transaction
from app.domain.budgets import (
    BudgetPeriodError,
    BudgetPeriodResult,
    PeriodRange,
    calculate_rollover_in,
    evaluate_period,
    month_range,
    period_for,
    prior_months,
    validate_budget_window,
)
from app.domain.categories import CategoryKind
from app.domain.fx import MissingRateError, RateBook, convert_minor_units
from app.domain.ledger import TransactionType
from app.domain.money import Currency, InvalidAmountError, to_minor_units
from app.schemas.budgets import BudgetCreate, BudgetStatusResponse, BudgetUpdate
from app.services import audit
from app.services import fx as fx_service
from app.services.categories import category_subtree_map, get_category


def _owned(user_id: uuid.UUID) -> Select[tuple[Budget]]:
    return select(Budget).where(Budget.user_id == user_id)


async def get_budget(session: AsyncSession, user_id: uuid.UUID, budget_id: uuid.UUID) -> Budget:
    budget = await session.scalar(_owned(user_id).where(Budget.id == budget_id))
    if budget is None:
        raise NotFoundError("Budget not found")
    return budget


async def list_budgets(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    category_id: uuid.UUID | None = None,
    include_archived: bool = False,
) -> tuple[list[Budget], int]:
    query = _owned(user_id)
    if category_id is not None:
        query = query.where(Budget.category_id == category_id)
    if not include_archived:
        query = query.where(Budget.is_archived.is_(False))

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(Budget.starts_on.desc(), Budget.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def _assert_no_other_active_budget(
    session: AsyncSession,
    user_id: uuid.UUID,
    category_id: uuid.UUID,
    *,
    exclude_id: uuid.UUID | None = None,
) -> None:
    query = _owned(user_id).where(
        Budget.category_id == category_id,
        Budget.is_archived.is_(False),
    )
    if exclude_id is not None:
        query = query.where(Budget.id != exclude_id)
    if await session.scalar(query) is not None:
        raise ConflictError("An active budget already exists for that category")


async def create_budget(session: AsyncSession, user_id: uuid.UUID, payload: BudgetCreate) -> Budget:
    category = await get_category(session, user_id, payload.category_id)
    if category.kind is not CategoryKind.EXPENSE:
        raise ValidationError("Budgets can only be set on expense categories")
    if category.is_archived:
        raise ValidationError("Cannot budget an archived category")

    try:
        validate_budget_window(payload.starts_on, payload.ends_on)
    except BudgetPeriodError as exc:
        raise ValidationError(str(exc)) from exc

    currency = Currency(payload.currency)
    try:
        amount_minor = to_minor_units(payload.amount, currency)
    except InvalidAmountError as exc:
        raise ValidationError(str(exc)) from exc

    await _assert_no_other_active_budget(session, user_id, category.id)

    budget = Budget(
        user_id=user_id,
        category_id=category.id,
        amount_minor=amount_minor,
        currency=currency.code,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        rollover_enabled=payload.rollover_enabled,
    )
    session.add(budget)
    try:
        await session.flush()
        audit.record(
            session,
            user_id=user_id,
            entity_type="budget",
            entity_id=budget.id,
            action="created",
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("A budget for that category and month already exists") from exc
    await session.refresh(budget)
    return budget


async def update_budget(
    session: AsyncSession,
    user_id: uuid.UUID,
    budget_id: uuid.UUID,
    payload: BudgetUpdate,
) -> Budget:
    budget = await get_budget(session, user_id, budget_id)

    if payload.amount is not None:
        currency = Currency(budget.currency)
        try:
            budget.amount_minor = to_minor_units(payload.amount, currency)
        except InvalidAmountError as exc:
            raise ValidationError(str(exc)) from exc

    if "ends_on" in payload.model_fields_set:
        try:
            validate_budget_window(budget.starts_on, payload.ends_on)
        except BudgetPeriodError as exc:
            raise ValidationError(str(exc)) from exc
        budget.ends_on = payload.ends_on

    if payload.rollover_enabled is not None:
        budget.rollover_enabled = payload.rollover_enabled

    if payload.is_archived is not None:
        if not payload.is_archived and budget.is_archived:
            await _assert_no_other_active_budget(
                session, user_id, budget.category_id, exclude_id=budget.id
            )
        budget.is_archived = payload.is_archived

    audit.record(
        session,
        user_id=user_id,
        entity_type="budget",
        entity_id=budget.id,
        action="updated",
    )
    await session.commit()
    await session.refresh(budget)
    return budget


async def delete_budget(session: AsyncSession, user_id: uuid.UUID, budget_id: uuid.UUID) -> None:
    budget = await get_budget(session, user_id, budget_id)
    await session.delete(budget)
    audit.record(
        session,
        user_id=user_id,
        entity_type="budget",
        entity_id=budget.id,
        action="deleted",
    )
    await session.commit()


def _end_of_day(value: date) -> datetime:
    """Rates are observed during the day; use the whole day when converting."""
    return datetime.combine(value, time.max, tzinfo=UTC)


def _period_end_day(period: PeriodRange) -> date:
    return period.end - timedelta(days=1)


async def _spend_by_month(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    category_ids: frozenset[uuid.UUID],
    window_start: date,
    window_end: date,
    budget_currency: str,
    rate_book: RateBook,
) -> tuple[dict[date, int], dict[date, int]]:
    """Converted spend and transaction count per month for a category subtree.

    Transfers are excluded by design: moving money between your own accounts is
    not spending, and counting it would make every transfer reduce two budgets.
    """
    if not category_ids:
        return {}, {}

    rows = await session.execute(
        select(
            Transaction.occurred_on,
            Transaction.currency,
            Transaction.amount_minor,
        ).where(
            Transaction.user_id == user_id,
            Transaction.transaction_type == TransactionType.EXPENSE,
            Transaction.category_id.in_(category_ids),
            Transaction.occurred_on >= window_start,
            Transaction.occurred_on < window_end,
        )
    )

    amounts: dict[date, int] = {}
    counts: dict[date, int] = {}
    for occurred_on, currency, amount_minor in rows:
        key = occurred_on.replace(day=1)
        if currency == budget_currency:
            converted = amount_minor
        else:
            try:
                resolved = rate_book.resolve(currency, budget_currency, _end_of_day(occurred_on))
            except MissingRateError as exc:
                raise ValidationError(str(exc)) from exc
            converted = convert_minor_units(
                amount_minor,
                from_currency=currency,
                to_currency=budget_currency,
                rate=resolved.rate,
            )
        amounts[key] = amounts.get(key, 0) + converted
        counts[key] = counts.get(key, 0) + 1

    return amounts, counts


async def budget_status(
    session: AsyncSession,
    user_id: uuid.UUID,
    budget: Budget,
    *,
    requested_month: date,
    rate_book: RateBook | None = None,
    subtree_map: dict[uuid.UUID, frozenset[uuid.UUID]] | None = None,
) -> BudgetStatusResponse:
    """Calculate one budget's status for `requested_month`.

    Rollover walks every month since the budget started, so the result reflects
    the real accumulated position rather than only the current month's numbers.
    """
    period = period_for(
        starts_on=budget.starts_on,
        ends_on=budget.ends_on,
        requested=requested_month,
    )
    if period is None:
        raise NotFoundError("Budget does not apply to the requested period")

    book = rate_book or await fx_service.load_rate_book(
        session, user_id, as_of=_end_of_day(_period_end_day(period))
    )
    subtrees = subtree_map or await category_subtree_map(session, user_id)
    category_ids = subtrees.get(budget.category_id, frozenset({budget.category_id}))

    amounts, counts = await _spend_by_month(
        session,
        user_id=user_id,
        category_ids=category_ids,
        window_start=budget.starts_on,
        window_end=period.end,
        budget_currency=budget.currency,
        rate_book=book,
    )

    prior = prior_months(starts_on=budget.starts_on, period=period)
    rollover_in = calculate_rollover_in(
        limit_minor=budget.amount_minor,
        prior_spends=[amounts.get(month.start, 0) for month in prior],
        enabled=budget.rollover_enabled,
    )

    result = evaluate_period(
        period=period,
        limit_minor=budget.amount_minor,
        spent_minor=amounts.get(period.start, 0),
        rollover_in_minor=rollover_in,
        rollover_enabled=budget.rollover_enabled,
    )
    return _to_response(budget, result, counts.get(period.start, 0))


def _to_response(
    budget: Budget, result: BudgetPeriodResult, transaction_count: int
) -> BudgetStatusResponse:
    return BudgetStatusResponse(
        budget_id=budget.id,
        category_id=budget.category_id,
        currency=budget.currency,
        period_start=result.period.start,
        period_end=result.period.end,
        limit_minor=result.limit_minor,
        rollover_in_minor=result.rollover_in_minor,
        effective_limit_minor=result.effective_limit_minor,
        spent_minor=result.spent_minor,
        remaining_minor=result.remaining_minor,
        carry_forward_minor=result.carry_forward_minor,
        percent_used=result.percent_used,
        status=result.status,
        transaction_count=transaction_count,
    )


async def status_for_all_budgets(
    session: AsyncSession, user_id: uuid.UUID, *, requested_month: date
) -> list[BudgetStatusResponse]:
    """Status for every active budget that applies to the requested month."""
    budgets = list(
        await session.scalars(
            _owned(user_id)
            .where(Budget.is_archived.is_(False))
            .order_by(Budget.starts_on, Budget.created_at)
        )
    )
    if not budgets:
        return []

    end_of_period = _end_of_day(_period_end_day(period_for_month(requested_month)))
    rate_book = await fx_service.load_rate_book(session, user_id, as_of=end_of_period)
    subtrees = await category_subtree_map(session, user_id)

    results: list[BudgetStatusResponse] = []
    for budget in budgets:
        period = period_for(
            starts_on=budget.starts_on,
            ends_on=budget.ends_on,
            requested=requested_month,
        )
        if period is None:
            continue
        results.append(
            await budget_status(
                session,
                user_id,
                budget,
                requested_month=requested_month,
                rate_book=rate_book,
                subtree_map=subtrees,
            )
        )
    return results


def period_for_month(requested_month: date) -> PeriodRange:
    """Expose the month range so the API can include it in portfolio responses."""
    return month_range(requested_month)
