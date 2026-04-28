"""CSV import parsing rules.

Bank exports are messy: amounts arrive with currency symbols, thousands
separators, parenthesised negatives and inconsistent date strings. Parsing is
strict about what it accepts and rejects a whole batch on any bad row -- a
partially imported statement is harder to reason about than a retry.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Final

from app.domain.ledger import TransactionType

#: Characters commonly used as currency markers or digit grouping. They carry
#: no numeric meaning and are removed before `Decimal` parsing.
_STRIPPED: Final = "£$€₦¥₹, \u00a0\u202f"

MAX_IMPORT_ROWS: Final = 10_000
MAX_DESCRIPTION_LENGTH: Final = 255
MAX_EXTERNAL_ID_LENGTH: Final = 128


class ImportParseError(ValueError):
    """A single CSV cell could not be interpreted."""


class AmountSignConvention(StrEnum):
    NEGATIVE_IS_EXPENSE = "negative_is_expense"
    POSITIVE_IS_EXPENSE = "positive_is_expense"


def parse_amount(raw: str) -> Decimal:
    """Parse a statement amount, preserving exact decimal precision."""
    text = raw.strip()
    if not text:
        raise ImportParseError("Amount is empty")

    negative = False
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1]

    for character in _STRIPPED:
        text = text.replace(character, "")

    if text.endswith("-"):
        negative = True
        text = text[:-1]

    try:
        amount = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ImportParseError(f"Amount {raw!r} is not a decimal number") from exc

    if not amount.is_finite():
        raise ImportParseError(f"Amount {raw!r} is not finite")
    if amount == 0:
        raise ImportParseError("Amount must not be zero")
    return -amount if negative else amount


def classify(
    amount: Decimal, *, type_value: str | None, convention: AmountSignConvention
) -> TransactionType:
    """Resolve income vs expense from an explicit type cell or the sign."""
    if type_value is not None and type_value.strip():
        normalised = type_value.strip().lower()
        if normalised == TransactionType.INCOME.value:
            return TransactionType.INCOME
        if normalised == TransactionType.EXPENSE.value:
            return TransactionType.EXPENSE
        raise ImportParseError(
            f"Unsupported transaction type {type_value!r}; expected income or expense"
        )

    if convention is AmountSignConvention.NEGATIVE_IS_EXPENSE:
        return TransactionType.EXPENSE if amount < 0 else TransactionType.INCOME
    return TransactionType.EXPENSE if amount > 0 else TransactionType.INCOME
