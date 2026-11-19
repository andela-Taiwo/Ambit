"""Account service."""

from __future__ import annotations

import uuid

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.models import Account, Transaction
from app.domain.money import Currency, InvalidAmountError, to_minor_units
from app.schemas.accounts import AccountCreate, AccountUpdate
from app.services import audit


def _owned(user_id: uuid.UUID) -> Select[tuple[Account]]:
    """Every query is scoped to the owner -- ownership is never optional."""
    return select(Account).where(Account.user_id == user_id)


async def get_account(session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    account = await session.scalar(_owned(user_id).where(Account.id == account_id))
    if account is None:
        # 404 rather than 403: confirming existence would leak that another
        # user owns this id.
        raise NotFoundError("Account not found")
    return account


async def list_accounts(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int,
    offset: int,
    include_archived: bool = False,
) -> tuple[list[Account], int]:
    query = _owned(user_id)
    if not include_archived:
        query = query.where(Account.is_archived.is_(False))

    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    rows = await session.scalars(query.order_by(Account.name).limit(limit).offset(offset))
    return list(rows), int(total or 0)


async def create_account(
    session: AsyncSession, user_id: uuid.UUID, payload: AccountCreate
) -> Account:
    currency = Currency(payload.currency)
    try:
        opening_balance_minor = to_minor_units(payload.opening_balance, currency)
    except InvalidAmountError as exc:
        raise ValidationError(str(exc)) from exc

    duplicate = await session.scalar(_owned(user_id).where(Account.name == payload.name))
    if duplicate is not None:
        raise ConflictError("An account with that name already exists")

    account = Account(
        user_id=user_id,
        name=payload.name,
        account_type=payload.account_type,
        currency=currency.code,
        opening_balance_minor=opening_balance_minor,
    )
    session.add(account)
    await session.flush()
    audit.record(
        session,
        user_id=user_id,
        entity_type="account",
        entity_id=account.id,
        action="created",
    )
    await session.commit()
    await session.refresh(account)
    return account


async def update_account(
    session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID, payload: AccountUpdate
) -> Account:
    account = await get_account(session, user_id, account_id)

    if payload.name is not None and payload.name != account.name:
        duplicate = await session.scalar(_owned(user_id).where(Account.name == payload.name))
        if duplicate is not None:
            raise ConflictError("An account with that name already exists")
        account.name = payload.name

    if payload.account_type is not None:
        account.account_type = payload.account_type
    if payload.is_archived is not None:
        account.is_archived = payload.is_archived

    audit.record(
        session,
        user_id=user_id,
        entity_type="account",
        entity_id=account.id,
        action="updated",
    )
    await session.commit()
    await session.refresh(account)
    return account


async def delete_account(session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> None:
    account = await get_account(session, user_id, account_id)
    await session.delete(account)
    audit.record(
        session,
        user_id=user_id,
        entity_type="account",
        entity_id=account.id,
        action="deleted",
    )
    await session.commit()


async def get_balance(
    session: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID
) -> tuple[Account, int]:
    """Opening balance plus the signed sum of every transaction on the account.

    Summed in the database rather than in Python so the query stays O(1) round
    trips as the ledger grows.
    """
    account = await get_account(session, user_id, account_id)

    movement = await session.scalar(
        select(func.coalesce(func.sum(Transaction.signed_amount_minor), 0)).where(
            Transaction.account_id == account_id
        )
    )

    return account, account.opening_balance_minor + int(movement or 0)
