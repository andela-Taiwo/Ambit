"""Account routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.domain.money import Currency, format_minor_units
from app.schemas.accounts import (
    AccountBalanceResponse,
    AccountCreate,
    AccountResponse,
    AccountUpdate,
)
from app.schemas.common import CONFLICT, NOT_FOUND, UNAUTHORISED, Page
from app.services import accounts as accounts_service

router = APIRouter(prefix="/accounts", tags=["accounts"], responses=UNAUTHORISED)


@router.get("", response_model=Page[AccountResponse], summary="List accounts")
async def list_accounts(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    include_archived: bool = False,
) -> Page[AccountResponse]:
    rows, total = await accounts_service.list_accounts(
        session, current_user.id, limit=limit, offset=offset, include_archived=include_archived
    )
    return Page(
        items=[AccountResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an account",
    responses=CONFLICT,
)
async def create_account(
    session: SessionDep, current_user: CurrentUser, payload: AccountCreate
) -> AccountResponse:
    account = await accounts_service.create_account(session, current_user.id, payload)
    return AccountResponse.model_validate(account)


@router.get(
    "/{account_id}", response_model=AccountResponse, summary="Get an account", responses=NOT_FOUND
)
async def get_account(
    session: SessionDep, current_user: CurrentUser, account_id: uuid.UUID
) -> AccountResponse:
    account = await accounts_service.get_account(session, current_user.id, account_id)
    return AccountResponse.model_validate(account)


@router.get(
    "/{account_id}/balance",
    response_model=AccountBalanceResponse,
    summary="Get an account's current balance",
    responses=NOT_FOUND,
)
async def get_balance(
    session: SessionDep, current_user: CurrentUser, account_id: uuid.UUID
) -> AccountBalanceResponse:
    account, balance_minor = await accounts_service.get_balance(
        session, current_user.id, account_id
    )
    return AccountBalanceResponse(
        account_id=account.id,
        currency=account.currency,
        balance_minor=balance_minor,
        balance=format_minor_units(balance_minor, Currency(account.currency)),
    )


@router.patch(
    "/{account_id}",
    response_model=AccountResponse,
    summary="Update an account",
    responses={**NOT_FOUND, **CONFLICT},
)
async def update_account(
    session: SessionDep,
    current_user: CurrentUser,
    account_id: uuid.UUID,
    payload: AccountUpdate,
) -> AccountResponse:
    account = await accounts_service.update_account(session, current_user.id, account_id, payload)
    return AccountResponse.model_validate(account)


@router.delete(
    "/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an account",
    responses=NOT_FOUND,
)
async def delete_account(
    session: SessionDep, current_user: CurrentUser, account_id: uuid.UUID
) -> None:
    await accounts_service.delete_account(session, current_user.id, account_id)
