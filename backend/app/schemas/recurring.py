"""Recurring-rule request/response contracts."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.ledger import TransactionType
from app.domain.money import Currency, UnknownCurrencyError
from app.domain.recurring import RecurrenceError, RecurrenceFrequency, validate_schedule
from app.schemas.common import CurrencyCode, ORMModel


def _today() -> date:
    return datetime.now(UTC).date()


def _validate_currency(value: str) -> str:
    try:
        return Currency(value).code
    except UnknownCurrencyError as exc:
        raise ValueError(str(exc)) from exc


class RecurringRuleCreate(BaseModel):
    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    description: str = Field(default="", max_length=255)
    transaction_type: Literal[TransactionType.INCOME, TransactionType.EXPENSE]
    amount: Decimal = Field(gt=0, examples=["1200.00"])
    currency: CurrencyCode
    frequency: RecurrenceFrequency
    interval: int = Field(default=1, ge=1, le=365)
    day_of_month: int | None = Field(
        default=None,
        ge=1,
        le=31,
        description="Monthly/yearly anchor day; defaults to the start date's day.",
    )
    starts_on: date = Field(default_factory=_today)
    ends_on: date | None = None

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        return _validate_currency(value)

    @model_validator(mode="after")
    def _check_schedule(self) -> RecurringRuleCreate:
        try:
            validate_schedule(
                frequency=self.frequency,
                interval=self.interval,
                day_of_month=self.day_of_month,
                starts_on=self.starts_on,
                ends_on=self.ends_on,
            )
        except RecurrenceError as exc:
            raise ValueError(str(exc)) from exc
        return self


class RecurringRuleUpdate(BaseModel):
    """Only the amount, classification and lifecycle are mutable.

    Changing a rule's cadence mid-stream would make already-generated history
    ambiguous; create a new rule and archive the old one instead.
    """

    category_id: uuid.UUID | None = None
    description: str | None = Field(default=None, max_length=255)
    amount: Decimal | None = Field(default=None, gt=0)
    ends_on: date | None = None
    is_active: bool | None = None


class RecurringRuleResponse(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    category_id: uuid.UUID | None
    description: str
    transaction_type: TransactionType
    amount_minor: int
    currency: str
    frequency: RecurrenceFrequency
    interval: int
    day_of_month: int | None
    starts_on: date
    ends_on: date | None
    next_run_on: date
    last_run_on: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class RecurringRunResponse(BaseModel):
    rule_id: uuid.UUID
    generated_count: int
    skipped_count: int = Field(description="Occurrences already materialised.")
    last_occurrence_on: date | None
    next_run_on: date
