"""Aggregates every v1 router. Feature routers are added here from Phase 1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import health

api_router = APIRouter()
api_router.include_router(health.router)
