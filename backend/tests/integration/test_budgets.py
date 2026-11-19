"""Budget CRUD and budget-vs-actual behaviour."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

BUDGETS = "/api/v1/budgets"
TRANSACTIONS = "/api/v1/transactions"
RATES = "/api/v1/exchange-rates"


@pytest.fixture
async def categories(
    client: AsyncClient, auth_headers: dict[str, str]
) -> dict[str, dict[str, Any]]:
    response = await client.get("/api/v1/categories", headers=auth_headers, params={"limit": 200})
    assert response.status_code == 200, response.text
    return {item["name"]: item for item in response.json()["items"]}


async def _create_budget(
    client: AsyncClient,
    headers: dict[str, str],
    category_id: object,
    *,
    amount: str = "300.00",
    starts_on: str = "2026-01-01",
    ends_on: str | None = None,
    rollover: bool = False,
    currency: str = "GBP",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "category_id": category_id,
        "amount": amount,
        "currency": currency,
        "starts_on": starts_on,
        "rollover_enabled": rollover,
    }
    if ends_on is not None:
        payload["ends_on"] = ends_on
    response = await client.post(BUDGETS, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def _add_expense(
    client: AsyncClient,
    headers: dict[str, str],
    account_id: object,
    category_id: object,
    *,
    amount: str = "10.00",
    occurred_on: str = "2026-01-15",
    currency: str = "GBP",
) -> None:
    response = await client.post(
        TRANSACTIONS,
        headers=headers,
        json={
            "account_id": account_id,
            "category_id": category_id,
            "transaction_type": "expense",
            "amount": amount,
            "currency": currency,
            "occurred_on": occurred_on,
        },
    )
    assert response.status_code == 201, response.text


class TestCreateBudget:
    async def test_creates_a_monthly_budget(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        body = await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        assert body["amount_minor"] == 30_000
        assert body["currency"] == "GBP"
        assert body["starts_on"] == "2026-01-01"
        assert body["rollover_enabled"] is False

    async def test_rejects_an_income_category(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        response = await client.post(
            BUDGETS,
            headers=auth_headers,
            json={
                "category_id": categories["Salary"]["id"],
                "amount": "10.00",
                "currency": "GBP",
                "starts_on": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_second_active_budget_for_the_same_category(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        response = await client.post(
            BUDGETS,
            headers=auth_headers,
            json={
                "category_id": categories["Groceries"]["id"],
                "amount": "200.00",
                "currency": "GBP",
                "starts_on": "2026-02-01",
            },
        )

        assert response.status_code == 409

    async def test_rejects_a_mid_month_start(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        response = await client.post(
            BUDGETS,
            headers=auth_headers,
            json={
                "category_id": categories["Groceries"]["id"],
                "amount": "100.00",
                "currency": "GBP",
                "starts_on": "2026-01-15",
            },
        )

        assert response.status_code == 422

    async def test_rejects_an_end_not_after_the_start(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        response = await client.post(
            BUDGETS,
            headers=auth_headers,
            json={
                "category_id": categories["Groceries"]["id"],
                "amount": "100.00",
                "currency": "GBP",
                "starts_on": "2026-01-01",
                "ends_on": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_an_over_precise_amount(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        response = await client.post(
            BUDGETS,
            headers=auth_headers,
            json={
                "category_id": categories["Groceries"]["id"],
                "amount": "100.005",
                "currency": "GBP",
                "starts_on": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_allows_a_zero_budget(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        body = await _create_budget(
            client, auth_headers, categories["Groceries"]["id"], amount="0.00"
        )

        assert body["amount_minor"] == 0

    async def test_requires_authentication(
        self, client: AsyncClient, categories: dict[str, Any]
    ) -> None:
        response = await client.post(
            BUDGETS,
            json={
                "category_id": categories["Groceries"]["id"],
                "amount": "100.00",
                "currency": "GBP",
                "starts_on": "2026-01-01",
            },
        )

        assert response.status_code == 401


class TestReadUpdateDelete:
    async def test_lists_only_the_callers_budgets(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
        categories: dict[str, Any],
    ) -> None:
        await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        response = await client.get(BUDGETS, headers=other_user_headers)

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_gets_a_budget(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        response = await client.get(f"{BUDGETS}/{budget['id']}", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["id"] == budget["id"]

    async def test_another_users_budget_is_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        response = await client.get(f"{BUDGETS}/{budget['id']}", headers=other_user_headers)

        assert response.status_code == 404

    async def test_updates_amount_and_rollover(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        response = await client.patch(
            f"{BUDGETS}/{budget['id']}",
            headers=auth_headers,
            json={"amount": "450.00", "rollover_enabled": True},
        )

        assert response.status_code == 200
        assert response.json()["amount_minor"] == 45_000
        assert response.json()["rollover_enabled"] is True

    async def test_clears_an_end_date(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(
            client, auth_headers, categories["Groceries"]["id"], ends_on="2026-06-01"
        )

        response = await client.patch(
            f"{BUDGETS}/{budget['id']}", headers=auth_headers, json={"ends_on": None}
        )

        assert response.status_code == 200
        assert response.json()["ends_on"] is None

    async def test_archiving_frees_the_category_for_a_new_budget(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        archived = await client.patch(
            f"{BUDGETS}/{budget['id']}", headers=auth_headers, json={"is_archived": True}
        )
        assert archived.status_code == 200

        replacement = await _create_budget(
            client, auth_headers, categories["Groceries"]["id"], amount="250.00"
        )
        assert replacement["id"] != budget["id"]

    async def test_deletes_a_budget(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        response = await client.delete(f"{BUDGETS}/{budget['id']}", headers=auth_headers)

        assert response.status_code == 204
        remaining = await client.get(f"{BUDGETS}/{budget['id']}", headers=auth_headers)
        assert remaining.status_code == 404


class TestBudgetStatus:
    async def test_reports_spend_against_the_limit(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])
        await _add_expense(
            client, auth_headers, account["id"], categories["Groceries"]["id"], amount="120.00"
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-01"},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["spent_minor"] == 12_000
        assert body["remaining_minor"] == 18_000
        assert body["percent_used"] == "40.00"
        assert body["status"] == "on_track"
        assert body["transaction_count"] == 1

    async def test_includes_spending_on_child_categories(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Housing"]["id"])
        await _add_expense(
            client, auth_headers, account["id"], categories["Utilities"]["id"], amount="90.00"
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-01"},
        )

        assert response.json()["spent_minor"] == 9_000

    async def test_ignores_transfers_and_income(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])
        second = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"name": "Savings", "account_type": "savings", "currency": "GBP"},
        )
        transfer = await client.post(
            "/api/v1/transactions/transfers",
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": second.json()["id"],
                "amount": "50.00",
                "currency": "GBP",
                "occurred_on": "2026-01-10",
            },
        )
        income = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": categories["Groceries"]["id"],
                "transaction_type": "income",
                "amount": "500.00",
                "currency": "GBP",
                "occurred_on": "2026-01-10",
            },
        )

        assert transfer.status_code == 201
        assert income.status_code == 201

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-01"},
        )

        assert response.json()["spent_minor"] == 0

    async def test_excludes_the_next_month(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])
        await _add_expense(
            client,
            auth_headers,
            account["id"],
            categories["Groceries"]["id"],
            amount="10.00",
            occurred_on="2026-01-31",
        )
        await _add_expense(
            client,
            auth_headers,
            account["id"],
            categories["Groceries"]["id"],
            amount="99.00",
            occurred_on="2026-02-01",
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-01"},
        )

        assert response.json()["spent_minor"] == 1_000

    async def test_rollover_carries_unspent_into_the_next_month(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(
            client,
            auth_headers,
            categories["Groceries"]["id"],
            amount="100.00",
            rollover=True,
        )
        await _add_expense(
            client, auth_headers, account["id"], categories["Groceries"]["id"], amount="40.00"
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-02"},
        )

        body = response.json()
        assert body["rollover_in_minor"] == 6_000
        assert body["effective_limit_minor"] == 16_000
        assert body["spent_minor"] == 0

    async def test_rollover_overspend_creates_a_negative_carry(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(
            client,
            auth_headers,
            categories["Groceries"]["id"],
            amount="100.00",
            rollover=True,
        )
        await _add_expense(
            client, auth_headers, account["id"], categories["Groceries"]["id"], amount="130.00"
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-02"},
        )

        body = response.json()
        assert body["rollover_in_minor"] == -3_000
        assert body["effective_limit_minor"] == 7_000
        assert body["status"] == "on_track"

    async def test_rollover_disabled_does_not_carry(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(
            client, auth_headers, categories["Groceries"]["id"], amount="100.00"
        )
        await _add_expense(
            client, auth_headers, account["id"], categories["Groceries"]["id"], amount="40.00"
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-02"},
        )

        assert response.json()["rollover_in_minor"] == 0
        assert response.json()["effective_limit_minor"] == 10_000

    async def test_before_the_start_month_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2025-12"},
        )

        assert response.status_code == 404

    async def test_after_the_end_month_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(
            client, auth_headers, categories["Groceries"]["id"], ends_on="2026-03-01"
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-03"},
        )

        assert response.status_code == 404

    async def test_zero_limit_with_spending_is_over(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        budget = await _create_budget(
            client, auth_headers, categories["Groceries"]["id"], amount="0.00"
        )
        await _add_expense(
            client, auth_headers, account["id"], categories["Groceries"]["id"], amount="1.00"
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-01"},
        )

        assert response.json()["status"] == "over"
        assert response.json()["percent_used"] == "100.00"

    async def test_missing_fx_rate_fails_loudly(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        naira = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={
                "name": "Naira Wallet",
                "account_type": "cash",
                "currency": "NGN",
            },
        )
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])
        await _add_expense(
            client,
            auth_headers,
            naira.json()["id"],
            categories["Groceries"]["id"],
            amount="200000.00",
            currency="NGN",
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-01"},
        )

        assert response.status_code == 422
        assert "No exchange rate" in response.json()["detail"]

    async def test_converts_foreign_spending_with_a_recorded_rate(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        naira = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"name": "Naira Wallet", "account_type": "cash", "currency": "NGN"},
        )
        rate = await client.post(
            RATES,
            headers=auth_headers,
            json={
                "base_currency": "GBP",
                "quote_currency": "NGN",
                "rate": "2000",
                "as_of": "2026-01-01T00:00:00Z",
            },
        )
        assert rate.status_code == 201, rate.text

        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])
        await _add_expense(
            client,
            auth_headers,
            naira.json()["id"],
            categories["Groceries"]["id"],
            amount="200000.00",
            currency="NGN",
        )

        response = await client.get(
            f"{BUDGETS}/{budget['id']}/status",
            headers=auth_headers,
            params={"period": "2026-01"},
        )

        assert response.status_code == 200
        assert response.json()["spent_minor"] == 10_000


class TestPortfolioStatus:
    async def test_returns_status_for_each_applicable_budget(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        categories: dict[str, Any],
    ) -> None:
        groceries = await _create_budget(
            client, auth_headers, categories["Groceries"]["id"], amount="100.00"
        )
        await _create_budget(
            client,
            auth_headers,
            categories["Transport"]["id"],
            amount="50.00",
            starts_on="2026-03-01",
        )
        await _add_expense(
            client, auth_headers, account["id"], categories["Groceries"]["id"], amount="25.00"
        )

        response = await client.get(
            f"{BUDGETS}/status", headers=auth_headers, params={"period": "2026-01"}
        )

        assert response.status_code == 200
        body = response.json()
        assert body["period_start"] == "2026-01-01"
        assert body["period_end"] == "2026-02-01"
        assert [item["budget_id"] for item in body["items"]] == [groceries["id"]]
        assert body["items"][0]["spent_minor"] == 2_500

    async def test_excludes_archived_budgets(
        self, client: AsyncClient, auth_headers: dict[str, str], categories: dict[str, Any]
    ) -> None:
        budget = await _create_budget(client, auth_headers, categories["Groceries"]["id"])
        await client.patch(
            f"{BUDGETS}/{budget['id']}", headers=auth_headers, json={"is_archived": True}
        )

        response = await client.get(
            f"{BUDGETS}/status", headers=auth_headers, params={"period": "2026-01"}
        )

        assert response.json()["items"] == []

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(f"{BUDGETS}/status")).status_code == 401


class TestUnknownBudget:
    async def test_status_of_an_unknown_budget_is_404(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            f"{BUDGETS}/{uuid.uuid4()}/status", headers=auth_headers, params={"period": "2026-01"}
        )

        assert response.status_code == 404
