"""Aggregates every v1 router."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import accounts, auth, categories, health, transactions

api_router = APIRouter()

# Health probes stay unprefixed at the root: hosting platforms and uptime
# monitors expect stable, well-known paths.
api_router.include_router(health.router)

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth.router)
v1_router.include_router(accounts.router)
v1_router.include_router(categories.router)
v1_router.include_router(transactions.router)

api_router.include_router(v1_router)
