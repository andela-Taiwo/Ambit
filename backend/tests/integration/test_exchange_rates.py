"""Exchange-rate API: provenance, privacy, and conversion previews."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

RATES = "/api/v1/exchange-rates"


async def _record(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    base: str = "GBP",
    quote: str = "USD",
    rate: str = "1.25",
    as_of: str = "2026-01-01T00:00:00Z",
) -> dict[str, Any]:
    response = await client.post(
        RATES,
        headers=headers,
        json={"base_currency": base, "quote_currency": quote, "rate": rate, "as_of": as_of},
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


class TestRecordRate:
    async def test_records_a_manual_rate_with_provenance(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        body = await _record(client, auth_headers)

        assert body["base_currency"] == "GBP"
        assert body["quote_currency"] == "USD"
        assert body["source"] == "manual"
        assert body["as_of"] == "2026-01-01T00:00:00Z"

    async def test_rejects_a_precision_beyond_twelve_decimal_places(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            RATES,
            headers=auth_headers,
            json={
                "base_currency": "GBP",
                "quote_currency": "USD",
                "rate": "1.1234567890123",
                "as_of": "2026-01-01T00:00:00Z",
            },
        )

        assert response.status_code == 422

    async def test_rejects_the_same_currency_on_both_sides(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            RATES,
            headers=auth_headers,
            json={"base_currency": "GBP", "quote_currency": "GBP", "rate": "1"},
        )

        assert response.status_code == 422

    async def test_rejects_an_unknown_currency(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            RATES,
            headers=auth_headers,
            json={"base_currency": "GBP", "quote_currency": "XYZ", "rate": "1"},
        )

        assert response.status_code == 422

    async def test_rejects_a_duplicate_observation(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _record(client, auth_headers)

        response = await client.post(
            RATES,
            headers=auth_headers,
            json={
                "base_currency": "GBP",
                "quote_currency": "USD",
                "rate": "1.30",
                "as_of": "2026-01-01T00:00:00Z",
            },
        )

        assert response.status_code == 409

    async def test_normalises_a_naive_timestamp_to_utc(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        body = await _record(client, auth_headers, as_of="2026-01-01T09:30:00")

        assert body["as_of"] == "2026-01-01T09:30:00Z"

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.post(
            RATES,
            json={"base_currency": "GBP", "quote_currency": "USD", "rate": "1.25"},
        )

        assert response.status_code == 401


class TestLatestRate:
    async def test_returns_the_latest_rate_at_or_before_the_instant(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _record(client, auth_headers, rate="1.20", as_of="2026-01-01T00:00:00Z")
        await _record(client, auth_headers, rate="1.30", as_of="2026-02-01T00:00:00Z")

        response = await client.get(
            f"{RATES}/latest",
            headers=auth_headers,
            params={
                "base_currency": "GBP",
                "quote_currency": "USD",
                "as_of": "2026-02-15T00:00:00Z",
            },
        )

        assert response.status_code == 200
        assert response.json()["rate"] == "1.3"
        assert response.json()["is_inverse"] is False

    async def test_resolves_the_inverse_pair(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _record(client, auth_headers, rate="1.25")

        response = await client.get(
            f"{RATES}/latest",
            headers=auth_headers,
            params={
                "base_currency": "USD",
                "quote_currency": "GBP",
                "as_of": "2026-02-01T00:00:00Z",
            },
        )

        assert response.status_code == 200
        assert response.json()["rate"] == "0.8"
        assert response.json()["is_inverse"] is True

    async def test_same_currency_returns_the_identity_rate(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            f"{RATES}/latest",
            headers=auth_headers,
            params={"base_currency": "GBP", "quote_currency": "GBP"},
        )

        assert response.status_code == 200
        assert response.json()["rate"] == "1"
        assert response.json()["source"] == "identity"

    async def test_no_applicable_rate_is_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            f"{RATES}/latest",
            headers=auth_headers,
            params={
                "base_currency": "GBP",
                "quote_currency": "USD",
                "as_of": "2025-12-31T00:00:00Z",
            },
        )

        assert response.status_code == 404

    async def test_another_users_manual_rate_is_invisible(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        """A manual override must never leak across tenants."""
        await _record(client, auth_headers)

        response = await client.get(
            f"{RATES}/latest",
            headers=other_user_headers,
            params={
                "base_currency": "GBP",
                "quote_currency": "USD",
                "as_of": "2026-02-01T00:00:00Z",
            },
        )

        assert response.status_code == 404


class TestConvert:
    async def test_converts_an_exact_amount(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _record(client, auth_headers, rate="1.25")

        response = await client.get(
            f"{RATES}/convert",
            headers=auth_headers,
            params={
                "from_currency": "GBP",
                "to_currency": "USD",
                "amount": "100.00",
                "as_of": "2026-02-01T00:00:00Z",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["amount_minor"] == 10_000
        assert body["converted_minor"] == 12_500
        assert body["rate"] == "1.25"
        assert body["rate_source"] == "manual"

    async def test_uses_the_inverse_rate(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _record(client, auth_headers, rate="1.25")

        response = await client.get(
            f"{RATES}/convert",
            headers=auth_headers,
            params={
                "from_currency": "USD",
                "to_currency": "GBP",
                "amount": "125.00",
                "as_of": "2026-02-01T00:00:00Z",
            },
        )

        assert response.json()["converted_minor"] == 10_000
        assert response.json()["rate_is_inverse"] is True

    async def test_over_precise_amount_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _record(client, auth_headers)

        response = await client.get(
            f"{RATES}/convert",
            headers=auth_headers,
            params={
                "from_currency": "GBP",
                "to_currency": "USD",
                "amount": "10.005",
                "as_of": "2026-02-01T00:00:00Z",
            },
        )

        assert response.status_code == 422

    async def test_missing_rate_is_a_422_not_a_guess(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            f"{RATES}/convert",
            headers=auth_headers,
            params={
                "from_currency": "GBP",
                "to_currency": "NGN",
                "amount": "10.00",
                "as_of": "2026-02-01T00:00:00Z",
            },
        )

        assert response.status_code == 422
        assert "No exchange rate" in response.json()["detail"]


class TestListRates:
    async def test_lists_only_visible_rates_newest_first(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        await _record(client, auth_headers, rate="1.20", as_of="2026-01-01T00:00:00Z")
        await _record(client, auth_headers, rate="1.30", as_of="2026-02-01T00:00:00Z")
        await _record(client, other_user_headers, base="GBP", quote="EUR", rate="1.10")

        response = await client.get(RATES, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["total"] == 2
        assert [item["rate"] for item in response.json()["items"]] == ["1.3", "1.2"]

    async def test_filters_by_pair(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        await _record(client, auth_headers, base="GBP", quote="USD")
        await _record(client, auth_headers, base="GBP", quote="EUR", rate="1.10")

        response = await client.get(
            RATES,
            headers=auth_headers,
            params={"base_currency": "GBP", "quote_currency": "EUR"},
        )

        assert response.json()["total"] == 1
        assert response.json()["items"][0]["quote_currency"] == "EUR"

    async def test_is_paginated(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        await _record(client, auth_headers, rate="1.20", as_of="2026-01-01T00:00:00Z")
        await _record(client, auth_headers, rate="1.30", as_of="2026-02-01T00:00:00Z")

        response = await client.get(f"{RATES}?limit=1&offset=1", headers=auth_headers)

        assert response.json()["limit"] == 1
        assert response.json()["offset"] == 1
        assert len(response.json()["items"]) == 1
