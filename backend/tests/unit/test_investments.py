"""Interest and accrual mathematics for investments."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.investments import (
    Compounding,
    InvestmentMathError,
    RatePeriod,
    accrued_interest,
    monthly_rate,
    project_interest,
    split_months,
)

TEN_MILLION_NAIRA_MINOR = 1_000_000_000


class TestMonthlyRate:
    def test_annual_rate_is_divided_by_twelve(self) -> None:
        assert monthly_rate(Decimal("24"), RatePeriod.ANNUAL) == Decimal("0.02")

    def test_monthly_rate_is_used_as_stated(self) -> None:
        assert monthly_rate(Decimal("2"), RatePeriod.MONTHLY) == Decimal("0.02")

    @pytest.mark.parametrize("rate", [Decimal("0"), Decimal("-1"), Decimal("NaN")])
    def test_rejects_an_unusable_rate(self, rate: Decimal) -> None:
        with pytest.raises(InvestmentMathError):
            monthly_rate(rate, RatePeriod.ANNUAL)


class TestSplitMonths:
    def test_exactly_one_month(self) -> None:
        assert split_months(date(2026, 1, 1), date(2026, 2, 1)) == (1, Decimal(0))

    def test_partial_month_uses_the_calendar_month(self) -> None:
        months, fraction = split_months(date(2026, 1, 15), date(2026, 2, 1))

        assert months == 0
        assert fraction == Decimal(17) / Decimal(31)

    def test_month_end_is_clamped_without_drifting(self) -> None:
        """31 January plus one month is 28 February in a non-leap year."""
        assert split_months(date(2026, 1, 31), date(2026, 2, 28)) == (1, Decimal(0))

    def test_short_month_ending_keeps_a_remainder(self) -> None:
        months, fraction = split_months(date(2026, 1, 31), date(2026, 3, 1))

        assert months == 1
        assert fraction == Decimal(1) / Decimal(28)

    def test_backwards_range_is_zero(self) -> None:
        assert split_months(date(2026, 2, 1), date(2026, 1, 1)) == (0, Decimal(0))


class TestProjectInterest:
    def test_the_plan_worked_example(self) -> None:
        """10,000,000 NGN at 24% per annum earns 200,000 NGN in one month."""
        interest = project_interest(
            principal_minor=TEN_MILLION_NAIRA_MINOR,
            rate_percent=Decimal("24"),
            rate_period=RatePeriod.ANNUAL,
            months=1,
        )

        assert interest == 20_000_000

    def test_simple_interest_over_a_year(self) -> None:
        assert (
            project_interest(
                principal_minor=TEN_MILLION_NAIRA_MINOR,
                rate_percent=Decimal("24"),
                rate_period=RatePeriod.ANNUAL,
                months=12,
            )
            == 240_000_000
        )

    def test_monthly_quoted_rate(self) -> None:
        assert (
            project_interest(
                principal_minor=TEN_MILLION_NAIRA_MINOR,
                rate_percent=Decimal("2"),
                rate_period=RatePeriod.MONTHLY,
                months=1,
            )
            == 20_000_000
        )

    def test_monthly_compounding(self) -> None:
        """24% annual compounded monthly for a year: 268,241,795 minor units."""
        assert (
            project_interest(
                principal_minor=TEN_MILLION_NAIRA_MINOR,
                rate_percent=Decimal("24"),
                rate_period=RatePeriod.ANNUAL,
                months=12,
                compounding=Compounding.MONTHLY,
            )
            == 268_241_795
        )

    def test_zero_principal_earns_nothing(self) -> None:
        assert (
            project_interest(
                principal_minor=0,
                rate_percent=Decimal("24"),
                rate_period=RatePeriod.ANNUAL,
                months=12,
            )
            == 0
        )

    def test_rejects_negative_principal(self) -> None:
        with pytest.raises(InvestmentMathError):
            project_interest(
                principal_minor=-1,
                rate_percent=Decimal("24"),
                rate_period=RatePeriod.ANNUAL,
                months=1,
            )

    def test_rejects_negative_months(self) -> None:
        with pytest.raises(InvestmentMathError):
            project_interest(
                principal_minor=100,
                rate_percent=Decimal("24"),
                rate_period=RatePeriod.ANNUAL,
                months=-1,
            )


class TestAccruedInterest:
    def test_one_full_month(self) -> None:
        result = accrued_interest(
            principal_minor=TEN_MILLION_NAIRA_MINOR,
            rate_percent=Decimal("24"),
            rate_period=RatePeriod.ANNUAL,
            start_date=date(2026, 1, 1),
            as_of=date(2026, 2, 1),
        )

        assert result.interest_minor == 20_000_000
        assert result.value_minor == 1_020_000_000
        assert result.months_elapsed == 1

    def test_partial_month_is_pro_rata(self) -> None:
        """17 of January's 31 days at 2% monthly: 109,677.42 NGN."""
        result = accrued_interest(
            principal_minor=TEN_MILLION_NAIRA_MINOR,
            rate_percent=Decimal("24"),
            rate_period=RatePeriod.ANNUAL,
            start_date=date(2026, 1, 15),
            as_of=date(2026, 2, 1),
        )

        assert result.interest_minor == 10_967_742
        assert result.months_elapsed == 0

    def test_before_the_start_date_accrues_nothing(self) -> None:
        result = accrued_interest(
            principal_minor=TEN_MILLION_NAIRA_MINOR,
            rate_percent=Decimal("24"),
            rate_period=RatePeriod.ANNUAL,
            start_date=date(2026, 1, 1),
            as_of=date(2025, 12, 31),
        )

        assert result.interest_minor == 0
        assert result.value_minor == TEN_MILLION_NAIRA_MINOR

    def test_accrual_stops_at_maturity(self) -> None:
        """Two months to maturity; asking six months later still yields two."""
        result = accrued_interest(
            principal_minor=TEN_MILLION_NAIRA_MINOR,
            rate_percent=Decimal("24"),
            rate_period=RatePeriod.ANNUAL,
            start_date=date(2026, 1, 1),
            as_of=date(2026, 7, 1),
            maturity_date=date(2026, 3, 1),
        )

        assert result.interest_minor == 40_000_000
        assert result.value_minor == 1_040_000_000

    def test_compound_accrual_matches_projection_at_a_month_boundary(self) -> None:
        result = accrued_interest(
            principal_minor=TEN_MILLION_NAIRA_MINOR,
            rate_percent=Decimal("24"),
            rate_period=RatePeriod.ANNUAL,
            start_date=date(2026, 1, 1),
            as_of=date(2027, 1, 1),
            compounding=Compounding.MONTHLY,
        )

        assert result.interest_minor == 268_241_795

    def test_rejects_maturity_before_start(self) -> None:
        with pytest.raises(InvestmentMathError):
            accrued_interest(
                principal_minor=100,
                rate_percent=Decimal("24"),
                rate_period=RatePeriod.ANNUAL,
                start_date=date(2026, 1, 1),
                as_of=date(2026, 2, 1),
                maturity_date=date(2025, 12, 1),
            )

    def test_zero_principal(self) -> None:
        result = accrued_interest(
            principal_minor=0,
            rate_percent=Decimal("24"),
            rate_period=RatePeriod.ANNUAL,
            start_date=date(2026, 1, 1),
            as_of=date(2026, 2, 1),
        )

        assert result.interest_minor == 0
        assert result.value_minor == 0
