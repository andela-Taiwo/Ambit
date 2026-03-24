"""Money handling.

Amounts are stored and passed around as **integer minor units** (pence, kobo,
cents) together with a currency. Floats are never used for money: binary
floating point cannot represent 0.10 exactly, and rounding drift in a ledger is
unacceptable (plan Section 9).

Conversion at the boundary goes through `Decimal`, and any amount with more
precision than the currency allows is rejected rather than silently rounded --
losing a fraction of a unit without telling anyone is a correctness bug, not a
display concern.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, Inexact, InvalidOperation, localcontext


class MoneyError(Exception):
    """Base class for money-related domain errors."""


class UnknownCurrencyError(MoneyError):
    """The currency code is not one this application supports."""


class InvalidAmountError(MoneyError):
    """The amount cannot be represented exactly in the given currency."""


# ISO 4217 minor-unit exponents for the currencies this app supports.
# Most currencies use 2; the exceptions are what make a lookup necessary.
_CURRENCY_EXPONENTS: dict[str, int] = {
    "GBP": 2,
    "USD": 2,
    "EUR": 2,
    "NGN": 2,
    "CAD": 2,
    "AUD": 2,
    "CHF": 2,
    "ZAR": 2,
    "GHS": 2,
    "KES": 2,
    # Zero-decimal currencies.
    "JPY": 0,
    "KRW": 0,
    "XOF": 0,
    "XAF": 0,
    # Three-decimal currencies.
    "BHD": 3,
    "KWD": 3,
    "TND": 3,
    "OMR": 3,
}

SUPPORTED_CURRENCIES: frozenset[str] = frozenset(_CURRENCY_EXPONENTS)

#: Guard against decimal amounts that would overflow the BigInteger columns.
#: Ten trillion major units is far beyond personal finance and keeps every
#: stored value inside a 64-bit integer with room to spare.
MAX_MINOR_UNITS = 10**15


@dataclass(frozen=True, slots=True)
class Currency:
    """An ISO 4217 currency code with its minor-unit exponent."""

    code: str

    def __init__(self, code: str) -> None:
        normalised = code.strip().upper()
        if normalised not in _CURRENCY_EXPONENTS:
            raise UnknownCurrencyError(f"Unsupported currency code: {code!r}")
        object.__setattr__(self, "code", normalised)

    @property
    def exponent(self) -> int:
        """Number of decimal places this currency subdivides into."""
        return _CURRENCY_EXPONENTS[self.code]

    def __str__(self) -> str:
        return self.code


def to_minor_units(amount: Decimal, currency: Currency) -> int:
    """Convert a decimal amount to integer minor units.

    Raises `InvalidAmountError` if `amount` carries more precision than the
    currency can represent, rather than rounding it away.
    """
    if not amount.is_finite():
        raise InvalidAmountError(f"Amount must be finite, got {amount!r}")

    scaled = amount.scaleb(currency.exponent)
    try:
        # Trapping Inexact turns "silently rounded" into a loud failure.
        with localcontext() as ctx:
            ctx.traps[Inexact] = True
            integral = scaled.to_integral_exact()
    except (Inexact, InvalidOperation, ValueError) as exc:
        raise InvalidAmountError(
            f"{amount} has more precision than {currency} supports "
            f"({currency.exponent} decimal places)"
        ) from exc

    minor = int(integral)
    if abs(minor) > MAX_MINOR_UNITS:
        raise InvalidAmountError(f"Amount {amount} exceeds the maximum supported value")
    return minor


def format_minor_units(minor_units: int, currency: Currency) -> str:
    """Render integer minor units as a plain decimal string.

    Returns a bare number with no currency symbol or thousands separators;
    locale-aware presentation belongs in the UI layer, not the domain.
    """
    return str(Decimal(minor_units).scaleb(-currency.exponent))
