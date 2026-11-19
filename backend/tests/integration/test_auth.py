"""Auth endpoints: register, login, refresh, logout, me."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
ME = "/api/v1/auth/me"


class TestRegister:
    async def test_registers_a_new_user(
        self, client: AsyncClient, user_payload: dict[str, str]
    ) -> None:
        response = await client.post(REGISTER, json=user_payload)

        assert response.status_code == 201
        body = response.json()
        assert body["email"] == user_payload["email"]
        assert body["display_name"] == user_payload["display_name"]

    async def test_never_returns_the_password_or_its_hash(
        self, client: AsyncClient, user_payload: dict[str, str]
    ) -> None:
        response = await client.post(REGISTER, json=user_payload)

        assert "password" not in response.text
        assert "password_hash" not in response.json()

    async def test_seeds_default_categories_for_the_new_user(
        self, client: AsyncClient, auth_headers: dict[str, str]
    ) -> None:
        response = await client.get("/api/v1/categories", headers=auth_headers)

        names = {item["name"] for item in response.json()["items"]}
        assert "Groceries" in names
        assert "Transport" in names

    async def test_duplicate_email_is_rejected(
        self, client: AsyncClient, user_payload: dict[str, str]
    ) -> None:
        await client.post(REGISTER, json=user_payload)
        response = await client.post(REGISTER, json=user_payload)

        assert response.status_code == 409

    async def test_email_is_matched_case_insensitively(
        self, client: AsyncClient, user_payload: dict[str, str]
    ) -> None:
        await client.post(REGISTER, json=user_payload)
        response = await client.post(
            REGISTER, json={**user_payload, "email": user_payload["email"].upper()}
        )

        assert response.status_code == 409

    async def test_rejects_a_short_password(
        self, client: AsyncClient, user_payload: dict[str, str]
    ) -> None:
        response = await client.post(REGISTER, json={**user_payload, "password": "short"})

        assert response.status_code == 422

    async def test_rejects_a_malformed_email(
        self, client: AsyncClient, user_payload: dict[str, str]
    ) -> None:
        response = await client.post(REGISTER, json={**user_payload, "email": "not-an-email"})

        assert response.status_code == 422

    async def test_rejects_an_unsupported_base_currency(
        self, client: AsyncClient, user_payload: dict[str, str]
    ) -> None:
        response = await client.post(REGISTER, json={**user_payload, "base_currency": "XYZ"})

        assert response.status_code == 422


class TestLogin:
    async def test_returns_an_access_token(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        response = await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )

        assert response.status_code == 200
        assert response.json()["access_token"]
        assert response.json()["token_type"] == "bearer"

    async def test_sets_the_refresh_token_as_an_httponly_cookie(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        """The refresh token must never be readable by JavaScript."""
        response = await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )

        # Cookie attribute names/values are case-insensitive (RFC 6265).
        set_cookie = response.headers["set-cookie"].lower()
        assert "refresh_token=" in set_cookie
        assert "httponly" in set_cookie
        assert "samesite=lax" in set_cookie or "samesite=strict" in set_cookie

    async def test_refresh_token_is_not_in_the_response_body(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        response = await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )

        assert "refresh_token" not in response.json()

    async def test_wrong_password_is_rejected(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        response = await client.post(
            LOGIN, json={"email": registered_user["email"], "password": "wrong-password-entirely"}
        )

        assert response.status_code == 401

    async def test_unknown_email_is_rejected_with_the_same_error(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        """Identical response prevents email enumeration."""
        wrong_password = await client.post(
            LOGIN, json={"email": registered_user["email"], "password": "wrong-password-entirely"}
        )
        unknown_email = await client.post(
            LOGIN, json={"email": "nobody@example.com", "password": "wrong-password-entirely"}
        )

        assert unknown_email.status_code == wrong_password.status_code == 401
        assert unknown_email.json() == wrong_password.json()

    async def test_login_is_case_insensitive_on_email(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        response = await client.post(
            LOGIN,
            json={
                "email": registered_user["email"].upper(),
                "password": registered_user["password"],
            },
        )

        assert response.status_code == 200


class TestMe:
    async def test_returns_the_authenticated_user(
        self, client: AsyncClient, auth_headers: dict[str, str], registered_user: dict[str, str]
    ) -> None:
        response = await client.get(ME, headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["email"] == registered_user["email"]

    async def test_requires_authentication(self, client: AsyncClient) -> None:
        response = await client.get(ME)

        assert response.status_code == 401

    async def test_rejects_a_garbage_token(self, client: AsyncClient) -> None:
        response = await client.get(ME, headers={"Authorization": "Bearer not-a-real-token"})

        assert response.status_code == 401


class TestRefresh:
    async def test_issues_a_new_access_token(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )

        response = await client.post(REFRESH)

        assert response.status_code == 200
        assert response.json()["access_token"]

    async def test_rotates_the_refresh_token(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        login = await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )
        original_cookie = login.cookies["refresh_token"]

        refresh = await client.post(REFRESH)

        assert refresh.cookies["refresh_token"] != original_cookie

    async def test_a_reused_refresh_token_is_rejected(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        """Replay detection: the old token must die when it is rotated."""
        login = await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )
        stolen = login.cookies["refresh_token"]

        await client.post(REFRESH)  # rotates, invalidating `stolen`

        client.cookies.set("refresh_token", stolen, path="/api/v1/auth")
        response = await client.post(REFRESH)

        assert response.status_code == 401

    async def test_requires_a_refresh_cookie(self, client: AsyncClient) -> None:
        response = await client.post(REFRESH)

        assert response.status_code == 401

    async def test_an_access_token_cannot_be_used_to_refresh(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        login = await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )
        access_token = login.json()["access_token"]

        client.cookies.set("refresh_token", access_token, path="/api/v1/auth")
        response = await client.post(REFRESH)

        assert response.status_code == 401


class TestLogout:
    async def test_clears_the_refresh_cookie(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )

        response = await client.post(LOGOUT)

        assert response.status_code == 204

    async def test_the_refresh_token_stops_working_after_logout(
        self, client: AsyncClient, registered_user: dict[str, str]
    ) -> None:
        login = await client.post(
            LOGIN,
            json={"email": registered_user["email"], "password": registered_user["password"]},
        )
        token = login.cookies["refresh_token"]

        await client.post(LOGOUT)

        client.cookies.set("refresh_token", token, path="/api/v1/auth")
        response = await client.post(REFRESH)
        assert response.status_code == 401

    async def test_logout_without_a_session_is_still_successful(self, client: AsyncClient) -> None:
        """Logout is idempotent -- it must never error."""
        response = await client.post(LOGOUT)

        assert response.status_code == 204
