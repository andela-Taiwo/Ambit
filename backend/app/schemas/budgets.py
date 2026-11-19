"""Budget request/response contracts."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.domain.budgets import BudgetPeriodError, BudgetStatus, month_start, validate_budget_window
from app.domain.money import Currency, UnknownCurrencyError
from app.schemas.common import CurrencyCode, ORMModel


def current_month_start() -> date:
    return month_start(datetime.now(UTC).date())


def _validate_currency(value: str) -> str:
    try:
        return Currency(value).code
    except UnknownCurrencyError as exc:
        raise ValueError(str(exc)) from exc


def _validate_month_boundary(value: date, *, field: str) -> date:
    try:
        validate_budget_window(value, None)
    except BudgetPeriodError as exc:
        raise ValueError(f"{field} must be the first day of a month") from exc
    return value


class BudgetCreate(BaseModel):
    category_id: uuid.UUID
    amount: Decimal = Field(
        ge=0,
        examples=["500.00"],
        description="Monthly limit in major units; converted to minor units on write.",
    )
    currency: CurrencyCode
    starts_on: date = Field(
        default_factory=current_month_start,
        description="First day of the first month the budget applies to.",
    )
    ends_on: date | None = Field(
        default=None,
        description=(
            "First day of the month the budget stops applying to (exclusive). "
            "Null means the budget runs until archived."
        ),
    )
    rollover_enabled: bool = False

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        return _validate_currency(value)

    @field_validator("starts_on")
    @classmethod
    def _check_start(cls, value: date) -> date:
        return _validate_month_boundary(value, field="starts_on")

    @field_validator("ends_on")
    @classmethod
    def _check_end(cls, value: date | None) -> date | None:
        if value is None:
            return None
        return _validate_month_boundary(value, field="ends_on")

    @model_validator(mode="after")
    def _check_window(self) -> BudgetCreate:
        try:
            validate_budget_window(self.starts_on, self.ends_on)
        except BudgetPeriodError as exc:
            raise ValueError(str(exc)) from exc
        return self


class BudgetUpdate(BaseModel):
    """Partial update. `ends_on` may be set to null to make a budget open-ended."""

    amount: Decimal | None = Field(default=None, ge=0)
    ends_on: date | None = None
    rollover_enabled: bool | None = None
    is_archived: bool | None = None

    @field_validator("ends_on")
    @classmethod
    def _check_end(cls, value: date | None) -> date | None:
        if value is None:
            return None
        return _validate_month_boundary(value, field="ends_on")


class BudgetResponse(ORMModel):
    id: uuid.UUID
    category_id: uuid.UUID
    amount_minor: int
    currency: str
    starts_on: date
    ends_on: date | None
    rollover_enabled: bool
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class BudgetStatusResponse(BaseModel):
    """Budget vs actual for one month, including the rollover chain's effect."""

    budget_id: uuid.UUID
    category_id: uuid.UUID
    currency: str
    period_start: date
    period_end: date = Field(
        description="Exclusive start of the following month, so [start, end) is the period."
    )
    limit_minor: int
    rollover_in_minor: int
    effective_limit_minor: int
    spent_minor: int
    remaining_minor: int
    carry_forward_minor: int = Field(
        description="What rolls into the next month; zero when rollover is disabled."
    )
    percent_used: Decimal
    status: BudgetStatus
    transaction_count: int


class BudgetPortfolioStatus(BaseModel):
    """Every active budget's status for one month."""

    period_start: date
    period_end: date
    base_currency: str = Field(
        description="The caller's base currency, for display; each budget keeps its own."
    )
    items: list[BudgetStatusResponse]
