"""Transaction routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.domain.ledger import TransactionType
from app.schemas.common import NOT_FOUND, UNAUTHORISED, Page
from app.schemas.imports import CsvImportErrorResponse, CsvImportRequest, CsvImportResult
from app.schemas.transactions import (
    TransactionCreate,
    TransactionResponse,
    TransactionUpdate,
    TransferCreate,
    TransferResponse,
)
from app.services import imports as imports_service
from app.services import transactions as transactions_service

router = APIRouter(prefix="/transactions", tags=["transactions"], responses=UNAUTHORISED)


@router.get("", response_model=Page[TransactionResponse], summary="List transactions")
async def list_transactions(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    account_id: uuid.UUID | None = None,
    category_id: uuid.UUID | None = None,
    transaction_type: TransactionType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[TransactionResponse]:
    rows, total = await transactions_service.list_transactions(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
        account_id=account_id,
        category_id=category_id,
        transaction_type=transaction_type,
        date_from=date_from,
        date_to=date_to,
    )
    return Page(
        items=[TransactionResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an income or expense transaction",
    responses=NOT_FOUND,
)
async def create_transaction(
    session: SessionDep, current_user: CurrentUser, payload: TransactionCreate
) -> TransactionResponse:
    transaction = await transactions_service.create_transaction(session, current_user.id, payload)
    return TransactionResponse.model_validate(transaction)


@router.post(
    "/import",
    response_model=CsvImportResult,
    summary="Import transactions from CSV",
    responses={422: {"model": CsvImportErrorResponse, "description": "Row-level errors"}},
)
async def import_transactions(
    session: SessionDep, current_user: CurrentUser, payload: CsvImportRequest
) -> CsvImportResult:
    """Validate the whole file first, then import; duplicates are skipped."""
    return await imports_service.import_csv(session, current_user, payload)


@router.post(
    "/transfers",
    response_model=TransferResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Transfer between two accounts",
    responses=NOT_FOUND,
)
async def create_transfer(
    session: SessionDep, current_user: CurrentUser, payload: TransferCreate
) -> TransferResponse:
    legs = await transactions_service.create_transfer(session, current_user.id, payload)
    return TransferResponse(
        transfer_group_id=legs[0].transfer_group_id,
        legs=[TransactionResponse.model_validate(leg) for leg in legs],
    )


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a transaction",
    responses=NOT_FOUND,
)
async def get_transaction(
    session: SessionDep, current_user: CurrentUser, transaction_id: uuid.UUID
) -> TransactionResponse:
    transaction = await transactions_service.get_transaction(
        session, current_user.id, transaction_id
    )
    return TransactionResponse.model_validate(transaction)


@router.patch(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Update a transaction",
    responses=NOT_FOUND,
)
async def update_transaction(
    session: SessionDep,
    current_user: CurrentUser,
    transaction_id: uuid.UUID,
    payload: TransactionUpdate,
) -> TransactionResponse:
    transaction = await transactions_service.update_transaction(
        session, current_user.id, transaction_id, payload
    )
    return TransactionResponse.model_validate(transaction)


@router.delete(
    "/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction (both legs, if it is a transfer)",
    responses=NOT_FOUND,
)
async def delete_transaction(
    session: SessionDep, current_user: CurrentUser, transaction_id: uuid.UUID
) -> None:
    await transactions_service.delete_transaction(session, current_user.id, transaction_id)
