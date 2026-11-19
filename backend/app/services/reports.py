"""Reporting: net worth, cash flow, category breakdown and CSV export.

Every amount is converted to the user's base currency with an explicit,
auditable rate. A missing rate fails the report with a 422 naming the pair and
date rather than quietly dropping or guessing a holding (plan Section 14).
"""

from __future__ import annotations

import csv
import io
import uuid
from bisect import bisect_right
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ValidationError
from app.db.models import Account, Category, Investment, InvestmentValuation, Transaction, User
from app.domain.accounts import AccountType
from app.domain.budgets import add_months, month_range, months_between
from app.domain.categories import CategoryKind
from app.domain.fx import MissingRateError, RateBook, convert_minor_units
from app.domain.ledger import TransactionType
from app.domain.money import Currency, format_minor_units
from app.schemas.investments import ValueSource
from app.schemas.reports import (
    CashFlowItem,
    CashFlowResponse,
    CategoryBreakdownItem,
    CategoryBreakdownResponse,
    ConvertedAmount,
    NetWorthAccount,
    NetWorthHistoryPoint,
    NetWorthHistoryResponse,
    NetWorthInvestment,
    NetWorthResponse,
)
from app.services import fx as fx_service
from app.services.investments import evaluate_value

#: Reports are capped so one request cannot ask for centuries of history.
MAX_REPORT_MONTHS = 120
MAX_HISTORY_POINTS = 60


@dataclass(frozen=True, slots=True)
class _AccountSnapshot:
    account_id: uuid.UUID
    name: str
    account_type: AccountType
    currency: str
    balance_minor: int


def _end_of_day(value: date) -> datetime:
    return datetime.combine(value, time.max, tzinfo=UTC)


def _convert(
    book: RateBook,
    *,
    amount_minor: int,
    currency: str,
    base_currency: str,
    at: date,
) -> ConvertedAmount:
    try:
        resolved = book.resolve(currency, base_currency, _end_of_day(at))
    except MissingRateError as exc:
        raise ValidationError(str(exc)) from exc

    converted = convert_minor_units(
        amount_minor,
        from_currency=currency,
        to_currency=base_currency,
        rate=resolved.rate,
    )
    return ConvertedAmount(
        currency=currency,
        amount_minor=amount_minor,
        base_currency=base_currency,
        base_minor=converted,
        rate=resolved.rate,
        rate_as_of=resolved.as_of.date(),
        rate_source=resolved.source,
        rate_is_inverse=resolved.is_inverse,
    )


async def _account_snapshots(
    session: AsyncSession, user_id: uuid.UUID, *, as_of: date
) -> list[_AccountSnapshot]:
    """Opening balance plus every signed movement up to `as_of`."""
    rows = await session.execute(
        select(
            Account.id,
            Account.name,
            Account.account_type,
            Account.currency,
            Account.opening_balance_minor,
            func.coalesce(func.sum(Transaction.signed_amount_minor), 0).label("movement"),
        )
        .outerjoin(
            Transaction,
            and_(
                Transaction.account_id == Account.id,
                Transaction.occurred_on <= as_of,
            ),
        )
        .where(
            Account.user_id == user_id,
            # Investment accounts are containers for the holdings in
            # `investments`; counting their ledger balance too would double
            # count the same money (ADR 0012).
            Account.account_type != AccountType.INVESTMENT,
        )
        .group_by(
            Account.id,
            Account.name,
            Account.account_type,
            Account.currency,
            Account.opening_balance_minor,
        )
        .order_by(Account.name)
    )

    return [
        _AccountSnapshot(
            account_id=row.id,
            name=row.name,
            account_type=row.account_type,
            currency=row.currency,
            balance_minor=int(row.opening_balance_minor) + int(row.movement),
        )
        for row in rows
    ]


async def _investments(session: AsyncSession, user_id: uuid.UUID) -> list[Investment]:
    return list(
        await session.scalars(
            select(Investment).where(Investment.user_id == user_id).order_by(Investment.name)
        )
    )


async def _valuations_until(
    session: AsyncSession, user_id: uuid.UUID, *, as_of: date
) -> dict[uuid.UUID, InvestmentValuation]:
    """Newest valuation per investment at or before `as_of`."""
    rows = await session.scalars(
        select(InvestmentValuation)
        .where(
            InvestmentValuation.user_id == user_id,
            InvestmentValuation.as_of <= as_of,
        )
        .order_by(InvestmentValuation.investment_id, InvestmentValuation.as_of.desc())
    )
    latest: dict[uuid.UUID, InvestmentValuation] = {}
    for valuation in rows:
        latest.setdefault(valuation.investment_id, valuation)
    return latest


