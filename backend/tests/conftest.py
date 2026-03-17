"""Shared pytest fixtures.

The integration fixtures start a real Postgres via Testcontainers rather than
SQLite, so dialect-specific behaviour (NUMERIC, constraints, async driver) is
exercised the same way in tests as in production.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer


@pytest.fixture(scope="session")
def postgres_dsn() -> Iterator[str]:
    """Start a throwaway Postgres for the session and yield an asyncpg DSN."""
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        yield postgres.get_connection_url()


@pytest.fixture
def app_env(postgres_dsn: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point application settings at the throwaway database."""
    monkeypatch.setenv("DATABASE_URL", postgres_dsn)
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-not-used-anywhere-real")
    monkeypatch.setenv("APP_ENV", "test")
    from app.core.config import get_settings

    get_settings.cache_clear()


@pytest.fixture
async def engine(app_env: None) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(os.environ["DATABASE_URL"], future=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def client(app_env: None) -> AsyncIterator[AsyncClient]:
    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    # The lifespan context runs so the DB engine is created and disposed
    # exactly as it is in production.
    async with (
        AsyncClient(transport=transport, base_url="http://test") as ac,
        app.router.lifespan_context(app),
    ):
        yield ac
