"""Password hashing and JWT issuance/verification.

Argon2id for passwords, short-lived JWT access tokens, and rotating refresh
tokens whose *hashes* are what get persisted -- a database leak must not hand
an attacker usable tokens (plan Section 10).
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Final

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, VerifyMismatchError

from app.core.config import get_settings

ALGORITHM: Final = "HS256"

_password_hasher = PasswordHasher()


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenError(Exception):
    """Base class for token failures."""


class InvalidTokenError(TokenError):
    """Signature, structure, or token type did not match expectations."""


class ExpiredTokenError(TokenError):
    """The token was well-formed but is past its expiry."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    subject: uuid.UUID
    token_type: TokenType
    token_id: uuid.UUID
    expires_at: datetime


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password, failing closed on any hashing error."""
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, Argon2Error, ValueError):
        return False


def password_needs_rehash(password_hash: str) -> bool:
    """True when the stored hash used weaker parameters than current policy."""
    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except (Argon2Error, ValueError):
        return False


def _create_token(
    subject: uuid.UUID,
    token_type: TokenType,
    expires_in: timedelta,
) -> tuple[str, uuid.UUID]:
    settings = get_settings()
    now = datetime.now(UTC)
    token_id = uuid.uuid4()

    payload = {
        "sub": str(subject),
        "typ": token_type.value,
        "jti": str(token_id),
        "iat": int(now.timestamp()),
        "exp": int((now + expires_in).timestamp()),
    }
    token = jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm=ALGORITHM)
    return token, token_id


def create_access_token(subject: uuid.UUID, expires_in: timedelta | None = None) -> str:
    ttl = expires_in or timedelta(seconds=get_settings().access_token_ttl_seconds)
    token, _ = _create_token(subject, TokenType.ACCESS, ttl)
    return token


def create_refresh_token(
    subject: uuid.UUID, expires_in: timedelta | None = None
) -> tuple[str, uuid.UUID]:
    """Return the refresh token and its id, which the caller persists (hashed)."""
    ttl = expires_in or timedelta(seconds=get_settings().refresh_token_ttl_seconds)
    return _create_token(subject, TokenType.REFRESH, ttl)


def decode_token(token: str, expected_type: TokenType) -> TokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[ALGORITHM],
            options={"require": ["sub", "typ", "jti", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise ExpiredTokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError("Token could not be decoded") from exc

    # Checked explicitly so a refresh token can never authenticate a request.
    if payload.get("typ") != expected_type.value:
        raise InvalidTokenError(
            f"Expected a {expected_type.value} token, got {payload.get('typ')!r}"
        )

    try:
        subject = uuid.UUID(payload["sub"])
        token_id = uuid.UUID(payload["jti"])
    except (KeyError, ValueError, AttributeError) as exc:
        raise InvalidTokenError("Token claims are malformed") from exc

    return TokenClaims(
        subject=subject,
        token_type=expected_type,
        token_id=token_id,
        expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
    )


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token for storage and lookup.

    SHA-256 rather than Argon2: the token is already high-entropy random data,
    so slow hashing buys nothing, and lookup needs to be deterministic.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
