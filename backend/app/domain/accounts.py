"""Account domain types."""

from __future__ import annotations

from enum import StrEnum


class AccountType(StrEnum):
    CASH = "cash"
    CURRENT = "current"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    INVESTMENT = "investment"


def is_investment_account(account_type: AccountType) -> bool:
    """Investment accounts hold the instruments introduced in Phase 4."""
    return account_type is AccountType.INVESTMENT
