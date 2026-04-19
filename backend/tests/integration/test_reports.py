"""Reporting: net worth, cash flow, category breakdown and CSV export."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

REPORTS = "/api/v1/reports"


async def _account(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    name: str,
    currency: str = "GBP",
    account_type: str = "current",
    opening: str = "0.00",
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={
            "name": name,
            "account_type": account_type,
            "currency": currency,
            "opening_balance": opening,
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def _transaction(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    account_id: object,
    transaction_type: str,
    amount: str,
    currency: str = "GBP",
    occurred_on: str,
    category_id: object | None = None,
    description: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "transaction_type": transaction_type,
        "amount": amount,
        "currency": currency,
        "occurred_on": occurred_on,
        "description": description,
    }
    if category_id is not None:
        payload["category_id"] = category_id
    response = await client.post("/api/v1/transactions", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


async def _rate(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    base: str,
    quote: str,
    rate: str,
    as_of: str = "2026-01-01T00:00:00Z",
) -> None:
    response = await client.post(
        "/api/v1/exchange-rates",
        headers=headers,
        json={"base_currency": base, "quote_currency": quote, "rate": rate, "as_of": as_of},
    )
    assert response.status_code == 201, response.text


async def _categories(client: AsyncClient, headers: dict[str, str]) -> dict[str, Any]:
    response = await client.get("/api/v1/categories", headers=headers, params={"limit": 200})
    return {item["name"]: item for item in response.json()["items"]}


async def _fixed_investment(
    client: AsyncClient,
    headers: dict[str, str],
    *,
    account_id: object,
    name: str,
    principal: str,
    currency: str,
    rate: str,
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/investments",
        headers=headers,
        json={
            "account_id": account_id,
            "name": name,
            "investment_type": "fixed_rate",
            "principal": principal,
            "currency": currency,
            "rate": rate,
            "rate_period": "annual",
            "start_date": "2026-01-01",
        },
    )
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


class TestNetWorth:
    async def test_reports_accounts_and_fixed_rate_holdings_in_base_currency(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        current = await _account(client, auth_headers, name="Current", opening="1000.00")
        gbp_investment = await _account(
            client, auth_headers, name="GBP Investments", account_type="investment"
        )
        ngn_investment = await _account(
            client,
            auth_headers,
            name="NGN Investments",
            account_type="investment",
            currency="NGN",
        )
        await _transaction(
            client,
            auth_headers,
            account_id=current["id"],
            transaction_type="income",
            amount="500.00",
            occurred_on="2026-01-10",
        )
        await _transaction(
            client,
            auth_headers,
            account_id=current["id"],
            transaction_type="expense",
            amount="200.00",
            occurred_on="2026-01-20",
        )
        await _fixed_investment(
            client,
            auth_headers,
            account_id=gbp_investment["id"],
            name="12% Bond",
            principal="1000.00",
            currency="GBP",
            rate="12",
        )
        await _fixed_investment(
            client,
            auth_headers,
            account_id=ngn_investment["id"],
            name="24% Naira Deposit",
            principal="10000000.00",
            currency="NGN",
            rate="24",
        )
        await _rate(client, auth_headers, base="GBP", quote="NGN", rate="2000")

        response = await client.get(
            f"{REPORTS}/net-worth",
            headers=auth_headers,
            params={"as_of": "2026-02-01"},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["base_currency"] == "GBP"
        # 1,000 opening + 500 income - 200 expense.
        assert body["accounts_total_minor"] == 130_000
        # 1,000 GBP bond + 1% for January, and 10.2m NGN at 2,000 NGN/GBP.
        assert body["investments_total_minor"] == 101_000 + 510_000
        assert body["total_minor"] == 130_000 + 101_000 + 510_000
        assert len(body["accounts"]) == 1
        assert len(body["investments"]) == 2

        naira = next(item for item in body["investments"] if item["name"] == "24% Naira Deposit")
        assert naira["value"]["currency"] == "NGN"
        assert naira["value"]["amount_minor"] == 1_020_000_000
        assert naira["value"]["base_minor"] == 510_000
        assert naira["value"]["rate_is_inverse"] is True

    async def test_missing_rate_fails_loudly(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _account(client, auth_headers, name="Naira", currency="NGN", opening="1000.00")

        response = await client.get(f"{REPORTS}/net-worth", headers=auth_headers)

        assert response.status_code == 422
        assert "No exchange rate from NGN to GBP" in response.json()["detail"]

    async def test_other_users_holdings_are_excluded(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        other_user_headers: dict[str, str],
    ) -> None:
        await _account(client, auth_headers, name="Current", opening="5000.00")

        response = await client.get(f"{REPORTS}/net-worth", headers=other_user_headers)

        assert response.status_code == 200
        assert response.json()["total_minor"] == 0

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(f"{REPORTS}/net-worth")).status_code == 401


class TestNetWorthHistory:
    async def test_returns_month_end_points(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        current = await _account(client, auth_headers, name="Current", opening="1000.00")
        await _transaction(
            client,
            auth_headers,
            account_id=current["id"],
            transaction_type="income",
            amount="500.00",
            occurred_on="2026-01-10",
        )
        await _transaction(
            client,
            auth_headers,
            account_id=current["id"],
            transaction_type="expense",
            amount="200.00",
            occurred_on="2026-01-20",
        )
        await _transaction(
            client,
            auth_headers,
            account_id=current["id"],
            transaction_type="expense",
            amount="100.00",
            occurred_on="2026-02-10",
        )

        response = await client.get(
            f"{REPORTS}/net-worth/history",
            headers=auth_headers,
            params={"months": 2, "as_of": "2026-02-28"},
        )

        assert response.status_code == 200, response.text
        points = response.json()["points"]
        assert [point["as_of"] for point in points] == ["2026-01-31", "2026-02-28"]
        assert [point["total_minor"] for point in points] == [130_000, 120_000]

    async def test_rejects_an_out_of_range_month_count(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            f"{REPORTS}/net-worth/history", headers=auth_headers, params={"months": 61}
        )

        assert response.status_code == 422

    async def test_excludes_investment_account_cash_from_history(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        current = await _account(client, auth_headers, name="Current", opening="1000.00")
        investment_account = await _account(
            client, auth_headers, name="Broker", account_type="investment"
        )
        transfer = await client.post(
            "/api/v1/transactions/transfers",
            headers=auth_headers,
            json={
                "from_account_id": current["id"],
                "to_account_id": investment_account["id"],
                "amount": "500.00",
                "currency": "GBP",
                "occurred_on": "2026-01-15",
            },
        )
        assert transfer.status_code == 201, transfer.text

        response = await client.get(
            f"{REPORTS}/net-worth/history",
            headers=auth_headers,
            params={"months": 1, "as_of": "2026-01-31"},
        )

        point = response.json()["points"][0]
        assert point["accounts_minor"] == 50_000
        assert point["total_minor"] == 50_000

    async def test_includes_investment_valuations_at_each_point(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await _account(client, auth_headers, name="Current", opening="1000.00")
        investment_account = await _account(
            client, auth_headers, name="Broker", account_type="investment"
        )
        investment = await client.post(
            "/api/v1/investments",
            headers=auth_headers,
            json={
                "account_id": investment_account["id"],
                "name": "Fund",
                "investment_type": "market_priced",
                "principal": "1000.00",
                "currency": "GBP",
                "start_date": "2026-01-01",
            },
        )
        for as_of, value in (("2026-01-01", "1000.00"), ("2026-02-01", "1100.00")):
            response = await client.post(
                f"/api/v1/investments/{investment.json()['id']}/valuations",
                headers=auth_headers,
                json={"as_of": as_of, "value": value},
            )
            assert response.status_code == 201, response.text

        response = await client.get(
            f"{REPORTS}/net-worth/history",
            headers=auth_headers,
            params={"months": 2, "as_of": "2026-02-28"},
        )

        assert response.status_code == 200, response.text
        points = response.json()["points"]
        assert [point["accounts_minor"] for point in points] == [100_000, 100_000]
        assert [point["investments_minor"] for point in points] == [100_000, 110_000]
        assert [point["total_minor"] for point in points] == [200_000, 210_000]


class TestCashFlow:
    async def test_groups_income_and_expense_by_month(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        categories = await _categories(client, auth_headers)
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="income",
            amount="500.00",
            occurred_on="2026-01-05",
            category_id=categories["Salary"]["id"],
        )
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="200.00",
            occurred_on="2026-01-20",
            category_id=categories["Groceries"]["id"],
        )
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="100.00",
            occurred_on="2026-02-10",
            category_id=categories["Groceries"]["id"],
        )

        response = await client.get(
            f"{REPORTS}/cash-flow",
            headers=auth_headers,
            params={"date_from": "2026-01-01", "date_to": "2026-02-28"},
        )

        assert response.status_code == 200, response.text
        items = response.json()["items"]
        assert len(items) == 2
        assert items[0]["income_minor"] == 50_000
        assert items[0]["expense_minor"] == 20_000
        assert items[0]["net_minor"] == 30_000
        assert items[0]["transaction_count"] == 2
        assert items[1]["income_minor"] == 0
        assert items[1]["expense_minor"] == 10_000
        assert items[1]["net_minor"] == -10_000

    async def test_converts_foreign_transactions(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        categories = await _categories(client, auth_headers)
        naira = await _account(client, auth_headers, name="Naira", currency="NGN")
        await _rate(client, auth_headers, base="GBP", quote="NGN", rate="2000")
        await _transaction(
            client,
            auth_headers,
            account_id=naira["id"],
            transaction_type="expense",
            amount="200000.00",
            currency="NGN",
            occurred_on="2026-01-15",
            category_id=categories["Groceries"]["id"],
        )

        response = await client.get(
            f"{REPORTS}/cash-flow",
            headers=auth_headers,
            params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        assert response.json()["items"][0]["expense_minor"] == 10_000

    async def test_rejects_an_inverted_range(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            f"{REPORTS}/cash-flow",
            headers=auth_headers,
            params={"date_from": "2026-02-01", "date_to": "2026-01-01"},
        )

        assert response.status_code == 422

    async def test_rejects_a_window_longer_than_the_cap(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(
            f"{REPORTS}/cash-flow",
            headers=auth_headers,
            params={"date_from": "2015-01-01", "date_to": "2026-12-31"},
        )

        assert response.status_code == 422


class TestCategoryBreakdown:
    async def test_rolls_child_spending_into_the_parent(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        categories = await _categories(client, auth_headers)
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="90.00",
            occurred_on="2026-01-10",
            category_id=categories["Utilities"]["id"],
        )
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="10.00",
            occurred_on="2026-01-11",
            category_id=categories["Groceries"]["id"],
        )

        response = await client.get(
            f"{REPORTS}/category-breakdown",
            headers=auth_headers,
            params={
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
                "include_subcategories": True,
            },
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total_minor"] == 10_000
        names = {item["name"]: item for item in body["items"]}
        assert names["Housing"]["total_minor"] == 9_000
        assert names["Housing"]["percent_of_total"] == "90.00"
        assert names["Groceries"]["total_minor"] == 1_000

    async def test_can_report_direct_categories_only(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        categories = await _categories(client, auth_headers)
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="90.00",
            occurred_on="2026-01-10",
            category_id=categories["Utilities"]["id"],
        )

        response = await client.get(
            f"{REPORTS}/category-breakdown",
            headers=auth_headers,
            params={
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
                "include_subcategories": False,
            },
        )

        assert [item["name"] for item in response.json()["items"]] == ["Utilities"]

    async def test_reports_income_by_category(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        categories = await _categories(client, auth_headers)
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="income",
            amount="500.00",
            occurred_on="2026-01-05",
            category_id=categories["Salary"]["id"],
        )

        response = await client.get(
            f"{REPORTS}/category-breakdown",
            headers=auth_headers,
            params={
                "kind": "income",
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
            },
        )

        assert response.status_code == 200
        assert response.json()["kind"] == "income"
        assert response.json()["items"][0]["name"] == "Salary"
        assert response.json()["items"][0]["percent_of_total"] == "100.00"

    async def test_includes_uncategorized_spending(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="25.00",
            occurred_on="2026-01-10",
        )

        response = await client.get(
            f"{REPORTS}/category-breakdown",
            headers=auth_headers,
            params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        assert response.json()["items"][0]["name"] == "Uncategorized"
        assert response.json()["items"][0]["category_id"] is None


class TestCsvExport:
    async def test_exports_a_csv_with_a_stable_header(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="24.99",
            occurred_on="2026-01-15",
            description="Weekly shop",
        )

        response = await client.get(
            f"{REPORTS}/transactions.csv",
            headers=auth_headers,
            params={"date_from": "2026-01-01", "date_to": "2026-01-31"},
        )

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/csv")
        assert "attachment" in response.headers["content-disposition"]
        lines = response.text.strip().splitlines()
        assert lines[0].startswith("occurred_on,transaction_type,account,category")
        assert len(lines) == 2
        assert "24.99" in lines[1]
        assert "Weekly shop" in lines[1]

    async def test_neutralises_spreadsheet_formulas(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="1.00",
            occurred_on="2026-01-15",
            description='=HYPERLINK("http://evil.test")',
        )

        response = await client.get(f"{REPORTS}/transactions.csv", headers=auth_headers)

        assert "'=HYPERLINK" in response.text

    async def test_exports_without_a_date_filter(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
    ) -> None:
        await _transaction(
            client,
            auth_headers,
            account_id=account["id"],
            transaction_type="expense",
            amount="5.00",
            occurred_on="2025-12-31",
        )

        response = await client.get(f"{REPORTS}/transactions.csv", headers=auth_headers)

        assert response.status_code == 200
        assert "2025-12-31" in response.text

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        assert (await client.get(f"{REPORTS}/transactions.csv")).status_code == 401
