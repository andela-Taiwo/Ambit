"""Application-level errors mapped to HTTP responses in `app.main`.

Routes raise these rather than `HTTPException` so the service layer stays
framework-agnostic and independently testable.
"""

from __future__ import annotations


class AppError(Exception):
    """Base class for expected, user-facing failures."""

    status_code: int = 400
    detail: str = "Request could not be processed"

    def __init__(
        self, detail: str | None = None, *, details: dict[str, object] | None = None
    ) -> None:
        super().__init__(detail or self.detail)
        if detail is not None:
            self.detail = detail
        self.details: dict[str, object] = details or {}


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(AppError):
    status_code = 409
    detail = "Resource already exists"


class ValidationError(AppError):
    status_code = 422
    detail = "Request failed validation"


class AuthenticationError(AppError):
    status_code = 401
    detail = "Could not validate credentials"


class PermissionDeniedError(AppError):
    status_code = 403
    detail = "You do not have access to this resource"


class ImportValidationError(AppError):
    """A bulk import was rejected atomically; `details` carries row errors."""

    status_code = 422
    detail = "Import contains invalid rows; nothing was imported"
