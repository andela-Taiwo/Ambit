"""Investment and valuation routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.domain.investments import InvestmentType
from app.schemas.common import CONFLICT, NOT_FOUND, UNAUTHORISED, Page
from app.schemas.investments import (
    InvestmentCreate,
    InvestmentResponse,
    InvestmentReturnsResponse,
    InvestmentUpdate,
    ValuationCreate,
    ValuationResponse,
)
from app.services import investments as investments_service

router = APIRouter(prefix="/investments", tags=["investments"], responses=UNAUTHORISED)


@router.get("", response_model=Page[InvestmentResponse], summary="List investments")
async def list_investments(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    account_id: uuid.UUID | None = None,
    investment_type: InvestmentType | None = None,
    include_archived: bool = False,
) -> Page[InvestmentResponse]:
    rows, total = await investments_service.list_investments(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
        account_id=account_id,
        investment_type=investment_type,
        include_archived=include_archived,
    )
    return Page(
        items=[InvestmentResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=InvestmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an investment",
    responses=NOT_FOUND | CONFLICT,
)
async def create_investment(
    session: SessionDep, current_user: CurrentUser, payload: InvestmentCreate
) -> InvestmentResponse:
    investment = await investments_service.create_investment(session, current_user.id, payload)
    return InvestmentResponse.model_validate(investment)


@router.get(
    "/{investment_id}",
    response_model=InvestmentResponse,
    summary="Get an investment",
    responses=NOT_FOUND,
)
async def get_investment(
    session: SessionDep, current_user: CurrentUser, investment_id: uuid.UUID
) -> InvestmentResponse:
    investment = await investments_service.get_investment(session, current_user.id, investment_id)
    return InvestmentResponse.model_validate(investment)


@router.patch(
    "/{investment_id}",
    response_model=InvestmentResponse,
    summary="Update an investment",
    responses=NOT_FOUND | CONFLICT,
)
async def update_investment(
    session: SessionDep,
    current_user: CurrentUser,
    investment_id: uuid.UUID,
    payload: InvestmentUpdate,
) -> InvestmentResponse:
    investment = await investments_service.update_investment(
        session, current_user.id, investment_id, payload
    )
    return InvestmentResponse.model_validate(investment)


@router.delete(
    "/{investment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an investment and its valuations",
    responses=NOT_FOUND,
)
async def delete_investment(
    session: SessionDep, current_user: CurrentUser, investment_id: uuid.UUID
) -> None:
    await investments_service.delete_investment(session, current_user.id, investment_id)


@router.get(
    "/{investment_id}/returns",
    response_model=InvestmentReturnsResponse,
    summary="Value an investment and calculate its return",
    responses=NOT_FOUND,
)
async def investment_returns(
    session: SessionDep,
    current_user: CurrentUser,
    investment_id: uuid.UUID,
    as_of: date | None = None,
) -> InvestmentReturnsResponse:
    investment = await investments_service.get_investment(session, current_user.id, investment_id)
    return await investments_service.investment_returns(
        session, current_user.id, investment, as_of=as_of
    )


@router.get(
    "/{investment_id}/valuations",
    response_model=Page[ValuationResponse],
    summary="List an investment's valuation snapshots",
    responses=NOT_FOUND,
)
async def list_valuations(
    session: SessionDep,
    current_user: CurrentUser,
    investment_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Page[ValuationResponse]:
    rows, total = await investments_service.list_valuations(
        session, current_user.id, investment_id, limit=limit, offset=offset
    )
    return Page(
        items=[ValuationResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/{investment_id}/valuations",
    response_model=ValuationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a valuation snapshot",
    responses=NOT_FOUND | CONFLICT,
)
async def create_valuation(
    session: SessionDep,
    current_user: CurrentUser,
    investment_id: uuid.UUID,
    payload: ValuationCreate,
) -> ValuationResponse:
    valuation = await investments_service.create_valuation(
        session, current_user.id, investment_id, payload
    )
    return ValuationResponse.model_validate(valuation)


@router.delete(
    "/{investment_id}/valuations/{valuation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a valuation snapshot",
    responses=NOT_FOUND,
)
async def delete_valuation(
    session: SessionDep,
    current_user: CurrentUser,
    investment_id: uuid.UUID,
    valuation_id: uuid.UUID,
) -> None:
    await investments_service.delete_valuation(
        session, current_user.id, investment_id, valuation_id
    )
