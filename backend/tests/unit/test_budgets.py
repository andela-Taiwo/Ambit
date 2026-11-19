"""Budget period boundaries and rollover arithmetic."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from app.domain.budgets import (
    BudgetPeriodError,
    BudgetStatus,
    add_months,
    calculate_rollover_in,
    evaluate_period,
    month_range,
    month_start,
    months_between,
    period_for,
    prior_months,
    validate_budget_window,
)


class TestMonthArithmetic:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (date(2026, 7, 15), date(2026, 7, 1)),
            (date(2026, 1, 1), date(2026, 1, 1)),
        ],
    )
    def test_month_start(self, value: date, expected: date) -> None:
        assert month_start(value) == expected

    @pytest.mark.parametrize(
        ("start", "months", "expected"),
        [
            (date(2026, 1, 1), 1, date(2026, 2, 1)),
            (date(2026, 12, 1), 1, date(2027, 1, 1)),
            (date(2026, 1, 1), 12, date(2027, 1, 1)),
            (date(2026, 1, 1), -1, date(2025, 12, 1)),
            (date(2024, 2, 1), 12, date(2025, 2, 1)),
        ],
    )
    def test_add_months(self, start: date, months: int, expected: date) -> None:
        assert add_months(start, months) == expected

    def test_month_range_is_half_open(self) -> None:
        period = month_range(date(2026, 2, 14))

        assert period.start == date(2026, 2, 1)
        assert period.end == date(2026, 3, 1)

    def test_months_between_covers_every_month(self) -> None:
        periods = months_between(date(2025, 11, 1), date(2026, 2, 1))

        assert [period.start for period in periods] == [
            date(2025, 11, 1),
            date(2025, 12, 1),
            date(2026, 1, 1),
        ]

    def test_months_between_is_empty_for_an_empty_window(self) -> None:
        assert months_between(date(2026, 1, 1), date(2026, 1, 1)) == []


class TestValidation:
    def test_rejects_a_mid_month_start(self) -> None:
        with pytest.raises(BudgetPeriodError):
            validate_budget_window(date(2026, 1, 15), None)

    def test_rejects_a_mid_month_end(self) -> None:
        with pytest.raises(BudgetPeriodError):
            validate_budget_window(date(2026, 1, 1), date(2026, 3, 15))

    def test_rejects_an_end_not_after_the_start(self) -> None:
        with pytest.raises(BudgetPeriodError):
            validate_budget_window(date(2026, 1, 1), date(2026, 1, 1))

    def test_accepts_a_month_aligned_window(self) -> None:
        validate_budget_window(date(2026, 1, 1), date(2026, 4, 1))


class TestPeriodFor:
    def test_returns_the_requested_month(self) -> None:
        period = period_for(starts_on=date(2026, 1, 1), ends_on=None, requested=date(2026, 2, 17))

        assert period is not None
        assert period.start == date(2026, 2, 1)
        assert period.end == date(2026, 3, 1)

    def test_returns_none_before_the_budget_starts(self) -> None:
        assert (
            period_for(starts_on=date(2026, 2, 1), ends_on=None, requested=date(2026, 1, 1)) is None
        )

    def test_ends_on_is_exclusive(self) -> None:
        """A budget ending 2026-03-01 covers February but not March."""
        assert (
            period_for(
                starts_on=date(2026, 1, 1), ends_on=date(2026, 3, 1), requested=date(2026, 2, 1)
            )
            is not None
        )
        assert (
            period_for(
                starts_on=date(2026, 1, 1), ends_on=date(2026, 3, 1), requested=date(2026, 3, 1)
            )
            is None
        )


class TestRollover:
    def test_disabled_rollover_carries_nothing(self) -> None:
        assert (
            calculate_rollover_in(limit_minor=100_00, prior_spends=[0, 10_00], enabled=False) == 0
        )

    def test_unspent_allowance_accumulates(self) -> None:
        """100.00 limit, spent 40.00 then 0.00: 160.00 carried in."""
        assert (
            calculate_rollover_in(limit_minor=10_000, prior_spends=[4_000, 0], enabled=True)
            == 16_000
        )

    def test_overspending_reduces_the_carry(self) -> None:
        """100.00 limit, spent 130.00 then 50.00: 20.00 carried in."""
        assert (
            calculate_rollover_in(limit_minor=10_000, prior_spends=[13_000, 5_000], enabled=True)
            == 2_000
        )

    def test_overspending_can_make_the_carry_negative(self) -> None:
        assert (
            calculate_rollover_in(limit_minor=10_000, prior_spends=[25_000], enabled=True)
            == -15_000
        )

    def test_prior_months_stop_before_the_target(self) -> None:
        periods = prior_months(starts_on=date(2025, 11, 1), period=month_range(date(2026, 2, 1)))

        assert [period.start.month for period in periods] == [11, 12, 1]


class TestEvaluatePeriod:
    def test_on_track(self) -> None:
        result = evaluate_period(
            period=month_range(date(2026, 2, 1)),
            limit_minor=100_00,
            spent_minor=25_00,
            rollover_in_minor=0,
            rollover_enabled=False,
        )

        assert result.status is BudgetStatus.ON_TRACK
        assert result.remaining_minor == 75_00
        assert result.percent_used == Decimal("25.00")
        assert result.carry_forward_minor == 0

    def test_warning_at_eighty_percent(self) -> None:
        result = evaluate_period(
            period=month_range(date(2026, 2, 1)),
            limit_minor=100_00,
            spent_minor=80_00,
            rollover_in_minor=0,
            rollover_enabled=False,
        )

        assert result.status is BudgetStatus.WARNING
        assert result.percent_used == Decimal("80.00")

    def test_over_budget_is_negative_remaining(self) -> None:
        result = evaluate_period(
            period=month_range(date(2026, 2, 1)),
            limit_minor=100_00,
            spent_minor=120_50,
            rollover_in_minor=0,
            rollover_enabled=False,
        )

        assert result.status is BudgetStatus.OVER
        assert result.remaining_minor == -20_50

    def test_rollover_increases_the_effective_limit(self) -> None:
        result = evaluate_period(
            period=month_range(date(2026, 2, 1)),
            limit_minor=100_00,
            spent_minor=90_00,
            rollover_in_minor=50_00,
            rollover_enabled=True,
        )

        assert result.effective_limit_minor == 150_00
        assert result.remaining_minor == 60_00
        assert result.carry_forward_minor == 60_00
        assert result.status is BudgetStatus.ON_TRACK

    def test_spending_beyond_a_reduced_allowance_is_over_budget(self) -> None:
        result = evaluate_period(
            period=month_range(date(2026, 2, 1)),
            limit_minor=100_00,
            spent_minor=80_00,
            rollover_in_minor=-30_00,
            rollover_enabled=True,
        )

        assert result.effective_limit_minor == 70_00
        assert result.remaining_minor == -10_00
        assert result.status is BudgetStatus.OVER

    def test_zero_limit_with_spending_is_over(self) -> None:
        result = evaluate_period(
            period=month_range(date(2026, 2, 1)),
            limit_minor=0,
            spent_minor=1,
            rollover_in_minor=0,
            rollover_enabled=False,
        )

        assert result.status is BudgetStatus.OVER
        assert result.percent_used == Decimal("100.00")

    def test_zero_limit_with_no_spending_is_on_track(self) -> None:
        result = evaluate_period(
            period=month_range(date(2026, 2, 1)),
            limit_minor=0,
            spent_minor=0,
            rollover_in_minor=0,
            rollover_enabled=False,
        )

        assert result.status is BudgetStatus.ON_TRACK
        assert result.percent_used == Decimal("0.00")
