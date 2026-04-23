"""Recurring-rule schedule generation.

Schedules are pure date arithmetic so every edge case -- month ends, leap
years, multi-month intervals, end dates -- is testable without a database.
Generation is idempotent at the database level: a transaction is unique per
(rule, occurrence), so a retried job cannot double-charge a user.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from enum import StrEnum
from typing import Final

#: Safety valve for catch-up runs. A daily rule left unattended for years would
#: otherwise generate an unbounded batch in one request; the remainder is picked
#: up by the next run because `next_run_on` is only advanced past emitted rows.
MAX_OCCURRENCES_PER_RUN: Final = 500

MAX_INTERVAL: Final = 365


class RecurrenceError(ValueError):
    """The recurring schedule is not valid."""


class RecurrenceFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


def _clamp_day(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def validate_schedule(
    *,
    frequency: RecurrenceFrequency,
    interval: int,
    day_of_month: int | None,
    starts_on: date,
    ends_on: date | None,
) -> None:
    if interval < 1 or interval > MAX_INTERVAL:
        raise RecurrenceError(f"interval must be between 1 and {MAX_INTERVAL}")
    if ends_on is not None and ends_on < starts_on:
        raise RecurrenceError("ends_on cannot be before starts_on")
    if day_of_month is not None and not 1 <= day_of_month <= 31:
        raise RecurrenceError("day_of_month must be between 1 and 31")
    if frequency in (RecurrenceFrequency.DAILY, RecurrenceFrequency.WEEKLY) and day_of_month:
        raise RecurrenceError("day_of_month only applies to monthly or yearly rules")


def advance(
    occurrence: date,
    *,
    frequency: RecurrenceFrequency,
    interval: int,
    day_of_month: int | None = None,
    anchor_month: int | None = None,
) -> date:
    """Return the next occurrence after `occurrence`.

    Monthly and yearly rules anchor on the intended day (not on the clamped
    date), so a 31st-of-month rule lands on 28 February and then on 31 March
    rather than drifting permanently to the 28th.
    """
    if frequency is RecurrenceFrequency.DAILY:
        return occurrence + timedelta(days=interval)
    if frequency is RecurrenceFrequency.WEEKLY:
        return occurrence + timedelta(weeks=interval)

    if frequency is RecurrenceFrequency.MONTHLY:
        index = occurrence.year * 12 + (occurrence.month - 1) + interval
        year, month_index = divmod(index, 12)
        return _clamp_day(year, month_index + 1, day_of_month or occurrence.day)

    target_year = occurrence.year + interval
    month = anchor_month or occurrence.month
    day = day_of_month or occurrence.day
    return _clamp_day(target_year, month, day)


def due_occurrences(
    *,
    next_run_on: date,
    frequency: RecurrenceFrequency,
    interval: int,
    day_of_month: int | None,
    anchor_month: int | None,
    as_of: date,
    ends_on: date | None = None,
    limit: int = MAX_OCCURRENCES_PER_RUN,
) -> list[date]:
    """Occurrences from `next_run_on` through `as_of`, bounded by `limit`."""
    results: list[date] = []
    occurrence = next_run_on

    while occurrence <= as_of and len(results) < limit:
        if ends_on is not None and occurrence > ends_on:
            break
        results.append(occurrence)
        occurrence = advance(
            occurrence,
            frequency=frequency,
            interval=interval,
            day_of_month=day_of_month,
            anchor_month=anchor_month,
        )

    return results
