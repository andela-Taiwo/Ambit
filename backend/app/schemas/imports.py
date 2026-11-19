"""CSV import contracts and the full-data export envelope."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.imports import AmountSignConvention
from app.domain.money import Currency, UnknownCurrencyError
from app.schemas.accounts import AccountResponse
from app.schemas.auth import UserResponse
from app.schemas.budgets import BudgetResponse
from app.schemas.categories import CategoryResponse
from app.schemas.common import CurrencyCode, ORMModel
from app.schemas.fx import ExchangeRateResponse
from app.schemas.investments import InvestmentResponse, ValuationResponse
from app.schemas.recurring import RecurringRuleResponse
from app.schemas.transactions import TransactionResponse


class CsvColumnMapping(BaseModel):
    """Which CSV header supplies each field."""

    date: str = "date"
    amount: str = "amount"
    description: str | None = None
    category: str | None = None
    type: str | None = None
    external_id: str | None = None


class CsvImportRequest(BaseModel):
    account_id: uuid.UUID
    csv: str = Field(min_length=1, max_length=10_000_000)
    mapping: CsvColumnMapping = Field(default_factory=CsvColumnMapping)
    date_format: str = "%Y-%m-%d"
    currency: CurrencyCode | None = Field(
        default=None, description="Defaults to the destination account's currency."
    )
    default_category_id: uuid.UUID | None = None
    default_description: str = Field(default="Imported transaction", max_length=255)
    amount_sign: AmountSignConvention = AmountSignConvention.NEGATIVE_IS_EXPENSE
    dry_run: bool = False

    @field_validator("currency")
    @classmethod
    def _check_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            return Currency(value).code
        except UnknownCurrencyError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("date_format")
    @classmethod
    def _check_date_format(cls, value: str) -> str:
        try:
            sample = datetime(2000, 1, 1)
            datetime.strptime(sample.strftime(value), value)
        except ValueError as exc:
            raise ValueError(f"Invalid date_format {value!r}") from exc
        return value


class CsvImportRowError(BaseModel):
    row: int = Field(description="1-based line number in the source CSV.")
    message: str


class CsvImportResult(BaseModel):
    imported_count: int
    skipped_count: int
    error_count: int = 0
    errors: list[CsvImportRowError] = Field(default_factory=list)
    batch_id: uuid.UUID | None = Field(
        default=None, description="Null for a dry run or a rejected import."
    )
    dry_run: bool


class CsvImportErrorResponse(BaseModel):
    detail: str
    error_count: int
    errors: list[CsvImportRowError]


class AuditLogResponse(ORMModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID | None
    action: str
    request_id: str | None
    occurred_at: datetime


class FullExportResponse(BaseModel):
    """The user's complete data set in one JSON document."""

    exported_at: datetime
    schema_version: Literal[1] = 1
    user: UserResponse
    accounts: list[AccountResponse]
    categories: list[CategoryResponse]
    transactions: list[TransactionResponse]
    budgets: list[BudgetResponse]
    investments: list[InvestmentResponse]
    investment_valuations: list[ValuationResponse]
    recurring_rules: list[RecurringRuleResponse]
    exchange_rates: list[ExchangeRateResponse]
    audit_logs: list[AuditLogResponse]
