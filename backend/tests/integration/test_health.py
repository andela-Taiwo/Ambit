"""Phase 0: health/readiness written test-first, per the plan's TDD rule."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.db import session as session_module

pytestmark = pytest.mark.integration


async def test_health_returns_ok_without_touching_the_database(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_reports_database_connectivity(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["checks"]["database"] == "ok"


async def test_ready_returns_503_when_database_is_unreachable(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _fail() -> None:
        raise ConnectionError("database is down")

    monkeypatch.setattr(session_module, "check_database_connection", _fail)

    response = await client.get("/ready")

    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "error"


async def test_openapi_schema_is_served(client: AsyncClient) -> None:
    """The OpenAPI doc is the frontend's contract; it must be reachable."""
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"]


async def test_every_response_carries_a_correlation_id(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.headers.get("x-request-id")


async def test_inbound_correlation_id_is_echoed_back(client: AsyncClient) -> None:
    """Section 11: the frontend's request ID propagates through the backend."""
    response = await client.get("/health", headers={"X-Request-ID": "abc-123"})

    assert response.headers["x-request-id"] == "abc-123"
