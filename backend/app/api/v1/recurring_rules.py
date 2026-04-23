"""Recurring-rule routes."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import NOT_FOUND, UNAUTHORISED, Page
from app.schemas.recurring import (
    RecurringRuleCreate,
    RecurringRuleResponse,
    RecurringRuleUpdate,
    RecurringRunResponse,
)
from app.services import recurring as recurring_service

router = APIRouter(prefix="/recurring-rules", tags=["recurring rules"], responses=UNAUTHORISED)


@router.get("", response_model=Page[RecurringRuleResponse], summary="List recurring rules")
async def list_rules(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    account_id: uuid.UUID | None = None,
    include_inactive: bool = False,
) -> Page[RecurringRuleResponse]:
    rows, total = await recurring_service.list_rules(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
        account_id=account_id,
        include_inactive=include_inactive,
    )
    return Page(
        items=[RecurringRuleResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=RecurringRuleResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a recurring rule",
    responses=NOT_FOUND,
)
async def create_rule(
    session: SessionDep, current_user: CurrentUser, payload: RecurringRuleCreate
) -> RecurringRuleResponse:
    rule = await recurring_service.create_rule(session, current_user.id, payload)
    return RecurringRuleResponse.model_validate(rule)


@router.get(
    "/{rule_id}",
    response_model=RecurringRuleResponse,
    summary="Get a recurring rule",
    responses=NOT_FOUND,
)
async def get_rule(
    session: SessionDep, current_user: CurrentUser, rule_id: uuid.UUID
) -> RecurringRuleResponse:
    rule = await recurring_service.get_rule(session, current_user.id, rule_id)
    return RecurringRuleResponse.model_validate(rule)


@router.patch(
    "/{rule_id}",
    response_model=RecurringRuleResponse,
    summary="Update a recurring rule",
    responses=NOT_FOUND,
)
async def update_rule(
    session: SessionDep,
    current_user: CurrentUser,
    rule_id: uuid.UUID,
    payload: RecurringRuleUpdate,
) -> RecurringRuleResponse:
    rule = await recurring_service.update_rule(session, current_user.id, rule_id, payload)
    return RecurringRuleResponse.model_validate(rule)


@router.delete(
    "/{rule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a recurring rule",
    responses=NOT_FOUND,
)
async def delete_rule(session: SessionDep, current_user: CurrentUser, rule_id: uuid.UUID) -> None:
    await recurring_service.delete_rule(session, current_user.id, rule_id)


@router.post(
    "/{rule_id}/run",
    response_model=RecurringRunResponse,
    summary="Materialise a rule's due occurrences now",
    responses=NOT_FOUND,
)
async def run_rule(
    session: SessionDep,
    current_user: CurrentUser,
    rule_id: uuid.UUID,
    as_of: date | None = None,
) -> RecurringRunResponse:
    return await recurring_service.run_rule(session, current_user.id, rule_id, as_of=as_of)
