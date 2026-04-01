"""Exchange-rate and conversion math."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.fx import (
    InvalidRateError,
    MissingRateError,
    RateBook,
    RateObservation,
    convert_minor_units,
    invert_rate,
    validate_rate,
)

AS_OF = datetime(2026, 1, 31, 12, tzinfo=UTC)


class TestValidateRate:
    @pytest.mark.parametrize(
        "rate", [Decimal("0"), Decimal("-1"), Decimal("NaN"), Decimal("Infinity")]
    )
    def test_rejects_unusable_rates(self, rate: Decimal) -> None:
        with pytest.raises(InvalidRateError):
            validate_rate(rate)

    def test_accepts_a_positive_rate(self) -> None:
        assert validate_rate(Decimal("0.79")) == Decimal("0.79")


class TestInvertRate:
    def test_inverts_at_working_precision(self) -> None:
        inverse = invert_rate(Decimal("1.25"))

        assert inverse == Decimal(1) / Decimal("1.25")

    def test_rejects_zero(self) -> None:
        with pytest.raises(InvalidRateError):
            invert_rate(Decimal("0"))


class TestConvertMinorUnits:
    def test_same_currency_is_a_passthrough(self) -> None:
        assert (
            convert_minor_units(
                123_456,
                from_currency="GBP",
                to_currency="GBP",
                rate=Decimal("999"),
            )
            == 123_456
        )

    def test_converts_gbp_to_usd(self) -> None:
        """100.00 GBP at 1.25 USD/GBP = 125.00 USD."""
        assert (
            convert_minor_units(
                10_000,
                from_currency="GBP",
                to_currency="USD",
                rate=Decimal("1.25"),
            )
            == 12_500
        )

    def test_converts_naira_to_pounds(self) -> None:
        """10,000.00 NGN at 0.00052 GBP/NGN = 5.20 GBP."""
        assert (
            convert_minor_units(
                1_000_000,
                from_currency="NGN",
                to_currency="GBP",
                rate=Decimal("0.00052"),
            )
            == 520
        )

    def test_rounds_once_half_even(self) -> None:
        """0.005 GBP is half a penny: banker's rounding takes it to zero."""
        assert (
            convert_minor_units(
                1,
                from_currency="JPY",
                to_currency="GBP",
                rate=Decimal("0.005"),
            )
            == 0
        )

    def test_rounds_up_when_above_half(self) -> None:
        assert (
            convert_minor_units(
                1,
                from_currency="JPY",
                to_currency="GBP",
                rate=Decimal("0.0051"),
            )
            == 1
        )

    def test_respects_three_decimal_currencies(self) -> None:
        """1.000 KWD (1000 fils) at 2.55 GBP/KWD = 2.550 GBP."""
        assert (
            convert_minor_units(
                1_000,
                from_currency="KWD",
                to_currency="GBP",
                rate=Decimal("2.55"),
            )
            == 255
        )

    def test_rejects_a_non_positive_rate(self) -> None:
        with pytest.raises(InvalidRateError):
            convert_minor_units(
                100,
                from_currency="GBP",
                to_currency="USD",
                rate=Decimal("0"),
            )


def _obs(
    base: str,
    quote: str,
    rate: str,
    as_of: datetime,
    source: str = "test",
) -> RateObservation:
    return RateObservation(
        base_currency=base,
        quote_currency=quote,
        rate=Decimal(rate),
        as_of=as_of,
        source=source,
    )


class TestRateBook:
    def test_resolves_the_latest_rate_at_or_before_the_instant(self) -> None:
        book = RateBook(
            global_observations=[
                _obs("GBP", "USD", "1.20", AS_OF - timedelta(days=10)),
                _obs("GBP", "USD", "1.25", AS_OF - timedelta(days=1)),
                _obs("GBP", "USD", "1.30", AS_OF + timedelta(days=1)),
            ]
        )

        resolved = book.resolve("GBP", "USD", AS_OF)

        assert resolved.rate == Decimal("1.25")
        assert resolved.as_of == AS_OF - timedelta(days=1)
        assert resolved.is_inverse is False

    def test_uses_the_inverse_when_only_the_opposite_pair_exists(self) -> None:
        book = RateBook(global_observations=[_obs("USD", "GBP", "0.80", AS_OF)])

        resolved = book.resolve("GBP", "USD", AS_OF)

        assert resolved.rate == Decimal(1) / Decimal("0.80")
        assert resolved.is_inverse is True

    def test_user_rates_take_precedence_over_shared_rates(self) -> None:
        book = RateBook(
            user_observations=[_obs("GBP", "USD", "1.10", AS_OF - timedelta(days=5), "manual")],
            global_observations=[_obs("GBP", "USD", "1.30", AS_OF - timedelta(days=1))],
        )

        assert book.resolve("GBP", "USD", AS_OF).rate == Decimal("1.10")

    def test_same_currency_is_an_identity_rate(self) -> None:
        resolved = RateBook().resolve("GBP", "GBP", AS_OF)

        assert resolved.rate == Decimal(1)
        assert resolved.source == "identity"

    def test_missing_rate_raises_instead_of_guessing(self) -> None:
        with pytest.raises(MissingRateError):
            RateBook().resolve("GBP", "USD", AS_OF)

    def test_a_rate_after_the_instant_is_not_used(self) -> None:
        book = RateBook(global_observations=[_obs("GBP", "USD", "1.25", AS_OF + timedelta(days=1))])

        with pytest.raises(MissingRateError):
            book.resolve("GBP", "USD", AS_OF)
