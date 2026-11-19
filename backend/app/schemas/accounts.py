"""Account request/response contracts."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

from app.domain.accounts import AccountType
from app.domain.money import Currency, UnknownCurrencyError
from app.schemas.common import CurrencyCode, ORMModel

AccountName = Annotated[str, Field(min_length=1, max_length=120)]


class AccountCreate(BaseModel):
    name: AccountName
    account_type: AccountType
    currency: CurrencyCode
    opening_balance: Decimal = Field(default=Decimal("0"), examples=["1500.00"])

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        try:
            return Currency(value).code
        except UnknownCurrencyError as exc:
            raise ValueError(str(exc)) from exc


class AccountUpdate(BaseModel):
    """All fields optional; currency is immutable once transactions exist."""

    name: AccountName | None = None
    account_type: AccountType | None = None
    is_archived: bool | None = None


class AccountResponse(ORMModel):
    id: uuid.UUID
    name: str
    account_type: AccountType
    currency: str
    opening_balance_minor: int
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class AccountBalanceResponse(BaseModel):
    """Current balance, derived from the opening balance plus all activity."""

    account_id: uuid.UUID
    currency: str
    balance_minor: int
    balance: str = Field(description="Decimal string, e.g. '1234.56'.")
