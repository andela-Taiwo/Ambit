"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AuthenticationError
from app.core.security import TokenError, TokenType, decode_token
from app.db.models import User
from app.db.session import get_session

# auto_error=False so a missing header raises our AuthenticationError (401 with
# a consistent body) rather than FastAPI's default 403.
_bearer_scheme = HTTPBearer(auto_error=False)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    if credentials is None:
        raise AuthenticationError("Not authenticated")

    try:
        claims = decode_token(credentials.credentials, expected_type=TokenType.ACCESS)
    except TokenError as exc:
        raise AuthenticationError(str(exc)) from exc

    user = await session.get(User, claims.subject)
    if user is None or not user.is_active:
        raise AuthenticationError("User no longer exists or is disabled")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
