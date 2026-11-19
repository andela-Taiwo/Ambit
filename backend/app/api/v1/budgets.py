"""Budget routes."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, SessionDep
from app.core.errors import ValidationError
from app.domain.budgets import month_range
from app.schemas.budgets import (
    BudgetCreate,
    BudgetPortfolioStatus,
    BudgetResponse,
    BudgetStatusResponse,
    BudgetUpdate,
)
from app.schemas.common import CONFLICT, NOT_FOUND, UNAUTHORISED, Page
from app.services import budgets as budgets_service

router = APIRouter(prefix="/budgets", tags=["budgets"], responses=UNAUTHORISED)

MonthParam = Annotated[
    str | None,
    Query(
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        examples=["2026-02"],
        description="Calendar month in YYYY-MM form. Defaults to the current month (UTC).",
    ),
]


def _requested_month(period: str | None) -> date:
    if period is None:
        return month_range(datetime.now(UTC).date()).start
    try:
        year_text, month_text = period.split("-", 1)
        return date(int(year_text), int(month_text), 1)
    except ValueError as exc:  # pragma: no cover - the regex already constrains this
        raise ValidationError("period must be a calendar month in YYYY-MM form") from exc


@router.get("", response_model=Page[BudgetResponse], summary="List budgets")
async def list_budgets(
    session: SessionDep,
    current_user: CurrentUser,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    category_id: uuid.UUID | None = None,
    include_archived: bool = False,
) -> Page[BudgetResponse]:
    rows, total = await budgets_service.list_budgets(
        session,
        current_user.id,
        limit=limit,
        offset=offset,
        category_id=category_id,
        include_archived=include_archived,
    )
    return Page(
        items=[BudgetResponse.model_validate(row) for row in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "",
    response_model=BudgetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a monthly category budget",
    responses=NOT_FOUND | CONFLICT,
)
async def create_budget(
    session: SessionDep, current_user: CurrentUser, payload: BudgetCreate
) -> BudgetResponse:
    budget = await budgets_service.create_budget(session, current_user.id, payload)
    return BudgetResponse.model_validate(budget)


@router.get(
    "/status",
    response_model=BudgetPortfolioStatus,
    summary="Budget vs actual for every active budget",
)
async def portfolio_status(
    session: SessionDep,
    current_user: CurrentUser,
    period: MonthParam = None,
) -> BudgetPortfolioStatus:
    requested = _requested_month(period)
    items = await budgets_service.status_for_all_budgets(
        session, current_user.id, requested_month=requested
    )
    month = month_range(requested)
    return BudgetPortfolioStatus(
        period_start=month.start,
        period_end=month.end,
        base_currency=current_user.base_currency,
        items=items,
    )


@router.get(
    "/{budget_id}",
    response_model=BudgetResponse,
    summary="Get a budget",
    responses=NOT_FOUND,
)
async def get_budget(
    session: SessionDep, current_user: CurrentUser, budget_id: uuid.UUID
) -> BudgetResponse:
    budget = await budgets_service.get_budget(session, current_user.id, budget_id)
    return BudgetResponse.model_validate(budget)


@router.get(
    "/{budget_id}/status",
    response_model=BudgetStatusResponse,
    summary="Get one budget's status for a month",
    responses=NOT_FOUND,
)
async def budget_status(
    session: SessionDep,
    current_user: CurrentUser,
    budget_id: uuid.UUID,
    period: MonthParam = None,
) -> BudgetStatusResponse:
    budget = await budgets_service.get_budget(session, current_user.id, budget_id)
    return await budgets_service.budget_status(
        session, current_user.id, budget, requested_month=_requested_month(period)
    )


@router.patch(
    "/{budget_id}",
    response_model=BudgetResponse,
    summary="Update a budget",
    responses=NOT_FOUND | CONFLICT,
)
async def update_budget(
    session: SessionDep,
    current_user: CurrentUser,
    budget_id: uuid.UUID,
    payload: BudgetUpdate,
) -> BudgetResponse:
    budget = await budgets_service.update_budget(session, current_user.id, budget_id, payload)
    return BudgetResponse.model_validate(budget)


@router.delete(
    "/{budget_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a budget",
    responses=NOT_FOUND,
)
async def delete_budget(
    session: SessionDep, current_user: CurrentUser, budget_id: uuid.UUID
) -> None:
    await budgets_service.delete_budget(session, current_user.id, budget_id)
