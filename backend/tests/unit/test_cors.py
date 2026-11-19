"""CORS preflight behaviour, including the local Vite origins."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient, Response

from app.core.config import get_settings

REGISTER = "/api/v1/auth/register"
PREFLIGHT_HEADERS = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type,authorization,x-request-id",
}


@pytest.fixture(autouse=True)
def local_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "local-cors-test-secret-key")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    get_settings.cache_clear()


async def _preflight(origin: str) -> Response:
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.options(REGISTER, headers={"Origin": origin, **PREFLIGHT_HEADERS})


class TestLocalPreflight:
    async def test_allows_the_vite_localhost_origin(self) -> None:
        response = await _preflight("http://localhost:5173")

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
        assert response.headers["access-control-allow-credentials"] == "true"

    async def test_allows_the_vite_loopback_origin(self) -> None:
        response = await _preflight("http://127.0.0.1:5173")

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"

    async def test_allows_the_preview_origin(self) -> None:
        response = await _preflight("http://localhost:4173")

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:4173"

    async def test_rejects_an_unlisted_origin(self) -> None:
        response = await _preflight("https://evil.example.com")

        assert response.status_code == 400
        assert "access-control-allow-origin" not in response.headers
