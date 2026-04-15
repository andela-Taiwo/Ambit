"""Investment interest and valuation mathematics.

Money stays in integer minor units and rates are `Decimal` percentages. Every
result is rounded exactly once, half-even. Two cases matter most:

* **Full calendar months accrue at the product's stated monthly rate.** The
  plan's worked example -- 10,000,000 NGN at 24% per annum -- must produce
  exactly 200,000 NGN for one month, not the 197,260 an ACT/365 shortcut gives.
* **A partial month accrues pro rata by days in that calendar month.** No
  approximation is silently applied to the full months before it.

Compounding is monthly when selected: interest is added to principal at each
month boundary, with any partial month accruing simple interest on the
resulting balance.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from enum import StrEnum
from typing import Final

_WORKING_PRECISION: Final = 50


class InvestmentMathError(ValueError):
    """The investment parameters cannot produce a meaningful accrual."""


class InvestmentType(StrEnum):
    """How the holding is valued."""

    FIXED_RATE = "fixed_rate"
    MARKET_PRICED = "market_priced"


class RatePeriod(StrEnum):
    """The period the stated rate applies to."""

    ANNUAL = "annual"
    MONTHLY = "monthly"


class Compounding(StrEnum):
    SIMPLE = "simple"
    MONTHLY = "monthly"


@dataclass(frozen=True, slots=True)
class AccrualResult:
    months_elapsed: int
    day_fraction: Decimal
    interest_minor: int
    value_minor: int


def validate_rate(rate: Decimal) -> Decimal:
    if not rate.is_finite() or rate <= 0:
        raise InvestmentMathError(f"Interest rate must be a finite positive number, got {rate!r}")
    return rate


def monthly_rate(rate_percent: Decimal, rate_period: RatePeriod) -> Decimal:
    """Convert a stated rate to the monthly rate used for accrual.

    24% per annum becomes 2% per month; a product quoted at 2% per month is
    used as-is. This is the exact conversion the worked example depends on.
    """
    validated = validate_rate(rate_percent)
    with localcontext() as ctx:
        ctx.prec = _WORKING_PRECISION
        if rate_period is RatePeriod.ANNUAL:
            return validated / Decimal(100) / Decimal(12)
        return validated / Decimal(100)


def _add_months_clamped(value: date, months: int) -> date:
    """Add months, clamping the day to the target month's length."""
    index = value.year * 12 + (value.month - 1) + months
    year, month_index = divmod(index, 12)
    month = month_index + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def split_months(start: date, end: date) -> tuple[int, Decimal]:
    """Split `[start, end]` into completed calendar months and a day fraction.

    The anchor preserves the start day-of-month (clamped for short months), so
    "one month" from 31 January is 28/29 February rather than a fixed 30 days.
    """
    if end <= start:
        return 0, Decimal(0)

    months = (end.year - start.year) * 12 + (end.month - start.month)
    anchor = _add_months_clamped(start, months)
    while anchor > end:
        months -= 1
        anchor = _add_months_clamped(start, months)

    next_anchor = _add_months_clamped(anchor, 1)
    if anchor == end:
        return months, Decimal(0)

    days_in_period = (next_anchor - anchor).days
    fraction = Decimal((end - anchor).days) / Decimal(days_in_period)
    return months, fraction


def _round_minor(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_EVEN))


def project_interest(
    *,
    principal_minor: int,
    rate_percent: Decimal,
    rate_period: RatePeriod,
    months: int,
    compounding: Compounding = Compounding.SIMPLE,
) -> int:
    """Interest earned over `months` full months, rounded to minor units."""
    if principal_minor < 0:
        raise InvestmentMathError("Principal must not be negative")
    if months < 0:
        raise InvestmentMathError("Months must not be negative")
    if principal_minor == 0 or months == 0:
        return 0

    monthly = monthly_rate(rate_percent, rate_period)
    with localcontext() as ctx:
        ctx.prec = _WORKING_PRECISION
        principal = Decimal(principal_minor)
        if compounding is Compounding.SIMPLE:
            interest = principal * monthly * months
        else:
            interest = principal * ((Decimal(1) + monthly) ** months - Decimal(1))
        return _round_minor(interest)


def accrued_interest(
    *,
    principal_minor: int,
    rate_percent: Decimal,
    rate_period: RatePeriod,
    start_date: date,
    as_of: date,
    maturity_date: date | None = None,
    compounding: Compounding = Compounding.SIMPLE,
) -> AccrualResult:
    """Interest accrued from `start_date` to `as_of`, capped at maturity.

    Accrual stops at `maturity_date`: a matured product does not keep earning
    at its coupon rate unless it is rolled over into a new holding.
    """
    if principal_minor < 0:
        raise InvestmentMathError("Principal must not be negative")
    if maturity_date is not None and maturity_date < start_date:
        raise InvestmentMathError("Maturity date cannot be before the start date")

    effective_end = as_of if maturity_date is None else min(as_of, maturity_date)
    months, day_fraction = split_months(start_date, effective_end)
    if principal_minor == 0 or (months == 0 and day_fraction == 0):
        return AccrualResult(
            months_elapsed=0,
            day_fraction=Decimal(0),
            interest_minor=0,
            value_minor=principal_minor,
        )

    monthly = monthly_rate(rate_percent, rate_period)
    with localcontext() as ctx:
        ctx.prec = _WORKING_PRECISION
        principal = Decimal(principal_minor)
        if compounding is Compounding.SIMPLE:
            interest = principal * monthly * (Decimal(months) + day_fraction)
            value = principal + interest
        else:
            balance = principal * (Decimal(1) + monthly) ** months
            interest = (balance - principal) + balance * monthly * day_fraction
            value = balance + balance * monthly * day_fraction

        return AccrualResult(
            months_elapsed=months,
            day_fraction=day_fraction,
            interest_minor=_round_minor(interest),
            value_minor=_round_minor(value),
        )
