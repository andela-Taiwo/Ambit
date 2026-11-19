"""CSV amount parsing and income/expense classification."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.imports import AmountSignConvention, ImportParseError, classify, parse_amount
from app.domain.ledger import TransactionType


class TestParseAmount:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("10.50", Decimal("10.50")),
            ("-10.50", Decimal("-10.50")),
            ("£1,234.56", Decimal("1234.56")),
            ("€ 99.99", Decimal("99.99")),
            ("₦2,000,000.00", Decimal("2000000.00")),
            ("(50.00)", Decimal("-50.00")),
            ("100-", Decimal("-100")),
            ("+12.30", Decimal("12.30")),
            (" 7 ", Decimal("7")),
        ],
    )
    def test_parses_common_statement_formats(self, raw: str, expected: Decimal) -> None:
        assert parse_amount(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "abc", "1.2.3", "NaN", "Infinity", "0", "0.00"])
    def test_rejects_unusable_values(self, raw: str) -> None:
        with pytest.raises(ImportParseError):
            parse_amount(raw)


class TestClassify:
    def test_negative_is_expense_by_default(self) -> None:
        assert (
            classify(
                Decimal("-10"), type_value=None, convention=AmountSignConvention.NEGATIVE_IS_EXPENSE
            )
            is TransactionType.EXPENSE
        )

    def test_positive_is_income_by_default(self) -> None:
        assert (
            classify(
                Decimal("10"), type_value=None, convention=AmountSignConvention.NEGATIVE_IS_EXPENSE
            )
            is TransactionType.INCOME
        )

    def test_positive_can_be_expense_when_the_bank_uses_debit_columns(self) -> None:
        assert (
            classify(
                Decimal("10"), type_value=None, convention=AmountSignConvention.POSITIVE_IS_EXPENSE
            )
            is TransactionType.EXPENSE
        )

    def test_explicit_type_wins_over_the_sign(self) -> None:
        assert (
            classify(
                Decimal("10"),
                type_value="expense",
                convention=AmountSignConvention.NEGATIVE_IS_EXPENSE,
            )
            is TransactionType.EXPENSE
        )

    def test_rejects_an_unsupported_type(self) -> None:
        with pytest.raises(ImportParseError):
            classify(
                Decimal("10"),
                type_value="transfer",
                convention=AmountSignConvention.NEGATIVE_IS_EXPENSE,
            )
