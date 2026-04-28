"""CSV import and full-data export behaviour."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

IMPORT = "/api/v1/transactions/import"
EXPORT = "/api/v1/export"
TRANSACTIONS = "/api/v1/transactions"


def _request(
    account_id: object,
    csv: str,
    *,
    mapping: dict[str, str] | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "csv": csv,
        "mapping": mapping or {"date": "date", "amount": "amount"},
    }
    payload.update(overrides)
    return payload


class TestCsvImport:
    async def test_imports_income_and_expense_rows(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount\n2026-01-02,-24.99\n2026-01-03,100.00\n",
            ),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["imported_count"] == 2
        assert body["skipped_count"] == 0
        assert body["batch_id"] is not None
        assert body["dry_run"] is False

        transactions = await client.get(TRANSACTIONS, headers=auth_headers, params={"limit": 200})
        rows = transactions.json()["items"]
        assert [row["signed_amount_minor"] for row in rows] == [10_000, -2_499]
        assert all(row["import_batch_id"] == body["batch_id"] for row in rows)

    async def test_reimporting_the_same_file_is_a_no_op(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        csv = "date,amount\n2026-01-02,-24.99\n2026-01-03,100.00\n"
        await client.post(IMPORT, headers=auth_headers, json=_request(account["id"], csv))

        response = await client.post(
            IMPORT, headers=auth_headers, json=_request(account["id"], csv)
        )

        assert response.json()["imported_count"] == 0
        assert response.json()["skipped_count"] == 2
        assert response.json()["batch_id"] is None

    async def test_rejects_a_file_with_no_data_rows(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(account["id"], "date,amount\n"),
        )

        assert response.status_code == 422
        assert "no data rows" in response.json()["detail"]

    async def test_dry_run_reports_without_writing(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(account["id"], "date,amount\n2026-01-02,-24.99\n", dry_run=True),
        )

        assert response.status_code == 200
        assert response.json()["imported_count"] == 1
        assert response.json()["batch_id"] is None
        transactions = await client.get(TRANSACTIONS, headers=auth_headers)
        assert transactions.json()["total"] == 0

    async def test_rejects_the_whole_file_on_a_bad_row(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount\n2026-01-02,-24.99\n2026-13-01,10.00\n2026-01-04,abc\n",
            ),
        )

        assert response.status_code == 422
        body = response.json()
        assert body["error_count"] == 2
        assert [error["row"] for error in body["errors"]] == [3, 4]
        transactions = await client.get(TRANSACTIONS, headers=auth_headers)
        assert transactions.json()["total"] == 0

    async def test_maps_categories_by_name(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        categories = await client.get(
            "/api/v1/categories", headers=auth_headers, params={"limit": 200}
        )
        groceries = next(item for item in categories.json()["items"] if item["name"] == "Groceries")

        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount,category\n2026-01-02,-24.99,groceries\n",
                mapping={"date": "date", "amount": "amount", "category": "category"},
            ),
        )

        assert response.status_code == 200, response.text
        transactions = await client.get(TRANSACTIONS, headers=auth_headers)
        assert transactions.json()["items"][0]["category_id"] == groceries["id"]

    async def test_uses_a_default_category(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        categories = await client.get(
            "/api/v1/categories", headers=auth_headers, params={"limit": 200}
        )
        groceries = next(item for item in categories.json()["items"] if item["name"] == "Groceries")

        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount\n2026-01-02,-24.99\n",
                default_category_id=groceries["id"],
            ),
        )

        assert response.status_code == 200
        transactions = await client.get(TRANSACTIONS, headers=auth_headers)
        assert transactions.json()["items"][0]["category_id"] == groceries["id"]

    async def test_rejects_an_unknown_category(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount,category\n2026-01-02,-24.99,Nope\n",
                mapping={"date": "date", "amount": "amount", "category": "category"},
            ),
        )

        assert response.status_code == 422
        assert "Unknown category" in response.json()["errors"][0]["message"]

    async def test_type_column_overrides_the_sign(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount,type\n2026-01-02,10.00,expense\n",
                mapping={"date": "date", "amount": "amount", "type": "type"},
            ),
        )

        assert response.status_code == 200
        transactions = await client.get(TRANSACTIONS, headers=auth_headers)
        assert transactions.json()["items"][0]["transaction_type"] == "expense"

    async def test_positive_is_expense_convention(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount\n2026-01-02,10.00\n",
                amount_sign="positive_is_expense",
            ),
        )

        assert response.status_code == 200
        transactions = await client.get(TRANSACTIONS, headers=auth_headers)
        assert transactions.json()["items"][0]["transaction_type"] == "expense"

    async def test_supports_bank_amount_and_date_formats(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                'date,amount\n31/01/2026,"£1,234.56"\n',
                date_format="%d/%m/%Y",
            ),
        )

        assert response.status_code == 200, response.text
        transactions = await client.get(TRANSACTIONS, headers=auth_headers)
        assert transactions.json()["items"][0]["amount_minor"] == 123_456
        assert transactions.json()["items"][0]["transaction_type"] == "income"

    async def test_duplicate_external_ids_are_skipped(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,amount,ref\n2026-01-02,-24.99,abc\n2026-01-02,-24.99,abc\n",
                mapping={"date": "date", "amount": "amount", "external_id": "ref"},
            ),
        )

        assert response.status_code == 200
        assert response.json()["imported_count"] == 1
        assert response.json()["skipped_count"] == 1

    async def test_rejects_a_currency_mismatch(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(account["id"], "date,amount\n2026-01-02,-24.99\n", currency="USD"),
        )

        assert response.status_code == 422

    async def test_rejects_an_archived_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        await client.patch(
            f"/api/v1/accounts/{account['id']}", headers=auth_headers, json={"is_archived": True}
        )

        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(account["id"], "date,amount\n2026-01-02,-24.99\n"),
        )

        assert response.status_code == 422

    async def test_cannot_import_into_another_users_account(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=other_user_headers,
            json=_request(account["id"], "date,amount\n2026-01-02,-24.99\n"),
        )

        assert response.status_code == 404

    async def test_missing_mapped_column_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            headers=auth_headers,
            json=_request(
                account["id"],
                "date,total\n2026-01-02,-24.99\n",
                mapping={"date": "date", "amount": "amount"},
            ),
        )

        assert response.status_code == 422
        assert "missing mapped column" in response.json()["detail"]

    async def test_requires_authentication(
        self, client: AsyncClient, account: dict[str, object]
    ) -> None:
        response = await client.post(
            IMPORT,
            json=_request(account["id"], "date,amount\n2026-01-02,-24.99\n"),
        )

        assert response.status_code == 401


class TestFullExport:
    async def test_exports_every_resource(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        categories = await client.get(
            "/api/v1/categories", headers=auth_headers, params={"limit": 200}
        )
        groceries = next(item for item in categories.json()["items"] if item["name"] == "Groceries")
        await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": groceries["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-01-02",
            },
        )
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
            json={
                "name": "Investments",
                "account_type": "investment",
                "currency": "GBP",
            },
        )
        investment = await client.post(
            "/api/v1/investments",
            headers=auth_headers,
            json={
                "account_id": investment_account.json()["id"],
                "name": "Bond",
                "investment_type": "fixed_rate",
                "principal": "1000.00",
                "currency": "GBP",
                "rate": "12",
                "rate_period": "annual",
                "start_date": "2026-01-01",
            },
        )
        await client.post(
            f"/api/v1/investments/{investment.json()['id']}/valuations",
            headers=auth_headers,
            json={"as_of": "2026-02-01", "value": "1010.00"},
        )
        await client.post(
            "/api/v1/recurring-rules",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "frequency": "monthly",
                "starts_on": "2026-01-01",
            },
        )
        await client.post(
            "/api/v1/exchange-rates",
            headers=auth_headers,
            json={
                "base_currency": "GBP",
                "quote_currency": "USD",
                "rate": "1.25",
                "as_of": "2026-01-01T00:00:00Z",
            },
        )

        response = await client.get(EXPORT, headers=auth_headers)

        assert response.status_code == 200, response.text
        assert "attachment" in response.headers["content-disposition"]
        body = response.json()
        assert body["schema_version"] == 1
        assert body["user"]["email"] == "ada@example.com"
        assert len(body["accounts"]) == 2
        assert len(body["transactions"]) == 1
        assert len(body["budgets"]) == 1
        assert len(body["investments"]) == 1
        assert len(body["investment_valuations"]) == 1
        assert len(body["recurring_rules"]) == 1
        assert len(body["exchange_rates"]) == 1
        assert body["audit_logs"]
        assert "password_hash" not in response.text
        assert "token_hash" not in response.text

    async def test_excludes_other_users_data(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        await client.post(
            "/api/v1/accounts",
            headers=other_user_headers,
            json={"name": "Theirs", "account_type": "cash", "currency": "GBP"},
        )

        response = await client.get(EXPORT, headers=auth_headers)

        assert response.json()["accounts"] == []

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(EXPORT)).status_code == 401
