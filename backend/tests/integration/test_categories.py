"""Category CRUD, hierarchy rules and ownership isolation."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

CATEGORIES = "/api/v1/categories"


class TestCreateCategory:
    async def test_creates_a_root_category(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Holidays", "kind": "expense"}
        )

        assert response.status_code == 201
        assert response.json()["parent_id"] is None

    async def test_creates_a_child_category(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        parent = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Hobbies", "kind": "expense"}
        )

        response = await client.post(
            CATEGORIES,
            headers=auth_headers,
            json={"name": "Cycling", "kind": "expense", "parent_id": parent.json()["id"]},
        )

        assert response.status_code == 201
        assert response.json()["parent_id"] == parent.json()["id"]

    async def test_rejects_a_parent_owned_by_another_user(
        self, client: AsyncClient, auth_headers: dict[str, str], other_user_headers: dict[str, str]
    ) -> None:
        theirs = await client.post(
            CATEGORIES, headers=other_user_headers, json={"name": "Theirs", "kind": "expense"}
        )

        response = await client.post(
            CATEGORIES,
            headers=auth_headers,
            json={"name": "Mine", "kind": "expense", "parent_id": theirs.json()["id"]},
        )

        assert response.status_code == 404

    async def test_rejects_a_duplicate_name_under_the_same_parent(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Holidays", "kind": "expense"}
        )

        response = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Holidays", "kind": "expense"}
        )

        assert response.status_code == 409

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.post(CATEGORIES, json={"name": "X", "kind": "expense"})

        assert response.status_code == 401


class TestListCategories:
    async def test_returns_the_seeded_defaults(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get(CATEGORIES, headers=auth_headers)

        assert response.status_code == 200
        assert len(response.json()["items"]) > 0

    async def test_does_not_leak_other_users_categories(
        self, client: AsyncClient, auth_headers: dict[str, str], other_user_headers: dict[str, str]
    ) -> None:
        mine = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Private", "kind": "expense"}
        )

        response = await client.get(CATEGORIES, headers=other_user_headers)

        ids = [item["id"] for item in response.json()["items"]]
        assert mine.json()["id"] not in ids

    async def test_filters_by_kind(self, client: AsyncClient, auth_headers: dict[str, str]) -> None:
        response = await client.get(f"{CATEGORIES}?kind=income", headers=auth_headers)

        kinds = {item["kind"] for item in response.json()["items"]}
        assert kinds <= {"income"}


class TestUpdateCategory:
    async def test_renames_a_category(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        created = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Misc", "kind": "expense"}
        )

        response = await client.patch(
            f"{CATEGORIES}/{created.json()['id']}",
            headers=auth_headers,
            json={"name": "Miscellaneous"},
        )

        assert response.status_code == 200
        assert response.json()["name"] == "Miscellaneous"

    async def test_rejects_making_a_category_its_own_parent(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        created = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Loop", "kind": "expense"}
        )
        category_id = created.json()["id"]

        response = await client.patch(
            f"{CATEGORIES}/{category_id}", headers=auth_headers, json={"parent_id": category_id}
        )

        assert response.status_code == 422

    async def test_rejects_reparenting_under_its_own_descendant(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        parent = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Top", "kind": "expense"}
        )
        child = await client.post(
            CATEGORIES,
            headers=auth_headers,
            json={"name": "Middle", "kind": "expense", "parent_id": parent.json()["id"]},
        )

        response = await client.patch(
            f"{CATEGORIES}/{parent.json()['id']}",
            headers=auth_headers,
            json={"parent_id": child.json()["id"]},
        )

        assert response.status_code == 422

    async def test_cannot_update_another_users_category(
        self, client: AsyncClient, auth_headers: dict[str, str], other_user_headers: dict[str, str]
    ) -> None:
        mine = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Mine", "kind": "expense"}
        )

        response = await client.patch(
            f"{CATEGORIES}/{mine.json()['id']}",
            headers=other_user_headers,
            json={"name": "Hijacked"},
        )

        assert response.status_code == 404


class TestDeleteCategory:
    async def test_deletes_a_category(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        created = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Temporary", "kind": "expense"}
        )

        response = await client.delete(f"{CATEGORIES}/{created.json()['id']}", headers=auth_headers)

        assert response.status_code == 204

    async def test_transactions_survive_their_category_being_deleted(
        self, client: AsyncClient, auth_headers: dict[str, str], account: dict[str, object]
    ) -> None:
        """Deleting a category must never delete financial records."""
        category = await client.post(
            CATEGORIES, headers=auth_headers, json={"name": "Doomed", "kind": "expense"}
        )
        transaction = await client.post(
            "/api/v1/transactions",
            headers=auth_headers,
            json={
                "account_id": account["id"],
                "category_id": category.json()["id"],
                "transaction_type": "expense",
                "amount": "12.00",
                "currency": "GBP",
                "occurred_on": "2026-03-01",
            },
        )

        await client.delete(f"{CATEGORIES}/{category.json()['id']}", headers=auth_headers)

        response = await client.get(
            f"/api/v1/transactions/{transaction.json()['id']}", headers=auth_headers
        )
        assert response.status_code == 200
        assert response.json()["category_id"] is None

    async def test_unknown_category_is_not_found(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.delete(f"{CATEGORIES}/{uuid.uuid4()}", headers=auth_headers)

        assert response.status_code == 404
