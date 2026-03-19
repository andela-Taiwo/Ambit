"""Ledger rules: transaction validity and double-entry transfers.

Amounts are always stored as a positive magnitude plus a `TransactionType`;
direction is derived, never encoded as a negative number. That keeps "how much"
and "which way" independent, so a sign error cannot silently turn income into
an expense.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import StrEnum


class LedgerError(Exception):
    """Base class for ledger domain errors."""


class InvalidTransactionError(LedgerError):
    """The transaction violates a ledger invariant."""


class CurrencyMismatchError(LedgerError):
    """An operation spans currencies without a conversion rate."""


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"
    TRANSFER = "transfer"


@dataclass(frozen=True, slots=True)
class TransferLeg:
    """One side of a transfer. Two legs always net to zero."""

    account_id: uuid.UUID
    signed_amount_minor: int
    currency: str
    transfer_group_id: uuid.UUID


def validate_transaction_amount(amount_minor: int) -> None:
    """Amounts are strictly positive magnitudes."""
    if amount_minor == 0:
        raise InvalidTransactionError("Transaction amount must not be zero")
    if amount_minor < 0:
        raise InvalidTransactionError(
            "Transaction amount must be positive; direction is set by the "
            "transaction type, not a negative amount"
        )


def signed_amount(amount_minor: int, transaction_type: TransactionType) -> int:
    """Apply the sign implied by the transaction type.

    Transfers sign as negative here because this expresses the *source* leg;
    the destination leg is produced by `build_transfer_legs`.
    """
    if transaction_type is TransactionType.INCOME:
        return amount_minor
    return -amount_minor


def build_transfer_legs(
    *,
    amount_minor: int,
    currency: str,
    from_account_id: uuid.UUID,
    to_account_id: uuid.UUID,
    to_currency: str | None = None,
) -> tuple[TransferLeg, TransferLeg]:
    """Build the debit/credit pair for a transfer between two accounts.

    Cross-currency transfers are rejected until Phase 4 introduces exchange
    rates -- guessing a rate would silently corrupt the ledger.
    """
    validate_transaction_amount(amount_minor)

    if from_account_id == to_account_id:
        raise InvalidTransactionError("Cannot transfer to the same account")

    if to_currency is not None and to_currency != currency:
        raise CurrencyMismatchError(
            f"Cross-currency transfers are not supported yet "
            f"({currency} -> {to_currency}); requires an exchange rate"
        )

    transfer_group_id = uuid.uuid4()

    debit = TransferLeg(
        account_id=from_account_id,
        signed_amount_minor=-amount_minor,
        currency=currency,
        transfer_group_id=transfer_group_id,
    )
    credit = TransferLeg(
        account_id=to_account_id,
        signed_amount_minor=amount_minor,
        currency=currency,
        transfer_group_id=transfer_group_id,
    )
    return debit, credit
