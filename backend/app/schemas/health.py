"""Health/readiness response contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Liveness: the process is up. Deliberately does not touch the database."""

    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    """Readiness: the app can serve traffic, including its dependencies."""

    status: Literal["ready", "not_ready"]
    checks: dict[str, Literal["ok", "error"]] = Field(default_factory=dict)
