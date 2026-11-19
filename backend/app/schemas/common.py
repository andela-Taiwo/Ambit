"""Shared schema building blocks."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

CurrencyCode = Annotated[str, Field(min_length=3, max_length=3, examples=["GBP", "NGN"])]


class ORMModel(BaseModel):
    """Response models read directly from ORM instances."""

    model_config = ConfigDict(from_attributes=True)


class Page[T](BaseModel):
    """A page of results. Every list endpoint paginates (plan Section 12, Phase 7)."""

    items: list[T]
    total: int = Field(description="Total matching rows, ignoring pagination.")
    limit: int
    offset: int


class ErrorResponse(BaseModel):
    """The body returned by every handled error (see `AppError` in app.main)."""

    detail: str


#: Reusable OpenAPI response declarations. Applied per-route so the generated
#: client models real failure modes rather than inferring only 200/422.
UNAUTHORISED: dict[int | str, dict[str, object]] = {
    401: {"model": ErrorResponse, "description": "Missing or invalid credentials"}
}
NOT_FOUND: dict[int | str, dict[str, object]] = {
    404: {"model": ErrorResponse, "description": "Resource not found or not owned by the caller"}
}
CONFLICT: dict[int | str, dict[str, object]] = {
    409: {"model": ErrorResponse, "description": "Conflicts with an existing resource"}
}
