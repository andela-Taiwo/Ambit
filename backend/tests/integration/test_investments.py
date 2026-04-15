"""Investment CRUD, valuations and return calculations."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

INVESTMENTS = "/api/v1/investments"


async def _investment_account(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str = "Naira Fixed Deposit",
    currency: str = "NGN",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": name,
            "account_type": "investment",
            "currency": currency,
            "opening_balance": "0.00",
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def _create_fixed(
    client: AsyncClient,
    headers: dict[str, str],
    account_id: object,
    *,
    name: str = "24% Naira Fixed Deposit",
    principal: str = "10000000.00",
    rate: str = "24",
    currency: str = "NGN",
    start_date: str = "2026-01-01",
    maturity_date: str | None = None,
    compounding: str = "simple",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "name": name,
        "investment_type": "fixed_rate",
        "principal": principal,
        "currency": currency,
        "rate": rate,
        "rate_period": "annual",
        "compounding": compounding,
        "start_date": start_date,
    }
    if maturity_date is not None:
        payload["maturity_date"] = maturity_date
    response = await client.post(INVESTMENTS, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


class TestCreateInvestment:
    async def test_creates_a_fixed_rate_holding(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)

        body = await _create_fixed(client, auth_headers, account["id"])

        assert body["principal_minor"] == 1_000_000_000
        assert body["rate"] == "24"
        assert body["rate_period"] == "annual"
        assert body["investment_type"] == "fixed_rate"

    async def test_rejects_a_current_account(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        response = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "Wrong container",
                "investment_type": "fixed_rate",
                "principal": "100.00",
                "currency": "GBP",
                "rate": "5",
                "rate_period": "annual",
                "start_date": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_currency_mismatch(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers, currency="NGN")

        response = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "Wrong currency",
                "investment_type": "fixed_rate",
                "principal": "100.00",
                "currency": "GBP",
                "rate": "5",
                "rate_period": "annual",
                "start_date": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_fixed_rate_requires_a_rate(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)

        response = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "No rate",
                "investment_type": "fixed_rate",
                "principal": "100.00",
                "currency": "NGN",
                "start_date": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_market_priced_rejects_a_rate(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)

        response = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "Market",
                "investment_type": "market_priced",
                "principal": "100.00",
                "currency": "NGN",
                "rate": "5",
                "rate_period": "annual",
                "start_date": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_maturity_before_start(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)

        response = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "Backwards",
                "investment_type": "fixed_rate",
                "principal": "100.00",
                "currency": "NGN",
                "rate": "5",
                "rate_period": "annual",
                "start_date": "2026-02-01",
                "maturity_date": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_duplicate_name(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        await _create_fixed(client, auth_headers, account["id"])

        response = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "24% Naira Fixed Deposit",
                "investment_type": "market_priced",
                "principal": "100.00",
                "currency": "NGN",
                "start_date": "2026-01-01",
            },
        )

        assert response.status_code == 409

    async def test_rejects_over_precise_principal(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)

        response = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "Precise",
                "investment_type": "market_priced",
                "principal": "100.005",
                "currency": "NGN",
                "start_date": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(INVESTMENTS)).status_code == 401


class TestInvestmentCrud:
    async def test_lists_only_the_callers_holdings(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        account = await _investment_account(client, auth_headers)
        await _create_fixed(client, auth_headers, account["id"])

        response = await client.get(INVESTMENTS, headers=other_user_headers)

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_gets_and_updates_a_holding(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        updated = await client.patch(
            f"{INVESTMENTS}/{investment['id']}",
            headers=auth_headers,
            json={"name": "Renamed", "principal": "12000000.00", "notes": "rolled over"},
        )

        assert updated.status_code == 200
        assert updated.json()["name"] == "Renamed"
        assert updated.json()["principal_minor"] == 1_200_000_000
        assert updated.json()["notes"] == "rolled over"

    async def test_another_users_holding_is_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.get(f"{INVESTMENTS}/{investment['id']}", headers=other_user_headers)

        assert response.status_code == 404

    async def test_archiving_hides_from_the_default_list(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        await client.patch(
            f"{INVESTMENTS}/{investment['id']}",
            headers=auth_headers,
            json={"is_archived": True},
        )

        default = await client.get(INVESTMENTS, headers=auth_headers)
        included = await client.get(
            INVESTMENTS, headers=auth_headers, params={"include_archived": True}
        )

        assert default.json()["items"] == []
        assert included.json()["total"] == 1

    async def test_deletes_a_holding(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.delete(f"{INVESTMENTS}/{investment['id']}", headers=auth_headers)

        assert response.status_code == 204
        assert (
            await client.get(f"{INVESTMENTS}/{investment['id']}", headers=auth_headers)
        ).status_code == 404

    async def test_market_priced_update_cannot_gain_a_rate(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        created = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "Market",
                "investment_type": "market_priced",
                "principal": "100.00",
                "currency": "NGN",
                "start_date": "2026-01-01",
            },
        )

        response = await client.patch(
            f"{INVESTMENTS}/{created.json()['id']}",
            headers=auth_headers,
            json={"rate": "5", "rate_period": "annual"},
        )

        assert response.status_code == 422


class TestReturns:
    async def test_accrues_the_worked_example(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.get(
            f"{INVESTMENTS}/{investment['id']}/returns",
            headers=auth_headers,
            params={"as_of": "2026-02-01"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["value_minor"] == 1_020_000_000
        assert body["accrued_interest_minor"] == 20_000_000
        assert body["gain_minor"] == 20_000_000
        assert body["gain_percent"] == "2.00"
        assert body["value_source"] == "accrual"
        assert body["projected_monthly_interest_minor"] == 20_000_000
        assert body["projected_annual_interest_minor"] == 240_000_000

    async def test_before_the_start_date_value_is_cost(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.get(
            f"{INVESTMENTS}/{investment['id']}/returns",
            headers=auth_headers,
            params={"as_of": "2025-12-31"},
        )

        assert response.json()["value_minor"] == 1_000_000_000
        assert response.json()["gain_minor"] == 0

    async def test_accrual_stops_at_maturity(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(
            client, auth_headers, account["id"], maturity_date="2026-03-01"
        )

        response = await client.get(
            f"{INVESTMENTS}/{investment['id']}/returns",
            headers=auth_headers,
            params={"as_of": "2026-12-31"},
        )

        assert response.json()["accrued_interest_minor"] == 40_000_000

    async def test_market_priced_without_a_valuation_uses_cost(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers, name="Broker", currency="GBP")
        created = await client.post(
            INVESTMENTS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "name": "Index Fund",
                "investment_type": "market_priced",
                "principal": "5000.00",
                "currency": "GBP",
                "start_date": "2026-01-01",
            },
        )

        response = await client.get(
            f"{INVESTMENTS}/{created.json()['id']}/returns",
            headers=auth_headers,
            params={"as_of": "2026-06-01"},
        )

        assert response.json()["value_source"] == "principal"
        assert response.json()["value_minor"] == 500_000
        assert response.json()["gain_minor"] == 0
        assert response.json()["projected_monthly_interest_minor"] is None

    async def test_a_valuation_snapshot_overrides_accrual(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])
        valuation = await client.post(
            f"{INVESTMENTS}/{investment['id']}/valuations",
            headers=auth_headers,
            json={"as_of": "2026-02-01", "value": "10500000.00", "notes": "bank statement"},
        )
        assert valuation.status_code == 201, valuation.text

        response = await client.get(
            f"{INVESTMENTS}/{investment['id']}/returns",
            headers=auth_headers,
            params={"as_of": "2026-02-15"},
        )

        body = response.json()
        assert body["value_source"] == "valuation"
        assert body["value_minor"] == 1_050_000_000
        assert body["valuation_as_of"] == "2026-02-01"
        assert body["gain_minor"] == 50_000_000
        assert body["gain_percent"] == "5.00"

    async def test_another_user_cannot_read_returns(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.get(
            f"{INVESTMENTS}/{investment['id']}/returns", headers=other_user_headers
        )

        assert response.status_code == 404


class TestValuations:
    async def test_lists_and_deletes_snapshots(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])
        first = await client.post(
            f"{INVESTMENTS}/{investment['id']}/valuations",
            headers=auth_headers,
            json={"as_of": "2026-02-01", "value": "10100000.00"},
        )
        second = await client.post(
            f"{INVESTMENTS}/{investment['id']}/valuations",
            headers=auth_headers,
            json={"as_of": "2026-03-01", "value": "10200000.00"},
        )
        assert first.status_code == 201
        assert second.status_code == 201

        listing = await client.get(
            f"{INVESTMENTS}/{investment['id']}/valuations", headers=auth_headers
        )

        assert listing.status_code == 200
        assert listing.json()["total"] == 2
        assert listing.json()["items"][0]["as_of"] == "2026-03-01"

        deleted = await client.delete(
            f"{INVESTMENTS}/{investment['id']}/valuations/{first.json()['id']}",
            headers=auth_headers,
        )
        assert deleted.status_code == 204

    async def test_rejects_a_valuation_before_the_start_date(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.post(
            f"{INVESTMENTS}/{investment['id']}/valuations",
            headers=auth_headers,
            json={"as_of": "2025-12-31", "value": "100.00"},
        )

        assert response.status_code == 422

    async def test_rejects_a_duplicate_date(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])
        await client.post(
            f"{INVESTMENTS}/{investment['id']}/valuations",
            headers=auth_headers,
            json={"as_of": "2026-02-01", "value": "10100000.00"},
        )

        response = await client.post(
            f"{INVESTMENTS}/{investment['id']}/valuations",
            headers=auth_headers,
            json={"as_of": "2026-02-01", "value": "10200000.00"},
        )

        assert response.status_code == 409

    async def test_another_user_cannot_record_a_valuation(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.post(
            f"{INVESTMENTS}/{investment['id']}/valuations",
            headers=other_user_headers,
            json={"as_of": "2026-02-01", "value": "1.00"},
        )

        assert response.status_code == 404

    async def test_unknown_valuation_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        account = await _investment_account(client, auth_headers)
        investment = await _create_fixed(client, auth_headers, account["id"])

        response = await client.delete(
            f"{INVESTMENTS}/{investment['id']}/valuations/{uuid.uuid4()}",
            headers=auth_headers,
        )

        assert response.status_code == 404
