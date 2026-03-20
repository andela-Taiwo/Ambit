"""Edge cases in the service layer that the happy-path CRUD tests miss."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.db.models import RefreshToken, User
from app.db.session import get_session
from app.services.auth import count_active_tokens, revoke_all_user_tokens

pytestmark = pytest.mark.integration


class TestTokenLifecycle:
    async def test_an_expired_refresh_token_is_rejected(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )
        token = login.cookies["refresh_token"]

        agen = get_session()
        session = await anext(agen)
        stored = await session.scalar(select(RefreshToken))
        assert stored is not None
        stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await session.commit()
        await agen.aclose()

        client.cookies.set("refresh_token", token, path="/api/v1/auth")
        response = await client.post("/api/v1/auth/refresh")

        assert response.status_code == 401

    async def test_revoking_all_tokens_ends_every_session(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        """Used on password change: every device is logged out."""
        login = await client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )
        token = login.cookies["refresh_token"]

        agen = get_session()
        session = await anext(agen)
        user = await session.scalar(select(User).where(User.email == registered_user["email"]))
        assert user is not None
        assert await count_active_tokens(session, user.id) == 1

        await revoke_all_user_tokens(session, user.id)
        assert await count_active_tokens(session, user.id) == 0
        await agen.aclose()

        client.cookies.set("refresh_token", token, path="/api/v1/auth")
        assert (await client.post("/api/v1/auth/refresh")).status_code == 401

    async def test_a_disabled_user_cannot_log_in(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        agen = get_session()
        session = await anext(agen)
        user = await session.scalar(select(User).where(User.email == registered_user["email"]))
        assert user is not None
        user.is_active = False
        await session.commit()
        await agen.aclose()

        response = await client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )

        assert response.status_code == 401

    async def test_a_disabled_user_cannot_use_an_existing_access_token(
        self, client: AsyncClient, auth_headers: dict[str, str], registered_user: dict[str, str]
    ) -> None:
        agen = get_session()
        session = await anext(agen)
        user = await session.scalar(select(User).where(User.email == registered_user["email"]))
        assert user is not None
        user.is_active = False
        await session.commit()
        await agen.aclose()

        response = await client.get("/api/v1/auth/me", headers=auth_headers)

        assert response.status_code == 401


class TestAccountEdges:
    async def test_renaming_to_an_existing_name_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        other = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"name": "Second", "account_type": "cash", "currency": "GBP"},
        )

        response = await client.patch(
            f"/api/v1/accounts/{other.json()['id']}",
            headers=auth_headers,
            json={"name": account["name"]},
        )

        assert response.status_code == 409

    async def test_renaming_to_its_own_name_is_allowed(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """A no-op rename must not trip the uniqueness check."""
        response = await client.patch(
            f"/api/v1/accounts/{account['id']}",
            headers=auth_headers,
            json={"name": account["name"]},
        )

        assert response.status_code == 200

    async def test_archiving_hides_an_account_from_the_default_list(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        await client.patch(
            f"/api/v1/accounts/{account['id']}",
            headers=auth_headers,
            json={"is_archived": True},
        )

        default = await client.get("/api/v1/accounts", headers=auth_headers)
        included = await client.get("/api/v1/accounts?include_archived=true", headers=auth_headers)

        assert default.json()["items"] == []
        assert len(included.json()["items"]) == 1

    async def test_changing_the_account_type_is_allowed(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.patch(
            f"/api/v1/accounts/{account['id']}",
            headers=auth_headers,
            json={"account_type": "savings"},
        )

        assert response.json()["account_type"] == "savings"

    async def test_balance_of_another_users_account_is_not_found(
        self,
        client: AsyncClient,
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        response = await client.get(
            f"/api/v1/accounts/{account['id']}/balance", headers=other_user_headers
        )

        assert response.status_code == 404


class TestCategoryEdges:
    async def test_archiving_hides_a_category_from_the_default_list(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        created = await client.post(
            "/api/v1/categories", headers=auth_headers, json={"name": "Temp", "kind": "expense"}
        )

        await client.patch(
            f"/api/v1/categories/{created.json()['id']}",
            headers=auth_headers,
            json={"is_archived": True},
        )

        default = await client.get("/api/v1/categories", headers=auth_headers)
        ids = [item["id"] for item in default.json()["items"]]

        assert created.json()["id"] not in ids

    async def test_renaming_a_child_to_a_sibling_name_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        parent = await client.post(
            "/api/v1/categories", headers=auth_headers, json={"name": "Parent", "kind": "expense"}
        )
        parent_id = parent.json()["id"]
        await client.post(
            "/api/v1/categories",
            headers=auth_headers,
            json={"name": "First", "kind": "expense", "parent_id": parent_id},
        )
        second = await client.post(
            "/api/v1/categories",
            headers=auth_headers,
            json={"name": "Second", "kind": "expense", "parent_id": parent_id},
        )

        response = await client.patch(
            f"/api/v1/categories/{second.json()['id']}",
            headers=auth_headers,
            json={"name": "First"},
        )

        assert response.status_code == 409

    async def test_the_same_name_is_allowed_under_different_parents(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        """`Transport > Insurance` and `Home > Insurance` must both be valid."""
        first = await client.post(
            "/api/v1/categories", headers=auth_headers, json={"name": "AAA", "kind": "expense"}
        )
        second = await client.post(
            "/api/v1/categories", headers=auth_headers, json={"name": "BBB", "kind": "expense"}
        )

        await client.post(
            "/api/v1/categories",
            headers=auth_headers,
            json={"name": "Insurance", "kind": "expense", "parent_id": first.json()["id"]},
        )
        response = await client.post(
            "/api/v1/categories",
            headers=auth_headers,
            json={"name": "Insurance", "kind": "expense", "parent_id": second.json()["id"]},
        )

        assert response.status_code == 201

    async def test_exceeding_the_nesting_depth_is_rejected(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        parent_id: str | None = None
        last_status = 201

        for level in range(6):
            payload: dict[str, object] = {"name": f"Level {level}", "kind": "expense"}
            if parent_id is not None:
                payload["parent_id"] = parent_id
            response = await client.post("/api/v1/categories", headers=auth_headers, json=payload)
            last_status = response.status_code
            if last_status != 201:
                break
            parent_id = response.json()["id"]

        assert last_status == 422

    async def test_get_unknown_category_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(f"/api/v1/categories/{uuid.uuid4()}", headers=auth_headers)

        assert response.status_code == 404


class TestTransactionEdges:
    async def test_rejects_an_unknown_category(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        response = await client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": str(uuid.uuid4()),
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 404

    async def test_rejects_a_category_owned_by_another_user(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        theirs = await client.post(
            "/api/v1/categories",
            headers=other_user_headers,
            json={"name": "Theirs", "kind": "expense"},
        )

        response = await client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": theirs.json()["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        assert response.status_code == 404

    async def test_updating_the_amount_updates_the_balance(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """1000.00 - 100.00 = 900.00, then corrected to -250.00 = 750.00."""
        created = await client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        await client.patch(
            f"/api/v1/transactions/{created.json()['id']}",
            headers=auth_headers,
            json={"amount": "250.00"},
        )

        balance = await client.get(
            f"/api/v1/accounts/{account['id']}/balance", headers=auth_headers
        )
        assert balance.json()["balance_minor"] == 75_000

    async def test_a_transfer_leg_cannot_be_edited(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        second = await client.post(
            "/api/v1/accounts",
            headers=auth_headers,
            json={"name": "Destination", "account_type": "savings", "currency": "GBP"},
        )
        transfer = await client.post(
            "/api/v1/transactions/transfers",
            headers=auth_headers,
            json={
                "from_account_id": account["id"],
                "to_account_id": second.json()["id"],
                "amount": "100.00",
                "currency": "GBP",
                "occurred_on": "2026-02-05",
            },
        )

        response = await client.patch(
            f"/api/v1/transactions/{transfer.json()['legs'][0]['id']}",
            headers=auth_headers,
            json={"description": "tampered"},
        )

        assert response.status_code == 422

    async def test_updates_occurred_on_and_notes(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        created = await client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        response = await client.patch(
            f"/api/v1/transactions/{created.json()['id']}",
            headers=auth_headers,
            json={"occurred_on": "2026-03-09", "notes": "Reconciled"},
        )

        assert response.json()["occurred_on"] == "2026-03-09"
        assert response.json()["notes"] == "Reconciled"

    async def test_assigning_a_category_on_update(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        created = await client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )
        category = await client.post(
            "/api/v1/categories",
            headers=auth_headers,
            json={"name": "Assigned", "kind": "expense"},
        )

        response = await client.patch(
            f"/api/v1/transactions/{created.json()['id']}",
            headers=auth_headers,
            json={"category_id": category.json()["id"]},
        )

        assert response.json()["category_id"] == category.json()["id"]

    async def test_filters_by_transaction_type(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        for tx_type, amount in (("income", "500.00"), ("expense", "20.00")):
            await client.post(
                "/api/v1/transactions",
                headers=auth_headers,
                json={
                    "account_id": account["id"],
                    "transaction_type": tx_type,
                    "amount": amount,
                    "currency": "GBP",
                    "occurred_on": "2026-02-01",
                },
            )

        response = await client.get(
            "/api/v1/transactions?transaction_type=income", headers=auth_headers
        )

        items = response.json()["items"]
        assert len(items) == 1
        assert items[0]["transaction_type"] == "income"

    async def test_filters_by_category(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        category = await client.post(
            "/api/v1/categories",
            headers=auth_headers,
            json={"name": "Filtered", "kind": "expense"},
        )
        await client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category.json()["id"],
                "transaction_type": "expense",
                "amount": "10.00",
                "currency": "GBP",
                "occurred_on": "2026-02-01",
            },
        )

        response = await client.get(
            f"/api/v1/transactions?category_id={category.json()['id']}", headers=auth_headers
        )

        assert len(response.json()["items"]) == 1

    async def test_another_users_transaction_is_not_found(
        self,
        client: AsyncClient,
        auth_headers: dict[str, str],
        account: dict[str, object],
        other_user_headers: dict[str, str],
    ) -> None:
        created = await client.post(
            "/api/v1/transactions",
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
            f"/api/v1/transactions/{created.json()['id']}", headers=other_user_headers
        )

        assert response.status_code == 404
