"""Full-data export route."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, SessionDep
from app.schemas.common import UNAUTHORISED
from app.schemas.imports import FullExportResponse
from app.services import export as export_service

router = APIRouter(prefix="/export", tags=["export"], responses=UNAUTHORISED)


@router.get("", response_model=FullExportResponse, summary="Export all of the caller's data")
async def export_data(
    session: SessionDep, current_user: CurrentUser, response: Response
) -> FullExportResponse:
    export = await export_service.build_export(session, current_user)
    filename = f"budgetting-export-{datetime.now(UTC).date().isoformat()}.json"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "no-store"
    return export
