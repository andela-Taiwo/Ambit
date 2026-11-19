"""Scheduled exchange-rate fetch.

Provider contract (deliberately small, so the provider stays swappable):
`GET <url>?base=GBP&symbols=USD,EUR` returning

    {"base": "GBP", "date": "2026-10-27", "rates": {"USD": 1.27, "EUR": 1.16}}

The key, when configured, is sent in a header (never the URL) so it cannot end
up in proxy or access logs. A failed fetch never deletes existing observations:
the last good rate stays resolvable, and the job exits non-zero so alerting
notices (plan Section 14).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging, get_logger
from app.db.models import ExchangeRate
from app.db.session import dispose_engine, session_scope
from app.domain.fx import InvalidRateError, validate_rate
from app.domain.money import Currency, UnknownCurrencyError

logger = get_logger(__name__)

#: Network timeout for the provider call, in seconds.
PROVIDER_TIMEOUT_SECONDS = 10


class RateProviderError(Exception):
    """The provider could not be reached or returned unusable data."""


class RateProvider(Protocol):
    """A source of rate observations."""

    @property
    def name(self) -> str: ...

    async def fetch(self, *, base_currency: str, quotes: Sequence[str]) -> ProviderRates: ...


@dataclass(frozen=True, slots=True)
class ProviderRates:
    base_currency: str
    as_of: datetime
    rates: dict[str, Decimal]
    source: str


def _coerce_decimal(value: object) -> Decimal:
    if isinstance(value, float):
        # json.loads(parse_float=Decimal) prevents this, but a caller could
        # construct the dict by hand. Refusing is safer than a binary float.
        raise RateProviderError("Provider returned a float; refusing imprecise data")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RateProviderError(f"Provider returned a non-numeric rate: {value!r}") from exc
    try:
        return validate_rate(parsed)
    except InvalidRateError as exc:
        raise RateProviderError(str(exc)) from exc


def _parse_as_of(payload: dict[str, object], *, now: datetime) -> datetime:
    raw_date = payload.get("date")
    if isinstance(raw_date, str) and raw_date:
        try:
            parsed_date = date.fromisoformat(raw_date[:10])
        except ValueError as exc:
            raise RateProviderError(f"Provider returned an invalid date: {raw_date!r}") from exc
        return datetime.combine(parsed_date, time.min, tzinfo=UTC)

    raw_timestamp = payload.get("timestamp")
    if isinstance(raw_timestamp, (int, float)) and not isinstance(raw_timestamp, bool):
        return datetime.fromtimestamp(int(raw_timestamp), tz=UTC)

    # No provider timestamp: treat the observation as a daily one so a retry
    # on the same day is idempotent rather than a new row per run.
    return datetime.combine(now.date(), time.min, tzinfo=UTC)


def parse_provider_payload(
    payload: bytes,
    *,
    expected_base: str,
    quotes: Sequence[str],
    source: str,
    now: datetime | None = None,
) -> ProviderRates:
    """Parse and validate a provider document. Never guesses a missing rate."""
    try:
        document = json.loads(payload, parse_float=Decimal)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise RateProviderError("Provider response was not valid JSON") from exc

    if not isinstance(document, dict):
        raise RateProviderError("Provider response must be a JSON object")

    base = document.get("base", expected_base)
    if not isinstance(base, str):
        raise RateProviderError("Provider base must be a string")
    try:
        base_currency = Currency(base).code
    except UnknownCurrencyError as exc:
        raise RateProviderError(f"Provider returned an unsupported base: {base!r}") from exc

    if base_currency != Currency(expected_base).code:
        raise RateProviderError(
            f"Provider quoted {base_currency} but {expected_base} was requested"
        )

    raw_rates = document.get("rates")
    if not isinstance(raw_rates, dict):
        raise RateProviderError("Provider response has no rates object")

    parsed: dict[str, Decimal] = {}
    for quote in quotes:
        try:
            quote_currency = Currency(quote).code
        except UnknownCurrencyError as exc:
            raise RateProviderError(f"Unsupported quote currency: {quote!r}") from exc
        if quote_currency == base_currency:
            continue
        if quote_currency not in raw_rates:
            raise RateProviderError(f"Provider did not return a rate for {quote_currency}")
        parsed[quote_currency] = _coerce_decimal(raw_rates[quote_currency])

    return ProviderRates(
        base_currency=base_currency,
        as_of=_parse_as_of(document, now=now or datetime.now(UTC)),
        rates=parsed,
        source=source,
    )


class HttpRateProvider:
    """Fetches rates over HTTP from the configured provider endpoint."""

    def __init__(
        self,
        *,
        url: str,
        api_key: str | None = None,
        api_key_header: str = "apikey",
        timeout: int = PROVIDER_TIMEOUT_SECONDS,
    ) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("exchange_rate_api_url must be an absolute HTTP(S) URL")
        self._url = url
        self._api_key = api_key
        self._api_key_header = api_key_header
        self._timeout = timeout
        self._host = parsed.hostname
        if len(f"http:{self._host}") > 64:
            raise ValueError("exchange-rate provider host is too long for the source column")

    @property
    def name(self) -> str:
        return f"http:{self._host}"

    async def fetch(self, *, base_currency: str, quotes: Sequence[str]) -> ProviderRates:
        return await asyncio.to_thread(self._fetch_sync, base_currency=base_currency, quotes=quotes)

    def _fetch_sync(self, *, base_currency: str, quotes: Sequence[str]) -> ProviderRates:
        separator = "&" if "?" in self._url else "?"
        params = urlencode({"base": base_currency, "symbols": ",".join(quotes)})
        request = Request(
            f"{self._url}{separator}{params}",
            headers={"Accept": "application/json"},
            method="GET",
        )
        if self._api_key:
            request.add_header(self._api_key_header, self._api_key)

        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = response.read()
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise RateProviderError(f"Exchange-rate provider request failed: {exc}") from exc

        return parse_provider_payload(
            payload,
            expected_base=base_currency,
            quotes=quotes,
            source=self.name,
        )


async def store_rates(
    session: AsyncSession,
    rates: ProviderRates,
    *,
    user_id: uuid.UUID | None = None,
) -> int:
    """Persist observations, skipping exact duplicates (idempotent job).

    `ON CONFLICT DO NOTHING` handles the concurrent-run case in the database
    rather than relying on a check-then-insert race.
    """
    inserted = 0
    for quote_currency, rate in rates.rates.items():
        statement = (
            pg_insert(ExchangeRate)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                base_currency=rates.base_currency,
                quote_currency=quote_currency,
                rate=rate,
                as_of=rates.as_of,
                source=rates.source,
            )
            .on_conflict_do_nothing()
        )
        result = cast(CursorResult[Any], await session.execute(statement))
        inserted += int(result.rowcount or 0)

    await session.commit()
    return inserted


async def run(
    *,
    settings: Settings,
    provider: RateProvider,
    user_id: uuid.UUID | None = None,
) -> int:
    """Fetch and store one observation set. Returns rows inserted."""
    provider_rates = await provider.fetch(
        base_currency=settings.exchange_rate_base_currency,
        quotes=settings.exchange_rate_quotes,
    )
    async with session_scope() as session:
        return await store_rates(session, provider_rates, user_id=user_id)


async def main() -> int:
    configure_logging(get_settings().log_level, json_output=get_settings().app_env != "local")
    settings = get_settings()

    if not settings.exchange_rate_api_url:
        logger.warning(
            "exchange_rate_fetch_skipped",
            reason="EXCHANGE_RATE_API_URL is not configured",
        )
        return 0

    provider = HttpRateProvider(
        url=settings.exchange_rate_api_url,
        api_key=(
            settings.exchange_rate_api_key.get_secret_value()
            if settings.exchange_rate_api_key is not None
            else None
        ),
        api_key_header=settings.exchange_rate_api_key_header,
    )

    try:
        inserted = await run(settings=settings, provider=provider)
    except RateProviderError as exc:
        logger.error("exchange_rate_fetch_failed", error=str(exc), source=provider.name)
        return 1
    finally:
        await dispose_engine()

    logger.info(
        "exchange_rates_stored",
        inserted=inserted,
        base=settings.exchange_rate_base_currency,
        source=provider.name,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