def _investment_value(
    investment: Investment, valuations: dict[uuid.UUID, InvestmentValuation], at: date
) -> tuple[int, ValueSource, date | None]:
    evaluated = evaluate_value(investment, valuations.get(investment.id), at)
    return evaluated.value_minor, evaluated.source, evaluated.valuation_as_of


async def net_worth(session: AsyncSession, user: User, *, as_of: date) -> NetWorthResponse:
    book = await fx_service.load_rate_book(session, user.id, as_of=_end_of_day(as_of))
    accounts = await _account_snapshots(session, user.id, as_of=as_of)
    investments = await _investments(session, user.id)
    valuations = await _valuations_until(session, user.id, as_of=as_of)

    account_items = [
        NetWorthAccount(
            account_id=snapshot.account_id,
            name=snapshot.name,
            account_type=snapshot.account_type,
            balance=_convert(
                book,
                amount_minor=snapshot.balance_minor,
                currency=snapshot.currency,
                base_currency=user.base_currency,
                at=as_of,
            ),
        )
        for snapshot in accounts
    ]

    investment_items: list[NetWorthInvestment] = []
    for investment in investments:
        value_minor, source, valuation_as_of = _investment_value(investment, valuations, as_of)
        investment_items.append(
            NetWorthInvestment(
                investment_id=investment.id,
                name=investment.name,
                investment_type=investment.investment_type,
                value=_convert(
                    book,
                    amount_minor=value_minor,
                    currency=investment.currency,
                    base_currency=user.base_currency,
                    at=as_of,
                ),
                value_source=source,
                valuation_as_of=valuation_as_of,
            )
        )

    accounts_total = sum(item.balance.base_minor for item in account_items)
    investments_total = sum(item.value.base_minor for item in investment_items)

    return NetWorthResponse(
        as_of=as_of,
        base_currency=user.base_currency,
        total_minor=accounts_total + investments_total,
        accounts_total_minor=accounts_total,
        investments_total_minor=investments_total,
        accounts=account_items,
        investments=investment_items,
    )


async def net_worth_history(
    session: AsyncSession, user: User, *, months: int, as_of: date
) -> NetWorthHistoryResponse:
    """Month-end net worth for the trailing `months`, current month partial."""
    if months < 1 or months > MAX_HISTORY_POINTS:
        raise ValidationError(f"months must be between 1 and {MAX_HISTORY_POINTS}")

    current_month = month_range(as_of)
    start_month = add_months(current_month.start, -(months - 1))
    points = [
        min(period.end - timedelta(days=1), as_of)
        for period in months_between(start_month, current_month.end)
    ]
    if not points:  # pragma: no cover - months >= 1 guarantees one point
        return NetWorthHistoryResponse(base_currency=user.base_currency, points=[])

    max_point = points[-1]
    book = await fx_service.load_rate_book(session, user.id, as_of=_end_of_day(max_point))

    account_rows = (
        await session.execute(
            select(
                Account.id,
                Account.currency,
                Account.opening_balance_minor,
            ).where(
                Account.user_id == user.id,
                Account.account_type != AccountType.INVESTMENT,
            )
        )
    ).all()
    opening = {row.id: int(row.opening_balance_minor) for row in account_rows}
    currencies = {row.id: row.currency for row in account_rows}

    movements = (
        await session.execute(
            select(
                Transaction.account_id,
                Transaction.occurred_on,
                Transaction.signed_amount_minor,
            )
            .join(Account, Account.id == Transaction.account_id)
            .where(
                Transaction.user_id == user.id,
                Account.account_type != AccountType.INVESTMENT,
                Transaction.occurred_on <= max_point,
            )
            .order_by(Transaction.occurred_on)
        )
    ).all()

    investments = await _investments(session, user.id)
    valuation_rows = list(
        await session.scalars(
            select(InvestmentValuation)
            .where(
                InvestmentValuation.user_id == user.id,
                InvestmentValuation.as_of <= max_point,
            )
            .order_by(InvestmentValuation.investment_id, InvestmentValuation.as_of)
        )
    )
    valuation_dates: dict[uuid.UUID, list[date]] = {}
    valuation_by_investment: dict[uuid.UUID, list[InvestmentValuation]] = {}
    for valuation in valuation_rows:
        valuation_dates.setdefault(valuation.investment_id, []).append(valuation.as_of)
        valuation_by_investment.setdefault(valuation.investment_id, []).append(valuation)

    balances = dict(opening)
    movement_index = 0
    history: list[NetWorthHistoryPoint] = []

    for point in points:
        while movement_index < len(movements):
            movement = movements[movement_index]
            if movement.occurred_on > point:
                break
            balances[movement.account_id] = balances.get(movement.account_id, 0) + int(
                movement.signed_amount_minor
            )
            movement_index += 1

        accounts_total = sum(
            _convert(
                book,
                amount_minor=balance,
                currency=currencies.get(account_id, user.base_currency),
                base_currency=user.base_currency,
                at=point,
            ).base_minor
            for account_id, balance in balances.items()
        )

        investments_total = 0
        for investment in investments:
            dates = valuation_dates.get(investment.id, [])
            position = bisect_right(dates, point) - 1
            latest_valuation = (
                valuation_by_investment[investment.id][position] if position >= 0 else None
            )
            value_minor, _, _ = _investment_value(
                investment,
                {investment.id: latest_valuation} if latest_valuation is not None else {},
                point,
            )
            investments_total += _convert(
                book,
                amount_minor=value_minor,
                currency=investment.currency,
                base_currency=user.base_currency,
                at=point,
            ).base_minor

        history.append(
            NetWorthHistoryPoint(
                as_of=point,
                total_minor=accounts_total + investments_total,
                accounts_minor=accounts_total,
                investments_minor=investments_total,
            )
        )

    return NetWorthHistoryResponse(base_currency=user.base_currency, points=history)


