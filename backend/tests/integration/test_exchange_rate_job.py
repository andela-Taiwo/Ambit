"""Persistence semantics of the scheduled exchange-rate fetch."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import ExchangeRate
from app.db.session import session_scope
from app.jobs.fetch_exchange_rates import ProviderRates, RateProviderError, run, store_rates

pytestmark = pytest.mark.integration


def _rates(as_of: datetime | None = None) -> ProviderRates:
    return ProviderRates(
        base_currency="GBP",
        as_of=as_of or datetime(2026, 10, 27, tzinfo=UTC),
        rates={"USD": Decimal("1.27"), "EUR": Decimal("1.16")},
        source="test:provider",
    )


class _FakeProvider:
    name = "test:provider"

    def __init__(self, result: ProviderRates | None = None, error: Exception | None = None) -> None:
        self._result = result
        self._error = error

    async def fetch(self, *, base_currency: str, quotes: Sequence[str]) -> ProviderRates:
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class TestStoreRates:
    async def test_stores_rates_and_is_idempotent(self, client: AsyncClient) -> None:
        async with session_scope() as session:
            assert await store_rates(session, _rates()) == 2
        async with session_scope() as session:
            assert await store_rates(session, _rates()) == 0

        async with session_scope() as session:
            rows = list(await session.scalars(select(ExchangeRate)))

        assert len(rows) == 2
        assert all(row.user_id is None for row in rows)
        assert all(row.source == "test:provider" for row in rows)

    async def test_global_rates_are_visible_to_every_user(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        async with session_scope() as session:
            await store_rates(session, _rates())

        response = await client.get(
            "/api/v1/exchange-rates/latest",
            headers=auth_headers,
            params={"base_currency": "GBP", "quote_currency": "USD"},
        )

        assert response.status_code == 200
        assert response.json()["rate"] == "1.27"
        assert response.json()["source"] == "test:provider"

    async def test_run_fetches_and_stores(self, client: AsyncClient) -> None:
        inserted = await run(settings=get_settings(), provider=_FakeProvider(result=_rates()))

        assert inserted == 2

    async def test_a_failed_fetch_leaves_existing_rates_untouched(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        async with session_scope() as session:
            await store_rates(session, _rates())

        with pytest.raises(RateProviderError):
            await run(
                settings=get_settings(),
                provider=_FakeProvider(error=RateProviderError("provider down")),
            )

        response = await client.get(
            "/api/v1/exchange-rates/latest",
            headers=auth_headers,
            params={"base_currency": "GBP", "quote_currency": "USD"},
        )
        assert response.status_code == 200
        assert response.json()["rate"] == "1.27"
