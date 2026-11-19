"""Reporting contracts: net worth, cash flow and category breakdown."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.accounts import AccountType
from app.domain.categories import CategoryKind
from app.domain.investments import InvestmentType
from app.schemas.fx import DecimalString
from app.schemas.investments import ValueSource


class ConvertedAmount(BaseModel):
    """A native amount plus its base-currency equivalent and the rate used.

    Returning the rate on every component makes a net-worth figure auditable:
    the user can see exactly which observation converted each holding.
    """

    currency: str
    amount_minor: int
    base_currency: str
    base_minor: int
    rate: DecimalString
    rate_as_of: date
    rate_source: str
    rate_is_inverse: bool


class NetWorthAccount(BaseModel):
    account_id: uuid.UUID
    name: str
    account_type: AccountType
    balance: ConvertedAmount


class NetWorthInvestment(BaseModel):
    investment_id: uuid.UUID
    name: str
    investment_type: InvestmentType
    value: ConvertedAmount
    value_source: ValueSource
    valuation_as_of: date | None


class NetWorthResponse(BaseModel):
    as_of: date
    base_currency: str
    total_minor: int
    accounts_total_minor: int
    investments_total_minor: int
    accounts: list[NetWorthAccount]
    investments: list[NetWorthInvestment]


class NetWorthHistoryPoint(BaseModel):
    as_of: date
    total_minor: int
    accounts_minor: int
    investments_minor: int


class NetWorthHistoryResponse(BaseModel):
    base_currency: str
    points: list[NetWorthHistoryPoint]


class CashFlowItem(BaseModel):
    period_start: date
    period_end: date = Field(description="Exclusive start of the following month.")
    income_minor: int
    expense_minor: int = Field(description="Positive magnitude of money out.")
    net_minor: int
    transaction_count: int


class CashFlowResponse(BaseModel):
    base_currency: str
    date_from: date
    date_to: date
    interval: Literal["month"] = "month"
    items: list[CashFlowItem]


class CategoryBreakdownItem(BaseModel):
    category_id: uuid.UUID | None
    name: str
    parent_id: uuid.UUID | None
    total_minor: int
    transaction_count: int
    percent_of_total: Decimal


class CategoryBreakdownResponse(BaseModel):
    base_currency: str
    date_from: date
    date_to: date
    kind: CategoryKind
    include_subcategories: bool
    total_minor: int
    items: list[CategoryBreakdownItem]
