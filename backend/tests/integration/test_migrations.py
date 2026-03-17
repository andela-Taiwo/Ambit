"""Migrations are the only schema path -- never `create_all` (plan Section 2)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def test_alembic_upgrade_head_creates_the_version_table(engine: AsyncEngine) -> None:
    from app.db.migrate import run_migrations

    await run_migrations()

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL AS present")
        )
        assert result.scalar_one() is True


async def test_migrations_are_idempotent(engine: AsyncEngine) -> None:
    from app.db.migrate import run_migrations

    await run_migrations()
    await run_migrations()

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT count(*) FROM alembic_version"))
        assert result.scalar_one() == 1
