"""Ledger rules: transaction validity and double-entry transfers.

Transfers are the highest-risk logic in Phase 1 -- they touch two accounts and
must never create or destroy value.
"""

from __future__ import annotations

import uuid

import pytest
from app.domain.ledger import (
    CurrencyMismatchError,
    InvalidTransactionError,
    TransactionType,
    build_transfer_legs,
    signed_amount,
    validate_transaction_amount,
)


class TestValidateTransactionAmount:
    def test_accepts_a_positive_amount(self) -> None:
        validate_transaction_amount(1_000)

    def test_rejects_zero(self) -> None:
        """A zero-value transaction is meaningless and usually a bug upstream."""
        with pytest.raises(InvalidTransactionError):
            validate_transaction_amount(0)

    def test_rejects_a_negative_amount(self) -> None:
        """Direction comes from the transaction type, never a negative amount."""
        with pytest.raises(InvalidTransactionError):
            validate_transaction_amount(-500)


class TestSignedAmount:
    def test_income_is_positive(self) -> None:
        assert signed_amount(1_000, TransactionType.INCOME) == 1_000

    def test_expense_is_negative(self) -> None:
        assert signed_amount(1_000, TransactionType.EXPENSE) == -1_000

    def test_transfer_is_negative_on_the_source_leg(self) -> None:
        assert signed_amount(1_000, TransactionType.TRANSFER) == -1_000


class TestBuildTransferLegs:
    def test_produces_exactly_two_legs(self) -> None:
        legs = build_transfer_legs(
            amount_minor=50_000,
            currency="GBP",
            from_account_id=uuid.uuid4(),
            to_account_id=uuid.uuid4(),
        )

        assert len(legs) == 2

    def test_legs_net_to_zero(self) -> None:
        """Double entry: a transfer moves value, it never creates or destroys it."""
        legs = build_transfer_legs(
            amount_minor=50_000,
            currency="GBP",
            from_account_id=uuid.uuid4(),
            to_account_id=uuid.uuid4(),
        )

        assert sum(leg.signed_amount_minor for leg in legs) == 0

    def test_debits_the_source_and_credits_the_destination(self) -> None:
        source, destination = uuid.uuid4(), uuid.uuid4()
        legs = build_transfer_legs(
            amount_minor=50_000,
            currency="GBP",
            from_account_id=source,
            to_account_id=destination,
        )

        debit = next(leg for leg in legs if leg.signed_amount_minor < 0)
        credit = next(leg for leg in legs if leg.signed_amount_minor > 0)

        assert debit.account_id == source
        assert credit.account_id == destination
        assert debit.signed_amount_minor == -50_000
        assert credit.signed_amount_minor == 50_000

    def test_both_legs_share_a_transfer_group_id(self) -> None:
        """The shared id is what lets the UI show one transfer, not two rows."""
        legs = build_transfer_legs(
            amount_minor=50_000,
            currency="GBP",
            from_account_id=uuid.uuid4(),
            to_account_id=uuid.uuid4(),
        )

        assert legs[0].transfer_group_id == legs[1].transfer_group_id

    def test_rejects_a_transfer_to_the_same_account(self) -> None:
        account_id = uuid.uuid4()

        with pytest.raises(InvalidTransactionError):
            build_transfer_legs(
                amount_minor=50_000,
                currency="GBP",
                from_account_id=account_id,
                to_account_id=account_id,
            )

    def test_rejects_a_zero_amount_transfer(self) -> None:
        with pytest.raises(InvalidTransactionError):
            build_transfer_legs(
                amount_minor=0,
                currency="GBP",
                from_account_id=uuid.uuid4(),
                to_account_id=uuid.uuid4(),
            )

    def test_rejects_a_negative_amount_transfer(self) -> None:
        with pytest.raises(InvalidTransactionError):
            build_transfer_legs(
                amount_minor=-100,
                currency="GBP",
                from_account_id=uuid.uuid4(),
                to_account_id=uuid.uuid4(),
            )

    def test_cross_currency_transfer_is_rejected_for_now(self) -> None:
        """Needs an exchange rate to be correct; that arrives in Phase 4."""
        with pytest.raises(CurrencyMismatchError):
            build_transfer_legs(
                amount_minor=50_000,
                currency="GBP",
                from_account_id=uuid.uuid4(),
                to_account_id=uuid.uuid4(),
                to_currency="NGN",
            )
