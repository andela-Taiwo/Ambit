"""Full-data export.

The export deliberately contains only the caller's own rows: no refresh-token
hashes, no other users' data, and no shared provider rates. It is the
"take your data with you" path from plan Phase 6.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Account,
    AuditLog,
    Budget,
    Category,
    ExchangeRate,
    Investment,
    InvestmentValuation,
    RecurringRule,
    Transaction,
    User,
)
from app.schemas.accounts import AccountResponse
from app.schemas.auth import UserResponse
from app.schemas.budgets import BudgetResponse
from app.schemas.categories import CategoryResponse
from app.schemas.fx import ExchangeRateResponse
from app.schemas.imports import AuditLogResponse, FullExportResponse
from app.schemas.investments import InvestmentResponse, ValuationResponse
from app.schemas.recurring import RecurringRuleResponse
from app.schemas.transactions import TransactionResponse


async def build_export(session: AsyncSession, user: User) -> FullExportResponse:
    accounts = list(
        await session.scalars(
            select(Account).where(Account.user_id == user.id).order_by(Account.name)
        )
    )
    categories = list(
        await session.scalars(
            select(Category).where(Category.user_id == user.id).order_by(Category.name)
        )
    )
    transactions = list(
        await session.scalars(
            select(Transaction)
            .where(Transaction.user_id == user.id)
            .order_by(Transaction.occurred_on, Transaction.created_at)
        )
    )
    budgets = list(
        await session.scalars(
            select(Budget)
            .where(Budget.user_id == user.id)
            .order_by(Budget.starts_on, Budget.created_at)
        )
    )
    investments = list(
        await session.scalars(
            select(Investment).where(Investment.user_id == user.id).order_by(Investment.name)
        )
    )
    valuations = list(
        await session.scalars(
            select(InvestmentValuation)
            .where(InvestmentValuation.user_id == user.id)
            .order_by(InvestmentValuation.as_of)
        )
    )
    recurring_rules = list(
        await session.scalars(
            select(RecurringRule)
            .where(RecurringRule.user_id == user.id)
            .order_by(RecurringRule.created_at)
        )
    )
    exchange_rates = list(
        await session.scalars(
            select(ExchangeRate).where(ExchangeRate.user_id == user.id).order_by(ExchangeRate.as_of)
        )
    )
    audit_logs = list(
        await session.scalars(
            select(AuditLog).where(AuditLog.user_id == user.id).order_by(AuditLog.occurred_at)
        )
    )

    return FullExportResponse(
        exported_at=datetime.now(UTC),
        user=UserResponse.model_validate(user),
        accounts=[AccountResponse.model_validate(row) for row in accounts],
        categories=[CategoryResponse.model_validate(row) for row in categories],
        transactions=[TransactionResponse.model_validate(row) for row in transactions],
        budgets=[BudgetResponse.model_validate(row) for row in budgets],
        investments=[InvestmentResponse.model_validate(row) for row in investments],
        investment_valuations=[ValuationResponse.model_validate(row) for row in valuations],
        recurring_rules=[RecurringRuleResponse.model_validate(row) for row in recurring_rules],
        exchange_rates=[ExchangeRateResponse.model_validate(row) for row in exchange_rates],
        audit_logs=[AuditLogResponse.model_validate(row) for row in audit_logs],
    )
