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
from sqlalchemy import text
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
async def migrated_db(app_env: None) -> AsyncIterator[None]:
    """Apply migrations, then truncate between tests for isolation.

    Migrations run once per session; truncation per test is far cheaper than
    rebuilding the schema and keeps tests independent of ordering.
    """
    from app.db.migrate import run_migrations
    from app.db.session import dispose_engine, get_engine

    await run_migrations()
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "TRUNCATE TABLE transactions, categories, accounts, "
                "refresh_tokens, audit_logs, users RESTART IDENTITY CASCADE"
            )
        )
    try:
        yield
    finally:
        await dispose_engine()


@pytest.fixture
async def client(migrated_db: None) -> AsyncIterator[AsyncClient]:
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


@pytest.fixture
def user_payload() -> dict[str, str]:
    return {
        "email": "ada@example.com",
        "password": "correct-horse-battery-staple",
        "display_name": "Ada Lovelace",
        "base_currency": "GBP",
    }


@pytest.fixture
async def registered_user(client: AsyncClient, user_payload: dict[str, str]) -> dict[str, str]:
    response = await client.post("/api/v1/auth/register", json=user_payload)
    assert response.status_code == 201, response.text
    return user_payload


@pytest.fixture
async def auth_headers(client: AsyncClient, registered_user: dict[str, str]) -> dict[str, str]:
    """Log in and return an Authorization header for the registered user."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": registered_user["email"], "password": registered_user["password"]},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
async def other_user_headers(client: AsyncClient) -> dict[str, str]:
    """A second, unrelated user -- used to prove ownership isolation."""
    payload = {
        "email": "mallory@example.com",
        "password": "another-very-long-password",
        "display_name": "Mallory",
        "base_currency": "GBP",
    }
    register = await client.post("/api/v1/auth/register", json=payload)
    assert register.status_code == 201, register.text
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": payload["email"], "password": payload["password"]},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


@pytest.fixture
async def account(client: AsyncClient, auth_headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Current Account",
            "account_type": "current",
            "currency": "GBP",
            "opening_balance": "1000.00",
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, object] = response.json()
    return result
