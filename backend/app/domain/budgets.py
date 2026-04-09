"""Budget period and rollover mathematics.

This module is deliberately framework-free: the highest-risk bugs in budgeting
are off-by-one period boundaries and sign errors in rollover, so those rules
are pure functions exercised directly by unit tests (plan Section 12, Phase 3).

Periods are half-open `[start, end)` calendar months. A budget's `ends_on` is
the first month it no longer applies to; an empty range is therefore never
mistaken for a fully-elapsed one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Final

#: A hard bound on rollover walks. Fifty years of history is far beyond any
#: real budget, but it keeps a corrupted start date from looping forever.
MAX_ROLLOVER_MONTHS: Final = 600

#: Percentage at which a budget is shown as approaching its limit.
WARNING_THRESHOLD_PERCENT: Final = Decimal("80.00")


class BudgetPeriodError(ValueError):
    """The requested budget window is not a valid month-aligned range."""


class BudgetStatus(StrEnum):
    ON_TRACK = "on_track"
    WARNING = "warning"
    OVER = "over"


@dataclass(frozen=True, slots=True, order=True)
class PeriodRange:
    """A half-open date range: `start` inclusive, `end` exclusive."""

    start: date
    end: date

    @property
    def label(self) -> str:
        return f"{self.start.year:04d}-{self.start.month:02d}"


@dataclass(frozen=True, slots=True)
class BudgetPeriodResult:
    limit_minor: int
    rollover_in_minor: int
    effective_limit_minor: int
    spent_minor: int
    remaining_minor: int
    carry_forward_minor: int
    percent_used: Decimal
    status: BudgetStatus
    period: PeriodRange


def month_start(value: date) -> date:
    return value.replace(day=1)


def add_months(value: date, months: int) -> date:
    """Return the first day of the month `months` away from `value`.

    Integer month arithmetic avoids timedelta approximations and handles
    December/January and leap years without special cases.
    """
    index = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(index, 12)
    return date(year, month_index + 1, 1)


def month_range(value: date) -> PeriodRange:
    start = month_start(value)
    return PeriodRange(start=start, end=add_months(start, 1))


def months_between(start: date, end_exclusive: date) -> list[PeriodRange]:
    """Every calendar month in `[start, end_exclusive)`.

    `start` may be any day; it is normalised to the first of its month.
    """
    cursor = month_start(start)
    boundary = month_start(end_exclusive)
    periods: list[PeriodRange] = []

    while cursor < boundary:
        periods.append(month_range(cursor))
        cursor = add_months(cursor, 1)
        if len(periods) > MAX_ROLLOVER_MONTHS:
            raise BudgetPeriodError(f"Budget window spans more than {MAX_ROLLOVER_MONTHS} months")

    return periods


def validate_month_boundary(value: date, *, field: str) -> None:
    """Budgets are month-aligned; a mid-month start has no coherent meaning."""
    if value.day != 1:
        raise BudgetPeriodError(f"{field} must be the first day of a month")


def validate_budget_window(starts_on: date, ends_on: date | None) -> None:
    validate_month_boundary(starts_on, field="starts_on")
    if ends_on is None:
        return
    validate_month_boundary(ends_on, field="ends_on")
    if ends_on <= starts_on:
        raise BudgetPeriodError("ends_on must be after starts_on")


def period_for(
    *,
    starts_on: date,
    ends_on: date | None,
    requested: date,
) -> PeriodRange | None:
    """The month range a budget covers for `requested`, or None if it does not."""
    target = month_start(requested)
    start = month_start(starts_on)

    if target < start:
        return None
    if ends_on is not None and target >= month_start(ends_on):
        return None
    return month_range(target)


def prior_months(*, starts_on: date, period: PeriodRange) -> list[PeriodRange]:
    """Months before `period` since the budget began, oldest first."""
    return months_between(starts_on, period.start)


def calculate_rollover_in(
    *,
    limit_minor: int,
    prior_spends: Sequence[int],
    enabled: bool,
) -> int:
    """Unspent (or overspent) allowance carried into the current month.

    Overspending produces a negative carry: the next month starts already in
    deficit, which is the behaviour that makes a rollover budget honest rather
    than a way to hide a bad month.
    """
    if not enabled:
        return 0
    return sum(limit_minor - spent for spent in prior_spends)


def evaluate_period(
    *,
    period: PeriodRange,
    limit_minor: int,
    spent_minor: int,
    rollover_in_minor: int,
    rollover_enabled: bool,
) -> BudgetPeriodResult:
    effective_limit = limit_minor + rollover_in_minor
    remaining = effective_limit - spent_minor

    percent = _percent_used(spent_minor, effective_limit)
    if remaining < 0:
        status = BudgetStatus.OVER
    elif percent >= WARNING_THRESHOLD_PERCENT:
        status = BudgetStatus.WARNING
    else:
        status = BudgetStatus.ON_TRACK

    return BudgetPeriodResult(
        limit_minor=limit_minor,
        rollover_in_minor=rollover_in_minor,
        effective_limit_minor=effective_limit,
        spent_minor=spent_minor,
        remaining_minor=remaining,
        carry_forward_minor=remaining if rollover_enabled else 0,
        percent_used=percent,
        status=status,
        period=period,
    )


def _percent_used(spent_minor: int, effective_limit_minor: int) -> Decimal:
    if effective_limit_minor > 0:
        return (Decimal(spent_minor) / Decimal(effective_limit_minor) * 100).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    # A zero (or negative) allowance has no meaningful ratio. Spending against
    # it is 100% of "nothing", which reads more sensibly than a division error.
    return Decimal("100.00") if spent_minor > 0 else Decimal("0.00")
