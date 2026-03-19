"""Password hashing and JWT issuance/verification (plan Section 10)."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from app.core.security import (
    ExpiredTokenError,
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_is_not_the_plaintext(self) -> None:
        assert hash_password("correct horse battery staple") != "correct horse battery staple"

    def test_uses_argon2(self) -> None:
        assert hash_password("s3cret-password").startswith("$argon2")

    def test_correct_password_verifies(self) -> None:
        assert verify_password("s3cret-password", hash_password("s3cret-password")) is True

    def test_wrong_password_does_not_verify(self) -> None:
        assert verify_password("wrong-password", hash_password("s3cret-password")) is False

    def test_hashes_are_salted_so_identical_passwords_differ(self) -> None:
        assert hash_password("same-password") != hash_password("same-password")

    def test_malformed_hash_does_not_verify(self) -> None:
        """A corrupt stored hash must fail closed, not raise."""
        assert verify_password("any-password", "not-a-real-hash") is False


class TestAccessTokens:
    def test_round_trips_the_subject(self) -> None:
        user_id = uuid.uuid4()
        claims = decode_token(create_access_token(user_id), expected_type=TokenType.ACCESS)

        assert claims.subject == user_id

    def test_carries_the_access_token_type(self) -> None:
        claims = decode_token(create_access_token(uuid.uuid4()), expected_type=TokenType.ACCESS)

        assert claims.token_type is TokenType.ACCESS

    def test_has_a_unique_id_per_token(self) -> None:
        user_id = uuid.uuid4()
        first = decode_token(create_access_token(user_id), expected_type=TokenType.ACCESS)
        second = decode_token(create_access_token(user_id), expected_type=TokenType.ACCESS)

        assert first.token_id != second.token_id

    def test_expired_token_is_rejected(self) -> None:
        token = create_access_token(uuid.uuid4(), expires_in=timedelta(seconds=-1))

        with pytest.raises(ExpiredTokenError):
            decode_token(token, expected_type=TokenType.ACCESS)

    def test_tampered_token_is_rejected(self) -> None:
        token = create_access_token(uuid.uuid4())

        with pytest.raises(InvalidTokenError):
            decode_token(token + "tampered", expected_type=TokenType.ACCESS)

    def test_garbage_is_rejected(self) -> None:
        with pytest.raises(InvalidTokenError):
            decode_token("not.a.jwt", expected_type=TokenType.ACCESS)


class TestRefreshTokens:
    def test_round_trips_the_subject(self) -> None:
        user_id = uuid.uuid4()
        token, _ = create_refresh_token(user_id)
        claims = decode_token(token, expected_type=TokenType.REFRESH)

        assert claims.subject == user_id

    def test_returns_the_token_id_for_persistence(self) -> None:
        _, token_id = create_refresh_token(uuid.uuid4())

        assert isinstance(token_id, uuid.UUID)

    def test_a_refresh_token_is_not_accepted_as_an_access_token(self) -> None:
        """Token confusion: a refresh token must never authenticate a request."""
        token, _ = create_refresh_token(uuid.uuid4())

        with pytest.raises(InvalidTokenError):
            decode_token(token, expected_type=TokenType.ACCESS)

    def test_an_access_token_is_not_accepted_as_a_refresh_token(self) -> None:
        token = create_access_token(uuid.uuid4())

        with pytest.raises(InvalidTokenError):
            decode_token(token, expected_type=TokenType.REFRESH)

    def test_refresh_tokens_are_stored_hashed_not_plaintext(self) -> None:
        token, _ = create_refresh_token(uuid.uuid4())

        assert hash_refresh_token(token) != token

    def test_refresh_token_hash_is_deterministic_for_lookup(self) -> None:
        token, _ = create_refresh_token(uuid.uuid4())

        assert hash_refresh_token(token) == hash_refresh_token(token)
