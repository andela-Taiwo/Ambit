"""Recurring schedule arithmetic, including month-end and leap-year cases."""

from __future__ import annotations

from datetime import date

import pytest

from app.domain.recurring import (
    MAX_OCCURRENCES_PER_RUN,
    RecurrenceError,
    RecurrenceFrequency,
    advance,
    due_occurrences,
    validate_schedule,
)


class TestAdvance:
    def test_daily(self) -> None:
        assert advance(date(2026, 1, 1), frequency=RecurrenceFrequency.DAILY, interval=2) == date(
            2026, 1, 3
        )

    def test_weekly(self) -> None:
        assert advance(date(2026, 1, 1), frequency=RecurrenceFrequency.WEEKLY, interval=2) == date(
            2026, 1, 15
        )

    def test_monthly_clamps_then_returns_to_the_anchor_day(self) -> None:
        """31 Jan -> 28 Feb -> 31 Mar, not a permanent drift to the 28th."""
        february = advance(
            date(2026, 1, 31),
            frequency=RecurrenceFrequency.MONTHLY,
            interval=1,
            day_of_month=31,
        )
        march = advance(
            february,
            frequency=RecurrenceFrequency.MONTHLY,
            interval=1,
            day_of_month=31,
        )

        assert february == date(2026, 2, 28)
        assert march == date(2026, 3, 31)

    def test_monthly_interval_skips_months(self) -> None:
        assert advance(
            date(2026, 1, 15),
            frequency=RecurrenceFrequency.MONTHLY,
            interval=3,
            day_of_month=15,
        ) == date(2026, 4, 15)

    def test_monthly_crosses_a_year(self) -> None:
        assert advance(
            date(2026, 12, 10),
            frequency=RecurrenceFrequency.MONTHLY,
            interval=1,
            day_of_month=10,
        ) == date(2027, 1, 10)

    def test_yearly_keeps_the_leap_day_anchor(self) -> None:
        """29 Feb 2024 -> 28 Feb 2025 -> 28 Feb 2026 -> 29 Feb 2028."""
        first = advance(
            date(2024, 2, 29),
            frequency=RecurrenceFrequency.YEARLY,
            interval=1,
            day_of_month=29,
            anchor_month=2,
        )
        second = advance(
            first,
            frequency=RecurrenceFrequency.YEARLY,
            interval=1,
            day_of_month=29,
            anchor_month=2,
        )
        leap_again = advance(
            second,
            frequency=RecurrenceFrequency.YEARLY,
            interval=2,
            day_of_month=29,
            anchor_month=2,
        )

        assert first == date(2025, 2, 28)
        assert second == date(2026, 2, 28)
        assert leap_again == date(2028, 2, 29)


class TestValidateSchedule:
    @pytest.mark.parametrize("interval", [0, -1, 366])
    def test_rejects_an_out_of_range_interval(self, interval: int) -> None:
        with pytest.raises(RecurrenceError):
            validate_schedule(
                frequency=RecurrenceFrequency.DAILY,
                interval=interval,
                day_of_month=None,
                starts_on=date(2026, 1, 1),
                ends_on=None,
            )

    def test_rejects_an_end_before_the_start(self) -> None:
        with pytest.raises(RecurrenceError):
            validate_schedule(
                frequency=RecurrenceFrequency.MONTHLY,
                interval=1,
                day_of_month=1,
                starts_on=date(2026, 2, 1),
                ends_on=date(2026, 1, 1),
            )

    @pytest.mark.parametrize("day", [0, 32])
    def test_rejects_an_invalid_day_of_month(self, day: int) -> None:
        with pytest.raises(RecurrenceError):
            validate_schedule(
                frequency=RecurrenceFrequency.MONTHLY,
                interval=1,
                day_of_month=day,
                starts_on=date(2026, 1, 1),
                ends_on=None,
            )

    def test_rejects_day_of_month_for_weekly_rules(self) -> None:
        with pytest.raises(RecurrenceError):
            validate_schedule(
                frequency=RecurrenceFrequency.WEEKLY,
                interval=1,
                day_of_month=15,
                starts_on=date(2026, 1, 1),
                ends_on=None,
            )


class TestDueOccurrences:
    def test_generates_up_to_the_as_of_date_inclusive(self) -> None:
        occurrences = due_occurrences(
            next_run_on=date(2026, 1, 1),
            frequency=RecurrenceFrequency.MONTHLY,
            interval=1,
            day_of_month=1,
            anchor_month=None,
            as_of=date(2026, 3, 1),
        )

        assert occurrences == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]

    def test_stops_at_the_end_date(self) -> None:
        occurrences = due_occurrences(
            next_run_on=date(2026, 1, 1),
            frequency=RecurrenceFrequency.MONTHLY,
            interval=1,
            day_of_month=1,
            anchor_month=None,
            as_of=date(2026, 12, 31),
            ends_on=date(2026, 3, 1),
        )

        assert occurrences == [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]

    def test_nothing_when_the_next_run_is_in_the_future(self) -> None:
        assert (
            due_occurrences(
                next_run_on=date(2026, 2, 1),
                frequency=RecurrenceFrequency.MONTHLY,
                interval=1,
                day_of_month=1,
                anchor_month=None,
                as_of=date(2026, 1, 31),
            )
            == []
        )

    def test_caps_a_long_catch_up(self) -> None:
        occurrences = due_occurrences(
            next_run_on=date(2020, 1, 1),
            frequency=RecurrenceFrequency.DAILY,
            interval=1,
            day_of_month=None,
            anchor_month=None,
            as_of=date(2026, 1, 1),
        )

        assert len(occurrences) == MAX_OCCURRENCES_PER_RUN
        assert occurrences[0] == date(2020, 1, 1)
