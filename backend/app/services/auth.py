"""Authentication service: registration, login, token rotation, logout."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AuthenticationError, ConflictError
from app.core.security import (
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_refresh_token,
    password_needs_rehash,
    verify_password,
)
from app.db.models import Category, RefreshToken, User
from app.domain.categories import DEFAULT_CATEGORIES
from app.schemas.auth import RegisterRequest


def normalise_email(email: str) -> str:
    """Emails are matched case-insensitively; the local part is lowercased too.

    Strictly, the local part is case-sensitive per RFC 5321, but no real
    provider treats it that way and users expect their address to work in any
    case. Normalising avoids duplicate accounts for the same person.
    """
    return email.strip().lower()


async def register_user(session: AsyncSession, payload: RegisterRequest) -> User:
    email = normalise_email(payload.email)

    existing = await session.scalar(select(User).where(User.email == email))
    if existing is not None:
        raise ConflictError("An account with that email already exists")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name.strip(),
        base_currency=payload.base_currency,
    )
    session.add(user)
    await session.flush()

    _seed_default_categories(session, user)
    await session.commit()
    await session.refresh(user)
    return user


def _seed_default_categories(session: AsyncSession, user: User) -> None:
    """Give a new user a usable starting set of categories."""
    for name, kind, children in DEFAULT_CATEGORIES:
        parent = Category(user_id=user.id, name=name, kind=kind, parent_id=None)
        session.add(parent)
        for child_name in children:
            session.add(Category(user_id=user.id, name=child_name, kind=kind, parent=parent))


async def authenticate_user(session: AsyncSession, email: str, password: str) -> User:
    """Verify credentials, returning the user or raising AuthenticationError.

    The same error is raised for an unknown email and a wrong password so the
    endpoint cannot be used to enumerate registered addresses.
    """
    user = await session.scalar(select(User).where(User.email == normalise_email(email)))

    if user is None:
        # Hash anyway so the response time does not reveal whether the account
        # exists (timing-based enumeration).
        hash_password(password)
        raise AuthenticationError("Incorrect email or password")

    if not verify_password(password, user.password_hash):
        raise AuthenticationError("Incorrect email or password")

    if not user.is_active:
        raise AuthenticationError("This account is disabled")

    # Transparently upgrade hashes when Argon2 parameters change.
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        await session.commit()

    return user


async def issue_tokens(session: AsyncSession, user: User) -> tuple[str, str]:
    """Issue an access token and a persisted refresh token."""
    settings = get_settings()
    access_token = create_access_token(user.id)
    refresh_token, token_id = create_refresh_token(user.id)

    session.add(
        RefreshToken(
            id=token_id,
            user_id=user.id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    await session.commit()
    return access_token, refresh_token


async def rotate_refresh_token(session: AsyncSession, token: str) -> tuple[str, str]:
    """Exchange a refresh token for a new token pair.

    The presented token is revoked as part of the exchange, so replaying it
    fails -- a stolen token is usable at most once, and only before the
    legitimate client refreshes.
    """
    try:
        claims = decode_token(token, expected_type=TokenType.REFRESH)
    except Exception as exc:
        raise AuthenticationError("Invalid refresh token") from exc

    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored is None or stored.revoked_at is not None:
        raise AuthenticationError("Invalid refresh token")

    if stored.expires_at <= datetime.now(UTC):
        raise AuthenticationError("Refresh token has expired")

    user = await session.get(User, claims.subject)
    if user is None or not user.is_active:
        raise AuthenticationError("Invalid refresh token")

    settings = get_settings()
    access_token = create_access_token(user.id)
    new_token, new_token_id = create_refresh_token(user.id)

    # The replacement row must exist before the old row can point at it, so
    # flush the INSERT before setting the self-referential FK.
    session.add(
        RefreshToken(
            id=new_token_id,
            user_id=user.id,
            token_hash=hash_refresh_token(new_token),
            expires_at=datetime.now(UTC) + timedelta(seconds=settings.refresh_token_ttl_seconds),
        )
    )
    await session.flush()

    stored.revoked_at = datetime.now(UTC)
    stored.replaced_by_id = new_token_id
    await session.commit()
    return access_token, new_token


async def revoke_refresh_token(session: AsyncSession, token: str) -> None:
    """Revoke a refresh token. Silent when the token is unknown or expired."""
    stored = await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if stored is not None and stored.revoked_at is None:
        stored.revoked_at = datetime.now(UTC)
        await session.commit()


async def revoke_all_user_tokens(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every active refresh token for a user (password change, etc.)."""
    tokens = await session.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    now = datetime.now(UTC)
    for stored in tokens:
        stored.revoked_at = now
    await session.commit()


async def count_active_tokens(session: AsyncSession, user_id: uuid.UUID) -> int:
    result = await session.scalar(
        select(func.count())
        .select_from(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    )
    return int(result or 0)
