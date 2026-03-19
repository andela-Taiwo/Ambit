"""Authentication routes.

The refresh token travels only in a Secure, httpOnly, SameSite cookie so
JavaScript -- and therefore any XSS payload -- cannot read it. The access token
is returned in the body for the client to hold in memory.
"""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import CurrentUser, SessionDep
from app.core.config import get_settings
from app.core.errors import AuthenticationError
from app.core.logging import get_logger
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.schemas.common import CONFLICT, UNAUTHORISED
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)

REFRESH_COOKIE_NAME: Final = "refresh_token"
#: Scoped to the refresh/logout routes so the cookie is not attached to every
#: API call, limiting its exposure.
REFRESH_COOKIE_PATH: Final = "/api/v1/auth"


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        # Secure is disabled locally so the cookie works over plain HTTP in
        # development; every deployed environment is HTTPS-only.
        secure=settings.app_env not in ("local", "test"),
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses=CONFLICT,
)
async def register(session: SessionDep, payload: RegisterRequest) -> UserResponse:
    user = await auth_service.register_user(session, payload)
    logger.info("user_registered", user_id=str(user.id))
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse, summary="Log in", responses=UNAUTHORISED)
async def login(session: SessionDep, payload: LoginRequest, response: Response) -> TokenResponse:
    user = await auth_service.authenticate_user(session, payload.email, payload.password)
    access_token, refresh_token = await auth_service.issue_tokens(session, user)

    _set_refresh_cookie(response, refresh_token)
    logger.info("user_logged_in", user_id=str(user.id))

    return TokenResponse(
        access_token=access_token,
        expires_in=get_settings().access_token_ttl_seconds,
    )


@router.post(
    "/refresh", response_model=TokenResponse, summary="Rotate tokens", responses=UNAUTHORISED
)
async def refresh(
    session: SessionDep,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> TokenResponse:
    if refresh_token is None:
        raise AuthenticationError("No refresh token provided")

    access_token, new_refresh_token = await auth_service.rotate_refresh_token(
        session, refresh_token
    )
    _set_refresh_cookie(response, new_refresh_token)

    return TokenResponse(
        access_token=access_token,
        expires_in=get_settings().access_token_ttl_seconds,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out and revoke the refresh token",
)
async def logout(
    session: SessionDep,
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> None:
    # Idempotent by design: logging out twice, or without a session, succeeds.
    if refresh_token is not None:
        await auth_service.revoke_refresh_token(session, refresh_token)

    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserResponse, summary="Current user", responses=UNAUTHORISED)
async def me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)
