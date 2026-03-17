"""Programmatic Alembic entrypoint.

Deploys and tests both call `run_migrations()` so there is exactly one
migration path across every environment (plan Section 2: never `create_all`).
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.core.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _alembic_config() -> Config:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "app" / "db" / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
    return config


def run_migrations_sync(revision: str = "head") -> None:
    command.upgrade(_alembic_config(), revision)


async def run_migrations(revision: str = "head") -> None:
    """Run migrations without blocking the event loop."""
    await asyncio.to_thread(run_migrations_sync, revision)


if __name__ == "__main__":
    run_migrations_sync()
