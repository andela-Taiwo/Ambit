"""Account domain rules."""

from __future__ import annotations

import pytest
from app.domain.accounts import AccountType, is_investment_account


class TestAccountType:
    @pytest.mark.parametrize("value", ["cash", "current", "savings", "credit_card", "investment"])
    def test_supported_account_types(self, value: str) -> None:
        assert AccountType(value).value == value

    def test_unknown_account_type_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="not a valid AccountType"):
            AccountType("crypto_wallet")


class TestIsInvestmentAccount:
    def test_investment_accounts_are_identified(self) -> None:
        """Phase 4 hangs holdings off these accounts."""
        assert is_investment_account(AccountType.INVESTMENT) is True

    @pytest.mark.parametrize(
        "account_type",
        [AccountType.CASH, AccountType.CURRENT, AccountType.SAVINGS, AccountType.CREDIT_CARD],
    )
    def test_other_accounts_are_not_investment_accounts(self, account_type: AccountType) -> None:
        assert is_investment_account(account_type) is False
