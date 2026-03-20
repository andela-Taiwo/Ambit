"""Money is stored as integer minor units -- never floats (plan Section 9).

These are worked-example tests: every expectation is a number a human can
verify by hand, per plan Section 14's mitigation for financial-math bugs.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.domain.money import (
    Currency,
    InvalidAmountError,
    UnknownCurrencyError,
    format_minor_units,
    to_minor_units,
)


class TestCurrency:
    def test_gbp_has_two_decimal_places(self) -> None:
        assert Currency("GBP").exponent == 2

    def test_ngn_has_two_decimal_places(self) -> None:
        assert Currency("NGN").exponent == 2

    def test_jpy_has_no_minor_unit(self) -> None:
        """Zero-decimal currencies are the classic source of x100 bugs."""
        assert Currency("JPY").exponent == 0

    def test_currency_code_is_normalised_to_uppercase(self) -> None:
        assert Currency("gbp").code == "GBP"

    def test_unknown_currency_is_rejected(self) -> None:
        with pytest.raises(UnknownCurrencyError):
            Currency("XYZ")


class TestToMinorUnits:
    @pytest.mark.parametrize(
        ("amount", "currency", "expected"),
        [
            ("10.00", "GBP", 1_000),
            ("0.01", "GBP", 1),
            ("1234.56", "GBP", 123_456),
            # The plan's worked example: 10 million Naira.
            ("10000000.00", "NGN", 1_000_000_000),
            # Zero-decimal currency: 1000 yen is 1000 minor units, not 100000.
            ("1000", "JPY", 1_000),
            ("0", "GBP", 0),
            ("-45.50", "GBP", -4_550),
        ],
    )
    def test_converts_decimal_to_minor_units(
        self, amount: str, currency: str, expected: int
    ) -> None:
        assert to_minor_units(Decimal(amount), Currency(currency)) == expected

    def test_rejects_more_precision_than_the_currency_allows(self) -> None:
        """0.005 GBP is not representable; silently rounding it would lose money."""
        with pytest.raises(InvalidAmountError):
            to_minor_units(Decimal("0.005"), Currency("GBP"))

    def test_rejects_fractional_yen(self) -> None:
        with pytest.raises(InvalidAmountError):
            to_minor_units(Decimal("100.5"), Currency("JPY"))

    def test_accepts_trailing_zeros_within_precision(self) -> None:
        assert to_minor_units(Decimal("10.10"), Currency("GBP")) == 1_010


class TestFormatMinorUnits:
    @pytest.mark.parametrize(
        ("minor", "currency", "expected"),
        [
            (1_000, "GBP", "10.00"),
            (1, "GBP", "0.01"),
            (0, "GBP", "0.00"),
            (-4_550, "GBP", "-45.50"),
            (1_000_000_000, "NGN", "10000000.00"),
            (1_000, "JPY", "1000"),
        ],
    )
    def test_formats_minor_units_as_decimal_string(
        self, minor: int, currency: str, expected: str
    ) -> None:
        assert format_minor_units(minor, Currency(currency)) == expected

    def test_round_trips_through_minor_units(self) -> None:
        original = Decimal("8675.309")
        currency = Currency("BHD")  # three decimal places
        assert format_minor_units(to_minor_units(original, currency), currency) == "8675.309"
