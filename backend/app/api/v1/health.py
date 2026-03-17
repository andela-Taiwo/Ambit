"""Liveness and readiness probes (plan Section 11).

These are unversioned at the URL level (`/health`, `/ready`) because hosting
platforms and uptime monitors expect stable, well-known paths.
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.core.logging import get_logger
from app.db import session as db_session
from app.schemas.health import HealthResponse, ReadinessResponse

router = APIRouter(tags=["health"])
logger = get_logger(__name__)


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/ready", response_model=ReadinessResponse, summary="Readiness probe")
async def ready(response: Response) -> ReadinessResponse:
    try:
        await db_session.check_database_connection()
    except Exception as exc:
        logger.warning("readiness_check_failed", check="database", error=str(exc))
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(status="not_ready", checks={"database": "error"})

    return ReadinessResponse(status="ready", checks={"database": "ok"})
