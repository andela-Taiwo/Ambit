"""Transaction service, including double-entry transfers."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError, ValidationError
from app.db.models import Transaction
from app.domain.ledger import (
    LedgerError,
    TransactionType,
    build_transfer_legs,
    signed_amount,
    validate_transaction_amount,
)
from app.domain.money import Currency, InvalidAmountError, to_minor_units
from app.schemas.transactions import TransactionCreate, TransactionUpdate, TransferCreate
from app.services.accounts import get_account
from app.services.categories import get_category


def _owned(user_id: uuid.UUID) -> Select[tuple[Transaction]]:
    return select(Transaction).where(Transaction.user_id == user_id)


async def get_transaction(
    session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> Transaction:
    transaction = await session.scalar(_owned(user_id).where(Transaction.id == transaction_id))
    if transaction is None:
        raise NotFoundError("Transaction not found")
    return transaction


async def list_transactions(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[Transaction], int]:
    query = _owned(user_id)

    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    if category_id is not None:
        query = query.where(Transaction.category_id == category_id)
    if transaction_type is not None:
        query = query.where(Transaction.transaction_type == transaction_type)
    if date_from is not None:
        query = query.where(Transaction.occurred_on >= date_from)
    if date_to is not None:
        query = query.where(Transaction.occurred_on <= date_to)

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(
        query.order_by(Transaction.occurred_on.desc(), Transaction.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(rows), int(total or 0)


async def create_transaction(
    session: AsyncSession, user_id: uuid.UUID, payload: TransactionCreate
) -> Transaction:
    account = await get_account(session, user_id, payload.account_id)

    if payload.currency != account.currency:
        raise ValidationError(
            f"Transaction currency {payload.currency} does not match "
            f"account currency {account.currency}"
        )

    if payload.category_id is not None:
        await get_category(session, user_id, payload.category_id)

    currency = Currency(payload.currency)
    try:
        amount_minor = to_minor_units(payload.amount, currency)
        validate_transaction_amount(amount_minor)
    except (InvalidAmountError, LedgerError) as exc:
        raise ValidationError(str(exc)) from exc

    transaction_type = TransactionType(payload.transaction_type)
    transaction = Transaction(
        user_id=user_id,
        account_id=account.id,
        category_id=payload.category_id,
        transaction_type=transaction_type,
        amount_minor=amount_minor,
        signed_amount_minor=signed_amount(amount_minor, transaction_type),
        currency=currency.code,
        occurred_on=payload.occurred_on,
        description=payload.description,
        notes=payload.notes,
    )
    session.add(transaction)
    await session.commit()
    await session.refresh(transaction)
    return transaction


async def create_transfer(
    session: AsyncSession, user_id: uuid.UUID, payload: TransferCreate
) -> list[Transaction]:
    """Create both legs of a transfer in a single transaction.

    Ownership of *both* accounts is checked before anything is written, so a
    rejected transfer never leaves a half-applied entry in the ledger.
    """
    source = await get_account(session, user_id, payload.from_account_id)
    destination = await get_account(session, user_id, payload.to_account_id)

    if payload.currency != source.currency:
        raise ValidationError(
            f"Transfer currency {payload.currency} does not match "
            f"source account currency {source.currency}"
        )

    currency = Currency(payload.currency)
    try:
        amount_minor = to_minor_units(payload.amount, currency)
        debit, credit = build_transfer_legs(
            amount_minor=amount_minor,
            currency=currency.code,
            from_account_id=source.id,
            to_account_id=destination.id,
            to_currency=destination.currency,
        )
    except (InvalidAmountError, LedgerError) as exc:
        raise ValidationError(str(exc)) from exc

    legs = [
        Transaction(
            user_id=user_id,
            account_id=leg.account_id,
            category_id=None,
            transaction_type=TransactionType.TRANSFER,
            amount_minor=abs(leg.signed_amount_minor),
            signed_amount_minor=leg.signed_amount_minor,
            currency=leg.currency,
            occurred_on=payload.occurred_on,
            description=payload.description,
            notes=payload.notes,
            transfer_group_id=leg.transfer_group_id,
        )
        for leg in (debit, credit)
    ]
    session.add_all(legs)
    await session.commit()
    for leg_row in legs:
        await session.refresh(leg_row)
    return legs


async def update_transaction(
    session: AsyncSession,
    user_id: uuid.UUID,
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
) -> Transaction:
    transaction = await get_transaction(session, user_id, transaction_id)

    if transaction.transfer_group_id is not None:
        raise ValidationError(
            "Transfer legs cannot be edited directly; delete and recreate the transfer"
        )

    if payload.category_id is not None:
        await get_category(session, user_id, payload.category_id)
        transaction.category_id = payload.category_id

    if payload.amount is not None:
        currency = Currency(transaction.currency)
        try:
            amount_minor = to_minor_units(payload.amount, currency)
            validate_transaction_amount(amount_minor)
        except (InvalidAmountError, LedgerError) as exc:
            raise ValidationError(str(exc)) from exc
        transaction.amount_minor = amount_minor
        transaction.signed_amount_minor = signed_amount(amount_minor, transaction.transaction_type)

    if payload.occurred_on is not None:
        transaction.occurred_on = payload.occurred_on
    if payload.description is not None:
        transaction.description = payload.description
    if payload.notes is not None:
        transaction.notes = payload.notes

    await session.commit()
    await session.refresh(transaction)
    return transaction


async def delete_transaction(
    session: AsyncSession, user_id: uuid.UUID, transaction_id: uuid.UUID
) -> None:
    """Delete a transaction, or both legs when it is part of a transfer.

    Removing one leg alone would leave the ledger unbalanced, so transfers are
    always deleted as a pair.
    """
    transaction = await get_transaction(session, user_id, transaction_id)

    if transaction.transfer_group_id is not None:
        legs = await session.scalars(
            _owned(user_id).where(Transaction.transfer_group_id == transaction.transfer_group_id)
        )
        for leg in legs:
            await session.delete(leg)
    else:
        await session.delete(transaction)

    await session.commit()
