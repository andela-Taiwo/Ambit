"""Reporting routes."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from fastapi.responses import StreamingResponse

from app.api.deps import CurrentUser, SessionDep
from app.domain.categories import CategoryKind
from app.schemas.common import UNAUTHORISED
from app.schemas.reports import (
    CashFlowResponse,
    CategoryBreakdownResponse,
    NetWorthHistoryResponse,
    NetWorthResponse,
)
from app.services import reports as reports_service

router = APIRouter(prefix="/reports", tags=["reports"], responses=UNAUTHORISED)


def _today() -> date:
    return datetime.now(UTC).date()


@router.get(
    "/net-worth",
    response_model=NetWorthResponse,
    summary="Net worth in the user's base currency",
)
async def net_worth(
    session: SessionDep, current_user: CurrentUser, as_of: date | None = None
) -> NetWorthResponse:
    return await reports_service.net_worth(session, current_user, as_of=as_of or _today())


@router.get(
    "/net-worth/history",
    response_model=NetWorthHistoryResponse,
    summary="Month-end net worth for the trailing period",
)
async def net_worth_history(
    session: SessionDep,
    current_user: CurrentUser,
    months: Annotated[int, Query(ge=1, le=60, description="Trailing months to include.")] = 12,
    as_of: date | None = None,
) -> NetWorthHistoryResponse:
    return await reports_service.net_worth_history(
        session, current_user, months=months, as_of=as_of or _today()
    )


@router.get(
    "/cash-flow",
    response_model=CashFlowResponse,
    summary="Income vs expense by month",
)
async def cash_flow(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> CashFlowResponse:
    return await reports_service.cash_flow(
        session, current_user, date_from=date_from, date_to=date_to
    )


@router.get(
    "/category-breakdown",
    response_model=CategoryBreakdownResponse,
    summary="Spend or income by category",
)
async def category_breakdown(
    session: SessionDep,
    current_user: CurrentUser,
    kind: CategoryKind = CategoryKind.EXPENSE,
    include_subcategories: bool = True,
    date_from: date | None = None,
    date_to: date | None = None,
) -> CategoryBreakdownResponse:
    return await reports_service.category_breakdown(
        session,
        current_user,
        date_from=date_from,
        date_to=date_to,
        kind=kind,
        include_subcategories=include_subcategories,
    )


@router.get(
    "/transactions.csv",
    summary="Export transactions as CSV",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/csv": {}}, "description": "A UTF-8 CSV export"}},
)
async def transactions_csv(
    session: SessionDep,
    current_user: CurrentUser,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Response:
    filename = f"transactions-{_today().isoformat()}.csv"
    stream = reports_service.transaction_csv(
        session, current_user.id, date_from=date_from, date_to=date_to
    )
    return StreamingResponse(
        stream,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
