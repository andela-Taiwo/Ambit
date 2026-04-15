"""Investment request/response contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, PlainSerializer, field_validator, model_validator

from app.domain.investments import Compounding, InvestmentType, RatePeriod
from app.domain.money import Currency, UnknownCurrencyError
from app.schemas.common import CurrencyCode, ORMModel
from app.schemas.fx import DecimalString

InvestmentName = Annotated[str, Field(min_length=1, max_length=120)]


def _validate_currency(value: str) -> str:
    try:
        return Currency(value).code
    except UnknownCurrencyError as exc:
        raise ValueError(str(exc)) from exc


def _format_percent(value: Decimal) -> str:
    return format(value, ".2f")


PercentString = Annotated[
    Decimal, PlainSerializer(_format_percent, return_type=str, when_used="json")
]

ValueSource = Literal["valuation", "accrual", "principal"]


class InvestmentCreate(BaseModel):
    account_id: uuid.UUID
    name: InvestmentName
    investment_type: InvestmentType
    principal: Decimal = Field(ge=0, examples=["10000000.00"])
    currency: CurrencyCode
    rate: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=9,
        decimal_places=6,
        description="Stated rate as a percentage, e.g. 24 for 24%.",
    )
    rate_period: RatePeriod | None = None
    compounding: Compounding = Compounding.SIMPLE
    start_date: date
    maturity_date: date | None = None
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str) -> str:
        return _validate_currency(value)

    @model_validator(mode="after")
    def _check_instrument(self) -> InvestmentCreate:
        if self.maturity_date is not None and self.maturity_date < self.start_date:
            raise ValueError("maturity_date cannot be before start_date")

        if self.investment_type is InvestmentType.FIXED_RATE:
            if self.rate is None or self.rate_period is None:
                raise ValueError("A fixed-rate investment requires rate and rate_period")
        elif self.rate is not None or self.rate_period is not None:
            raise ValueError("A market-priced investment must not set rate or rate_period")
        return self


class InvestmentUpdate(BaseModel):
    """Only mutable terms. Type, account, currency and start date are fixed.

    Changing them after valuations exist would silently reinterpret history.
    """

    name: InvestmentName | None = None
    principal: Decimal | None = Field(default=None, ge=0)
    rate: Decimal | None = Field(default=None, gt=0, max_digits=9, decimal_places=6)
    rate_period: RatePeriod | None = None
    compounding: Compounding | None = None
    maturity_date: date | None = None
    notes: str | None = None
    is_archived: bool | None = None

    @model_validator(mode="after")
    def _check_rate_pair(self) -> InvestmentUpdate:
        if (self.rate is None) != (self.rate_period is None):
            raise ValueError("rate and rate_period must be provided together")
        return self


class InvestmentResponse(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    name: str
    investment_type: InvestmentType
    principal_minor: int
    currency: str
    rate: DecimalString | None
    rate_period: RatePeriod | None
    compounding: Compounding
    start_date: date
    maturity_date: date | None
    notes: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class InvestmentReturnsResponse(BaseModel):
    """Current value and return, with the basis for the value made explicit."""

    investment_id: uuid.UUID
    name: str
    currency: str
    as_of: date
    principal_minor: int
    value_minor: int
    value_source: ValueSource
    valuation_as_of: date | None = Field(
        description="Date of the valuation used; null when derived from accrual or principal."
    )
    accrued_interest_minor: int
    gain_minor: int
    gain_percent: PercentString
    projected_monthly_interest_minor: int | None
    projected_annual_interest_minor: int | None
    start_date: date
    maturity_date: date | None


class ValuationCreate(BaseModel):
    as_of: date
    value: Decimal = Field(ge=0, examples=["10500000.00"])
    notes: str | None = None


class ValuationResponse(ORMModel):
    id: uuid.UUID
    investment_id: uuid.UUID
    as_of: date
    value_minor: int
    source: str
    notes: str | None
    created_at: datetime
