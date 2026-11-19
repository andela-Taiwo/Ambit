"""Exchange-rate request/response contracts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, Field, PlainSerializer, field_validator, model_validator

from app.domain.fx import ResolvedRate
from app.domain.money import Currency, UnknownCurrencyError
from app.schemas.common import CurrencyCode, ORMModel


def format_decimal(value: Decimal) -> str:
    """Render a Decimal as a plain string without exponent or trailing zeros.

    Rates come back from Postgres scaled to 12 decimal places; sending
    `1.300000000000` over the wire is harmless numerically but noisy for every
    client, so normalise the presentation while keeping exact arithmetic.
    """
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


#: A decimal that serialises as a JSON *string*, never a float.
DecimalString = Annotated[
    Decimal, PlainSerializer(format_decimal, return_type=str, when_used="json")
]


def _normalise_currency(value: str) -> str:
    try:
        return Currency(value).code
    except UnknownCurrencyError as exc:
        raise ValueError(str(exc)) from exc


def _ensure_aware(value: datetime) -> datetime:
    """Treat a naive timestamp as UTC instead of letting it fail later.

    Rate resolution compares timestamps in Postgres, so silently mixing naive
    and aware values is exactly the kind of bug that produces a *plausible*
    wrong rate. Normalising once at the boundary keeps the rest of the stack
    timezone-aware.
    """
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class ExchangeRateCreate(BaseModel):
    """Record a manual rate. Provider rates are written by the scheduled job."""

    base_currency: CurrencyCode
    quote_currency: CurrencyCode
    rate: Decimal = Field(
        gt=0,
        max_digits=24,
        decimal_places=12,
        examples=["1.27"],
        description="One unit of base_currency buys this many quote_currency.",
    )
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("base_currency", "quote_currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return _normalise_currency(value)

    @field_validator("as_of")
    @classmethod
    def _validate_as_of(cls, value: datetime) -> datetime:
        return _ensure_aware(value)

    @model_validator(mode="after")
    def _validate_pair(self) -> ExchangeRateCreate:
        if self.base_currency == self.quote_currency:
            raise ValueError("A currency cannot be quoted against itself")
        return self


class ExchangeRateResponse(ORMModel):
    id: uuid.UUID
    base_currency: str
    quote_currency: str
    rate: DecimalString
    as_of: datetime
    source: str
    fetched_at: datetime


class ResolvedRateResponse(BaseModel):
    """The effective rate for a pair at a point in time, plus provenance."""

    base_currency: str
    quote_currency: str
    rate: DecimalString
    as_of: datetime
    source: str
    is_inverse: bool = Field(
        description="True when resolved from the opposite stored pair (1/rate)."
    )

    @classmethod
    def from_domain(cls, resolved: ResolvedRate) -> ResolvedRateResponse:
        return cls(
            base_currency=resolved.base_currency,
            quote_currency=resolved.quote_currency,
            rate=resolved.rate,
            as_of=resolved.as_of,
            source=resolved.source,
            is_inverse=resolved.is_inverse,
        )


class ConversionResponse(BaseModel):
    """A conversion preview. The rate used is returned so it can be audited."""

    from_currency: str
    to_currency: str
    amount_minor: int
    converted_minor: int
    rate: DecimalString
    rate_as_of: datetime
    rate_source: str
    rate_is_inverse: bool
