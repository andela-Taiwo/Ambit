"""Transaction request/response contracts."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from app.domain.ledger import TransactionType
from app.domain.money import Currency, UnknownCurrencyError
from app.schemas.common import CurrencyCode, ORMModel

Description = Annotated[str, Field(max_length=255)]


class TransactionCreate(BaseModel):
    """Create an income or expense entry.

    Transfers use the dedicated `/transactions/transfers` endpoint, since they
    produce two linked rows rather than one.
    """

    account_id: uuid.UUID
    category_id: uuid.UUID | None = None
    transaction_type: Literal[TransactionType.INCOME, TransactionType.EXPENSE]
    amount: Decimal = Field(gt=0, examples=["24.99"])
    currency: CurrencyCode
    occurred_on: date
    description: Description = ""
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        try:
            return Currency(value).code
        except UnknownCurrencyError as exc:
            raise ValueError(str(exc)) from exc


class TransactionUpdate(BaseModel):
    """Transfer legs are not editable through this endpoint."""

    category_id: uuid.UUID | None = None
    amount: Decimal | None = Field(default=None, gt=0)
    occurred_on: date | None = None
    description: Description | None = None
    notes: str | None = None


class TransferCreate(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: Decimal = Field(gt=0, examples=["500.00"])
    currency: CurrencyCode
    occurred_on: date
    description: Description = ""
    notes: str | None = None

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        try:
            return Currency(value).code
        except UnknownCurrencyError as exc:
            raise ValueError(str(exc)) from exc


class TransactionResponse(ORMModel):
    id: uuid.UUID
    account_id: uuid.UUID
    category_id: uuid.UUID | None
    transaction_type: TransactionType
    amount_minor: int = Field(description="Positive magnitude in minor units.")
    signed_amount_minor: int = Field(
        description=(
            "Amount with direction applied: negative debits the account, "
            "positive credits it. This is what balances sum."
        )
    )
    currency: str
    occurred_on: date
    description: str
    notes: str | None
    transfer_group_id: uuid.UUID | None
    recurring_rule_id: uuid.UUID | None = None
    occurrence_on: date | None = None
    created_at: datetime
    updated_at: datetime


class TransferResponse(BaseModel):
    """Both legs of a transfer, sharing one group id."""

    transfer_group_id: uuid.UUID
    legs: list[TransactionResponse]
