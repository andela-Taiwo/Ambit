"""Session/engine lifecycle -- the foundation every Phase 1 repository sits on."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration


async def test_get_session_yields_a_working_session(app_env: None) -> None:
    from app.db.session import dispose_engine, get_session

    try:
        agen = get_session()
        session = await anext(agen)
        assert isinstance(session, AsyncSession)
        assert (await session.execute(text("SELECT 1"))).scalar_one() == 1
        await agen.aclose()
    finally:
        await dispose_engine()


async def test_get_session_rolls_back_when_the_caller_raises(app_env: None) -> None:
    from app.db.session import dispose_engine, get_session

    try:
        agen = get_session()
        session = await anext(agen)
        await session.execute(text("CREATE TEMP TABLE rollback_probe (id int)"))
        await session.execute(text("INSERT INTO rollback_probe VALUES (1)"))

        with pytest.raises(RuntimeError):
            await agen.athrow(RuntimeError("caller blew up"))

        assert not session.in_transaction()
    finally:
        await dispose_engine()


async def test_init_engine_is_idempotent(app_env: None) -> None:
    from app.db.session import dispose_engine, init_engine

    try:
        assert init_engine() is init_engine()
    finally:
        await dispose_engine()


async def test_get_engine_initialises_on_first_use(app_env: None) -> None:
    from app.db.session import dispose_engine, get_engine

    try:
        assert get_engine() is get_engine()
    finally:
        await dispose_engine()


async def test_check_database_connection_succeeds(app_env: None) -> None:
    from app.db.session import check_database_connection, dispose_engine

    try:
        await check_database_connection()
    finally:
        await dispose_engine()


async def test_dispose_engine_is_safe_to_call_twice(app_env: None) -> None:
    from app.db.session import dispose_engine, init_engine

    init_engine()
    await dispose_engine()
    await dispose_engine()
