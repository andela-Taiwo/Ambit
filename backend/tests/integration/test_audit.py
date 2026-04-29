"""Financial mutations are recorded in the append-only audit trail."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import AuditLog
from app.db.session import session_scope

pytestmark = pytest.mark.integration


async def _audit_rows(entity_type: str) -> list[AuditLog]:
    async with session_scope() as session:
        return list(
            await session.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == entity_type)
                .order_by(AuditLog.occurred_at)
            )
        )


class TestAuditTrail:
    async def test_transaction_create_and_delete_are_audited(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        headers = {**auth_headers, "X-Request-ID": "audit-test-request"}
        created = await client.post(
            "/api/v1/transactions",
            headers=headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-01-02",
            },
        )
        assert created.status_code == 201, created.text
        await client.delete(f"/api/v1/transactions/{created.json()['id']}", headers=headers)

        rows = await _audit_rows("transaction")

        assert [row.action for row in rows] == ["created", "deleted"]
        assert all(row.entity_id is not None for row in rows)
        assert all(row.request_id == "audit-test-request" for row in rows)

    async def test_budget_and_investment_changes_are_audited(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        categories = await client.get(
            "/api/v1/categories", headers=auth_headers, params={"limit": 200}
        )
        groceries = next(item for item in categories.json()["items"] if item["name"] == "Groceries")
        await client.post(
            "/api/v1/budgets",
            headers=auth_headers,
            json={
                "category_id": groceries["id"],
                "amount": "100.00",
                "currency": "GBP",
                "starts_on": "2026-01-01",
            },
        )
        investment_account = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"name": "Invest", "account_type": "investment", "currency": "GBP"},
        )
        await client.post(
            "/api/v1/investments",
            headers=auth_headers,
            json={
                "account_id": investment_account.json()["id"],
                "name": "Bond",
                "investment_type": "fixed_rate",
                "principal": "100.00",
                "currency": "GBP",
                "rate": "5",
                "rate_period": "annual",
                "start_date": "2026-01-01",
            },
        )

        assert [row.action for row in await _audit_rows("budget")] == ["created"]
        assert [row.action for row in await _audit_rows("investment")] == ["created"]

    async def test_import_batch_is_audited(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            "/api/v1/transactions/import",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "csv": "date,amount\n2026-01-02,-10.00\n",
                "mapping": {"date": "date", "amount": "amount"},
            },
        )
        assert response.status_code == 200, response.text

        rows = await _audit_rows("import_batch")

        assert [row.action for row in rows] == ["imported"]
        assert rows[0].entity_id == uuid.UUID(response.json()["batch_id"])
