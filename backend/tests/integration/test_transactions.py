"""Transaction CRUD and double-entry transfers."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

TRANSACTIONS = "/api/v1/transactions"
TRANSFERS = "/api/v1/transactions/transfers"


@pytest.fixture
async def second_account(client: AsyncClient, auth_headers: dict[str, str]) -> dict[str, object]:
    response = await client.post(
        "/api/v1/accounts",
        headers=auth_headers,
        json={
            "name": "Savings Account",
            "account_type": "savings",
            "currency": "GBP",
            "opening_balance": "0.00",
        },
    )
    result: dict[str, object] = response.json()
    return result


class TestCreateTransaction:
    async def test_records_an_expense(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "24.99",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
                "description": "Weekly shop",
            },
        )

        assert response.status_code == 201
        assert response.json()["amount_minor"] == 2_499

    async def test_records_income(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "income",
                "amount": "3200.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 201
        assert response.json()["transaction_type"] == "income"

    async def test_rejects_a_zero_amount(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "0",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_negative_amount(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "-50.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_currency_mismatch_with_the_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """A GBP account cannot hold an NGN transaction."""
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "1000.00",
                "currency": "NGN",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 422

    async def test_cannot_post_to_another_users_account(
        self,
        client: AsyncClient,
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        response = await client.post(
            TRANSACTIONS,
            headers=other_user_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 404

    async def test_transfer_type_is_rejected_on_this_endpoint(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """Transfers must go through the dedicated endpoint to stay paired."""
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "transfer",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 422


class TestTransfers:
    async def test_creates_two_linked_legs(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        second_account: dict[str, object],
    ) -> None:
        response = await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": second_account["id"],
                "amount": "250.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        assert response.status_code == 201
        assert len(response.json()["legs"]) == 2

    async def test_moves_money_without_creating_or_destroying_it(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        second_account: dict[str, object],
    ) -> None:
        """1000.00 - 250.00 = 750.00 here, 0.00 + 250.00 = 250.00 there."""
        await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": second_account["id"],
                "amount": "250.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        source = await client.get(f"/api/v1/accounts/{account['id']}/balance", headers=auth_headers)
        destination = await client.get(
            f"/api/v1/accounts/{second_account['id']}/balance", headers=auth_headers
        )

        assert source.json()["balance_minor"] == 75_000
        assert destination.json()["balance_minor"] == 25_000

    async def test_rejects_a_transfer_to_the_same_account(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": account["id"],
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        assert response.status_code == 422

    async def test_rejects_a_cross_currency_transfer(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """Deferred to Phase 4, when exchange rates exist."""
        naira = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"name": "Naira", "account_type": "savings", "currency": "NGN"},
        )

        response = await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": naira.json()["id"],
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        assert response.status_code == 422

    async def test_cannot_transfer_into_another_users_account(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        theirs = await client.post(
            "/api/v1/accounts",
            headers=other_user_headers,
            json={"name": "Their Account", "account_type": "cash", "currency": "GBP"},
        )

        response = await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": theirs.json()["id"],
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        assert response.status_code == 404

    async def test_a_failed_transfer_leaves_no_partial_legs(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        """Atomicity: half a transfer would corrupt the ledger."""
        theirs = await client.post(
            "/api/v1/accounts",
            headers=other_user_headers,
            json={"name": "Their Account", "account_type": "cash", "currency": "GBP"},
        )

        await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": theirs.json()["id"],
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        balance = await client.get(
            f"/api/v1/accounts/{account['id']}/balance", headers=auth_headers
        )
        assert balance.json()["balance_minor"] == 100_000


class TestListTransactions:
    async def test_lists_only_the_callers_transactions(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        response = await client.get(TRANSACTIONS, headers=other_user_headers)

        assert response.json()["items"] == []

    async def test_filters_by_account(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        second_account: dict[str, object],
    ) -> None:
        await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        response = await client.get(
            f"{TRANSACTIONS}?account_id={second_account['id']}", headers=auth_headers
        )

        assert response.json()["items"] == []

    async def test_filters_by_date_range(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        inside = await client.get(
            f"{TRANSACTIONS}?date_from=2026-01-01&date_to=2026-12-31", headers=auth_headers
        )
        outside = await client.get(
            f"{TRANSACTIONS}?date_from=2025-01-01&date_to=2025-12-31", headers=auth_headers
        )

        assert len(inside.json()["items"]) == 1
        assert outside.json()["items"] == []


class TestUpdateAndDelete:
    async def test_updates_a_transaction(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        created = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "24.99",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        response = await client.patch(
            f"{TRANSACTIONS}/{created.json()['id']}",
            headers=auth_headers,
            json={"description": "Corrected description"},
        )

        assert response.status_code == 200
        assert response.json()["description"] == "Corrected description"

    async def test_deletes_a_transaction(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        created = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "24.99",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        response = await client.delete(
            f"{TRANSACTIONS}/{created.json()['id']}", headers=auth_headers
        )

        assert response.status_code == 204

    async def test_deleting_a_transfer_leg_removes_both_legs(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        second_account: dict[str, object],
    ) -> None:
        """Leaving one orphaned leg would unbalance the ledger."""
        transfer = await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": second_account["id"],
                "amount": "250.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )
        leg_id = transfer.json()["legs"][0]["id"]

        await client.delete(f"{TRANSACTIONS}/{leg_id}", headers=auth_headers)

        remaining = await client.get(TRANSACTIONS, headers=auth_headers)
        assert remaining.json()["items"] == []

    async def test_cannot_delete_another_users_transaction(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        created = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "24.99",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        response = await client.delete(
            f"{TRANSACTIONS}/{created.json()['id']}", headers=other_user_headers
        )

        assert response.status_code == 404

    async def test_unknown_transaction_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.delete(f"{TRANSACTIONS}/{uuid.uuid4()}", headers=auth_headers)

        assert response.status_code == 404


class TestSignedAmounts:
    async def test_income_is_signed_positive(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "income",
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.json()["signed_amount_minor"] == 10_000

    async def test_expense_is_signed_negative(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            TRANSACTIONS,
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.json()["signed_amount_minor"] == -10_000

    async def test_transfer_legs_are_exposed_with_direction(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        second_account: dict[str, object],
    ) -> None:
        """The client must be able to tell which leg is the debit."""
        response = await client.post(
            TRANSFERS,
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": second_account["id"],
                "amount": "250.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        signed = [leg["signed_amount_minor"] for leg in response.json()["legs"]]
        assert sorted(signed) == [-25_000, 25_000]
