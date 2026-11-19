"""Account CRUD, including ownership isolation."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

ACCOUNTS = "/api/v1/accounts"


class TestCreateAccount:
    async def test_creates_an_account(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            ACCOUNTS,
            headers=auth_headers,
            json={
                "name": "Savings",
                "account_type": "savings",
                "currency": "GBP",
                "opening_balance": "2500.00",
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Savings"
        assert body["opening_balance_minor"] == 250_000

    async def test_stores_naira_amounts_without_precision_loss(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """The plan's worked example: 10 million Naira."""
        response = await client.post(
            ACCOUNTS,
            headers=auth_headers,
            json={
                "name": "Naira Fixed Deposit",
                "account_type": "investment",
                "currency": "NGN",
                "opening_balance": "10000000.00",
            },
        )

        assert response.json()["opening_balance_minor"] == 1_000_000_000

    async def test_rejects_an_unsupported_currency(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            ACCOUNTS,
            headers=auth_headers,
            json={"name": "Bad", "account_type": "cash", "currency": "XYZ"},
        )

        assert response.status_code == 422

    async def test_rejects_over_precise_opening_balance(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            ACCOUNTS,
            headers=auth_headers,
            json={
                "name": "Too precise",
                "account_type": "cash",
                "currency": "GBP",
                "opening_balance": "10.005",
            },
        )

        assert response.status_code == 422

    async def test_duplicate_name_for_the_same_user_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            ACCOUNTS,
            headers=auth_headers,
            json={"name": account["name"], "account_type": "cash", "currency": "GBP"},
        )

        assert response.status_code == 409

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.post(
            ACCOUNTS, json={"name": "X", "account_type": "cash", "currency": "GBP"}
        )

        assert response.status_code == 401


class TestListAccounts:
    async def test_lists_only_the_callers_accounts(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        response = await client.get(ACCOUNTS, headers=other_user_headers)

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_returns_the_callers_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.get(ACCOUNTS, headers=auth_headers)

        ids = [item["id"] for item in response.json()["items"]]
        assert account["id"] in ids

    async def test_is_paginated(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.get(f"{ACCOUNTS}?limit=1&offset=0", headers=auth_headers)

        body = response.json()
        assert body["limit"] == 1
        assert body["offset"] == 0
        assert "total" in body


class TestGetAccount:
    async def test_returns_the_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.get(f"{ACCOUNTS}/{account['id']}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == account["id"]

    async def test_another_users_account_is_not_found(
        self,
        client: AsyncClient,
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        """404 not 403: existence itself must not leak across users."""
        response = await client.get(f"{ACCOUNTS}/{account['id']}", headers=other_user_headers)

        assert response.status_code == 404

    async def test_unknown_account_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(f"{ACCOUNTS}/{uuid.uuid4()}", headers=auth_headers)

        assert response.status_code == 404


class TestUpdateAccount:
    async def test_renames_the_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.patch(
            f"{ACCOUNTS}/{account['id']}", headers=auth_headers, json={"name": "Renamed"}
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Renamed"

    async def test_cannot_update_another_users_account(
        self,
        client: AsyncClient,
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        response = await client.patch(
            f"{ACCOUNTS}/{account['id']}", headers=other_user_headers, json={"name": "Hijacked"}
        )

        assert response.status_code == 404


class TestAccountBalance:
    async def test_balance_starts_at_the_opening_balance(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.get(f"{ACCOUNTS}/{account['id']}/balance", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["balance_minor"] == 100_000

    async def test_balance_reflects_income_and_expenses(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """1000.00 opening + 500.00 income - 200.00 expense = 1300.00."""
        for tx_type, amount in (("income", "500.00"), ("expense", "200.00")):
            await client.post(
                "/api/v1/transactions",
                headers=auth_headers,
                json={
                    "account_id": account["id"],
                    "transaction_type": tx_type,
                    "amount": amount,
                    "currency": "GBP",
                    "occurred_on": "2026-01-15",
                },
            )

        response = await client.get(f"{ACCOUNTS}/{account['id']}/balance", headers=auth_headers)

        assert response.json()["balance_minor"] == 130_000
        assert response.json()["balance"] == "1300.00"


class TestDeleteAccount:
    async def test_deletes_an_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.delete(f"{ACCOUNTS}/{account['id']}", headers=auth_headers)

        assert response.status_code == 204

    async def test_cannot_delete_another_users_account(
        self,
        client: AsyncClient,
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        response = await client.delete(f"{ACCOUNTS}/{account['id']}", headers=other_user_headers)

        assert response.status_code == 404
