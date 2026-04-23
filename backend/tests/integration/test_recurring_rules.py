"""Recurring-rule CRUD and idempotent transaction generation."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from httpx import AsyncClient

from app.db.models import RecurringRule
from app.db.session import session_scope
from app.jobs.run_recurring import run as run_job

pytestmark = pytest.mark.integration

RULES = "/api/v1/recurring-rules"


async def _categories(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/api/v1/categories", headers=headers, params={"limit": 200})
    return {item["name"]: item for item in response.json()["items"]}


async def _create_rule(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    account_id: object,
    category_id: object | None,
    transaction_type: str = "expense",
    amount: str = "1000.00",
    frequency: str = "monthly",
    interval: int = 1,
    day_of_month: int | None = 31,
    starts_on: str = "2026-01-31",
    ends_on: str | None = "2026-04-30",
    currency: str = "GBP",
    description: str = "Rent",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "category_id": category_id,
        "transaction_type": transaction_type,
        "amount": amount,
        "currency": currency,
        "frequency": frequency,
        "interval": interval,
        "starts_on": starts_on,
        "description": description,
    }
    if day_of_month is not None:
        payload["day_of_month"] = day_of_month
    if ends_on is not None:
        payload["ends_on"] = ends_on
    response = await client.post(RULES, headers=headers, json=payload)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def _run(
    client: AsyncClient, headers: dict[str, str], rule_id: object, *, as_of: str
) -> dict[str, Any]:
    response = await client.post(f"{RULES}/{rule_id}/run", headers=headers, params={"as_of": as_of})
    assert response.status_code == 200, response.text
    result: dict[str, Any] = response.json()
    return result


async def _transactions(
    client: AsyncClient, headers: dict[str, str], *, date_from: str, date_to: str
) -> list[dict[str, Any]]:
    response = await client.get(
        "/api/v1/transactions",
        headers=headers,
        params={"date_from": date_from, "date_to": date_to, "limit": 200},
    )
    assert response.status_code == 200, response.text
    items: list[dict[str, Any]] = response.json()["items"]
    return items


class TestCreateRule:
    async def test_creates_a_monthly_rule(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        categories = await _categories(client, auth_headers)

        rule = await _create_rule(
            client,
            auth_headers,
            account_id=account["id"],
            category_id=categories["Housing"]["id"],
        )

        assert rule["amount_minor"] == 100_000
        assert rule["frequency"] == "monthly"
        assert rule["day_of_month"] == 31
        assert rule["next_run_on"] == "2026-01-31"
        assert rule["last_run_on"] is None
        assert rule["is_active"] is True

    async def test_defaults_day_of_month_to_the_start_date(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(
            client,
            auth_headers,
            account_id=account["id"],
            category_id=None,
            starts_on="2026-01-15",
            day_of_month=None,
        )

        assert rule["day_of_month"] == 15

    async def test_rejects_an_income_category_on_an_expense_rule(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        categories = await _categories(client, auth_headers)

        response = await client.post(
            RULES,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": categories["Salary"]["id"],
                "transaction_type": "expense",
                "amount": "100.00",
                "currency": "GBP",
                "frequency": "monthly",
                "starts_on": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_currency_mismatch(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            RULES,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "100.00",
                "currency": "NGN",
                "frequency": "monthly",
                "starts_on": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_transfer_type(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            RULES,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "transfer",
                "amount": "100.00",
                "currency": "GBP",
                "frequency": "monthly",
                "starts_on": "2026-01-01",
            },
        )

        assert response.status_code == 422

    async def test_requires_authentication(
        self, client: AsyncClient, account: dict[str, object]
    ) -> None:
        response = await client.post(
            RULES,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "100.00",
                "currency": "GBP",
                "frequency": "monthly",
                "starts_on": "2026-01-01",
            },
        )

        assert response.status_code == 401


class TestRunRule:
    async def test_generates_month_end_occurrences(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        categories = await _categories(client, auth_headers)
        rule = await _create_rule(
            client,
            auth_headers,
            account_id=account["id"],
            category_id=categories["Housing"]["id"],
        )

        result = await _run(client, auth_headers, rule["id"], as_of="2026-04-30")

        assert result["generated_count"] == 4
        assert result["skipped_count"] == 0
        assert result["last_occurrence_on"] == "2026-04-30"
        assert result["next_run_on"] == "2026-05-31"

        transactions = await _transactions(
            client, auth_headers, date_from="2026-01-01", date_to="2026-04-30"
        )
        assert [tx["occurrence_on"] for tx in transactions] == [
            "2026-04-30",
            "2026-03-31",
            "2026-02-28",
            "2026-01-31",
        ]
        assert all(tx["amount_minor"] == 100_000 for tx in transactions)
        assert all(tx["signed_amount_minor"] == -100_000 for tx in transactions)
        assert all(tx["recurring_rule_id"] == rule["id"] for tx in transactions)

    async def test_is_idempotent(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)
        first = await _run(client, auth_headers, rule["id"], as_of="2026-02-28")
        second = await _run(client, auth_headers, rule["id"], as_of="2026-02-28")

        assert first["generated_count"] == 2
        assert second["generated_count"] == 0
        assert second["skipped_count"] == 0
        assert second["next_run_on"] == "2026-03-31"

    async def test_existing_occurrences_are_skipped_if_the_cursor_is_rewound(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """A crashed run that did not advance the cursor must converge."""
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)
        await _run(client, auth_headers, rule["id"], as_of="2026-02-28")

        async with session_scope() as session:
            stored = await session.get(RecurringRule, uuid.UUID(rule["id"]))
            assert stored is not None
            stored.next_run_on = stored.starts_on
            await session.commit()

        second = await _run(client, auth_headers, rule["id"], as_of="2026-02-28")

        assert second["generated_count"] == 0
        assert second["skipped_count"] == 2
        assert second["last_occurrence_on"] is None

    async def test_resumes_from_the_cursor(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        await _run(client, auth_headers, rule["id"], as_of="2026-01-31")
        second = await _run(client, auth_headers, rule["id"], as_of="2026-03-31")

        assert second["generated_count"] == 2
        assert second["last_occurrence_on"] == "2026-03-31"

    async def test_nothing_due_before_the_start_date(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        result = await _run(client, auth_headers, rule["id"], as_of="2026-01-01")

        assert result["generated_count"] == 0
        assert result["next_run_on"] == "2026-01-31"

    async def test_income_rule_credits_the_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        categories = await _categories(client, auth_headers)
        rule = await _create_rule(
            client,
            auth_headers,
            account_id=account["id"],
            category_id=categories["Salary"]["id"],
            transaction_type="income",
            amount="2500.00",
            day_of_month=25,
            starts_on="2026-01-25",
            ends_on=None,
        )

        await _run(client, auth_headers, rule["id"], as_of="2026-01-25")

        transactions = await _transactions(
            client, auth_headers, date_from="2026-01-01", date_to="2026-01-31"
        )
        assert transactions[0]["transaction_type"] == "income"
        assert transactions[0]["signed_amount_minor"] == 250_000

    async def test_inactive_rule_cannot_be_run(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)
        await client.patch(f"{RULES}/{rule['id']}", headers=auth_headers, json={"is_active": False})

        response = await client.post(
            f"{RULES}/{rule['id']}/run",
            headers=auth_headers,
            params={"as_of": "2026-04-30"},
        )

        assert response.status_code == 422

    async def test_another_user_cannot_run_the_rule(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        response = await client.post(
            f"{RULES}/{rule['id']}/run",
            headers=other_user_headers,
            params={"as_of": "2026-04-30"},
        )

        assert response.status_code == 404


class TestRuleCrud:
    async def test_lists_only_the_callers_rules(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        response = await client.get(RULES, headers=other_user_headers)

        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_updates_amount_and_ends_on(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        response = await client.patch(
            f"{RULES}/{rule['id']}",
            headers=auth_headers,
            json={"amount": "1200.00", "description": "Rent (new)", "ends_on": "2026-12-31"},
        )

        assert response.status_code == 200
        assert response.json()["amount_minor"] == 120_000
        assert response.json()["description"] == "Rent (new)"
        assert response.json()["ends_on"] == "2026-12-31"

    async def test_clears_the_end_date(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        response = await client.patch(
            f"{RULES}/{rule['id']}", headers=auth_headers, json={"ends_on": None}
        )

        assert response.status_code == 200
        assert response.json()["ends_on"] is None

    async def test_deletes_a_rule(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        rule = await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        response = await client.delete(f"{RULES}/{rule['id']}", headers=auth_headers)

        assert response.status_code == 204
        assert (await client.get(f"{RULES}/{rule['id']}", headers=auth_headers)).status_code == 404

    async def test_unknown_rule_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(f"{RULES}/{uuid.uuid4()}", headers=auth_headers)

        assert response.status_code == 404


class TestScheduledJob:
    async def test_runs_every_due_rule(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        rules, generated = await run_job(as_of=date(2026, 2, 28))

        assert rules == 1
        assert generated == 2

    async def test_is_safe_to_run_twice(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        await _create_rule(client, auth_headers, account_id=account["id"], category_id=None)

        await run_job(as_of=date(2026, 2, 28))
        rules, generated = await run_job(as_of=date(2026, 2, 28))

        assert rules == 0
        assert generated == 0