def _resolve_range(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    today = datetime.now(UTC).date()
    resolved_to = date_to or today
    resolved_from = date_from or month_range(resolved_to).start
    if resolved_from > resolved_to:
        raise ValidationError("date_from must not be after date_to")
    if (resolved_to - resolved_from).days > MAX_REPORT_MONTHS * 31:
        raise ValidationError(f"Reporting window is limited to {MAX_REPORT_MONTHS} months")
    return resolved_from, resolved_to


async def cash_flow(
    session: AsyncSession,
    user: User,
    *,
    date_from: date | None,
    date_to: date | None,
) -> CashFlowResponse:
    start, end = _resolve_range(date_from, date_to)
    book = await fx_service.load_rate_book(session, user.id, as_of=_end_of_day(end))

    rows = await session.execute(
        select(
            Transaction.occurred_on,
            Transaction.transaction_type,
            Transaction.currency,
            Transaction.amount_minor,
        ).where(
            Transaction.user_id == user.id,
            Transaction.transaction_type.in_((TransactionType.INCOME, TransactionType.EXPENSE)),
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
        )
    )

    buckets: dict[date, list[int]] = {}
    for occurred_on, transaction_type, currency, amount_minor in rows:
        key = occurred_on.replace(day=1)
        bucket = buckets.setdefault(key, [0, 0, 0])
        converted = _convert(
            book,
            amount_minor=int(amount_minor),
            currency=currency,
            base_currency=user.base_currency,
            at=occurred_on,
        ).base_minor
        if transaction_type is TransactionType.INCOME:
            bucket[0] += converted
        else:
            bucket[1] += converted
        bucket[2] += 1

    items: list[CashFlowItem] = []
    for period in months_between(month_range(start).start, add_months(month_range(end).start, 1)):
        income, expense, count = buckets.get(period.start, [0, 0, 0])
        items.append(
            CashFlowItem(
                period_start=period.start,
                period_end=period.end,
                income_minor=income,
                expense_minor=expense,
                net_minor=income - expense,
                transaction_count=count,
            )
        )

    return CashFlowResponse(
        base_currency=user.base_currency,
        date_from=start,
        date_to=end,
        items=items,
    )


async def category_breakdown(
    session: AsyncSession,
    user: User,
    *,
    date_from: date | None,
    date_to: date | None,
    kind: CategoryKind,
    include_subcategories: bool,
) -> CategoryBreakdownResponse:
    start, end = _resolve_range(date_from, date_to)
    book = await fx_service.load_rate_book(session, user.id, as_of=_end_of_day(end))

    category_rows = (
        await session.execute(
            select(Category.id, Category.name, Category.parent_id).where(
                Category.user_id == user.id
            )
        )
    ).all()
    by_id = {row.id: row for row in category_rows}

    def rollup_id(category_id: uuid.UUID) -> uuid.UUID | None:
        current = category_id
        seen: set[uuid.UUID] = set()
        while current in by_id and current not in seen:
            seen.add(current)
            parent = by_id[current].parent_id
            if parent is None:
                return current
            current = parent
        return category_id

    transaction_type = (
        TransactionType.EXPENSE if kind is CategoryKind.EXPENSE else TransactionType.INCOME
    )
    rows = await session.execute(
        select(
            Transaction.category_id,
            Transaction.occurred_on,
            Transaction.currency,
            Transaction.amount_minor,
        ).where(
            Transaction.user_id == user.id,
            Transaction.transaction_type == transaction_type,
            Transaction.occurred_on >= start,
            Transaction.occurred_on <= end,
        )
    )

    totals: dict[uuid.UUID | None, list[int]] = {}
    for category_id, occurred_on, currency, amount_minor in rows:
        key = rollup_id(category_id) if (include_subcategories and category_id) else category_id
        bucket = totals.setdefault(key, [0, 0])
        bucket[0] += _convert(
            book,
            amount_minor=int(amount_minor),
            currency=currency,
            base_currency=user.base_currency,
            at=occurred_on,
        ).base_minor
        bucket[1] += 1

    grand_total = sum(bucket[0] for bucket in totals.values())
    items: list[CategoryBreakdownItem] = []
    for category_id, (total, count) in totals.items():
        category = by_id.get(category_id) if category_id is not None else None
        percent = (
            (Decimal(total) / Decimal(grand_total) * 100).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            if grand_total
            else Decimal("0.00")
        )
        items.append(
            CategoryBreakdownItem(
                category_id=category_id,
                name=category.name if category is not None else "Uncategorized",
                parent_id=category.parent_id if category is not None else None,
                total_minor=total,
                transaction_count=count,
                percent_of_total=percent,
            )
        )

    items.sort(key=lambda item: (-item.total_minor, item.name))

    return CategoryBreakdownResponse(
        base_currency=user.base_currency,
        date_from=start,
        date_to=end,
        kind=kind,
        include_subcategories=include_subcategories,
        total_minor=grand_total,
        items=items,
    )


_CSV_HEADER = (
    "occurred_on",
    "transaction_type",
    "account",
    "category",
    "amount",
    "currency",
    "description",
    "notes",
    "transfer_group_id",
    "id",
)


def _csv_safe(value: str) -> str:
    """Neutralise spreadsheet formula injection in exported text fields."""
    return f"'{value}" if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


async def transaction_csv(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    date_from: date | None,
    date_to: date | None,
) -> AsyncIterator[str]:
    """Stream a CSV export without holding the whole ledger in memory."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")

    def flush() -> str:
        value = buffer.getvalue()
        buffer.seek(0)
        buffer.truncate(0)
        return value

    writer.writerow(_CSV_HEADER)
    yield flush()

    query = (
        select(
            Transaction.occurred_on,
            Transaction.transaction_type,
            Account.name,
            Category.name,
            Transaction.amount_minor,
            Transaction.currency,
            Transaction.description,
            Transaction.notes,
            Transaction.transfer_group_id,
            Transaction.id,
        )
        .join(Account, Account.id == Transaction.account_id)
        .outerjoin(Category, Category.id == Transaction.category_id)
        .where(Transaction.user_id == user_id)
    )
    if date_from is not None:
        query = query.where(Transaction.occurred_on >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_on <= date_to)
    query = query.order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc())

    result = await session.stream(query)
    async for (
        occurred_on,
        transaction_type,
        account_name,
        category_name,
        amount_minor,
        currency,
        description,
        notes,
        transfer_group_id,
        transaction_id,
    ) in result:
        writer.writerow(
            [
                occurred_on.isoformat(),
                transaction_type.value,
                _csv_safe(account_name),
                _csv_safe(category_name or ""),
                format_minor_units(int(amount_minor), Currency(currency)),
                currency,
                _csv_safe(description),
                _csv_safe(notes or ""),
                str(transfer_group_id or ""),
                str(transaction_id),
            ]
        )
        yield flush()
