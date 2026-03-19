"""Authentication request/response contracts."""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.domain.money import Currency, UnknownCurrencyError
from app.schemas.common import CurrencyCode, ORMModel

#: Long enough to resist offline guessing, capped so Argon2 cannot be used as
#: a CPU-exhaustion vector.
Password = Annotated[str, Field(min_length=12, max_length=128)]


class RegisterRequest(BaseModel):
    email: EmailStr
    password: Password
    display_name: Annotated[str, Field(min_length=1, max_length=120)]
    base_currency: CurrencyCode = "GBP"

    @field_validator("base_currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        try:
            return Currency(value).code
        except UnknownCurrencyError as exc:
            raise ValueError(str(exc)) from exc


class LoginRequest(BaseModel):
    email: EmailStr
    password: Annotated[str, Field(min_length=1, max_length=128)]


class TokenResponse(BaseModel):
    """The refresh token is NOT in this body -- it is set as an httpOnly cookie."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds.")


class UserResponse(ORMModel):
    id: uuid.UUID
    email: EmailStr
    display_name: str
    base_currency: str
