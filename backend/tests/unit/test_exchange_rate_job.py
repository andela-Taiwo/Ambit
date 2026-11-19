"""Exchange-rate provider parsing and the scheduled fetch job."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from urllib.error import URLError

import pytest

from app.jobs import fetch_exchange_rates as job
from app.jobs.fetch_exchange_rates import (
    HttpRateProvider,
    RateProviderError,
    parse_provider_payload,
)

NOW = datetime(2026, 10, 27, 12, tzinfo=UTC)


def _payload(**overrides: Any) -> bytes:
    document: dict[str, Any] = {
        "base": "GBP",
        "date": "2026-10-27",
        "rates": {"USD": 1.27, "EUR": 1.16, "NGN": 2100.5},
    }
    document.update(overrides)
    return json.dumps(document).encode()


class TestParseProviderPayload:
    def test_parses_rates_as_exact_decimals(self) -> None:
        result = parse_provider_payload(
            _payload(),
            expected_base="GBP",
            quotes=["USD", "EUR", "NGN"],
            source="http:provider",
            now=NOW,
        )

        assert result.base_currency == "GBP"
        assert result.as_of == datetime(2026, 10, 27, tzinfo=UTC)
        assert result.rates == {
            "USD": Decimal("1.27"),
            "EUR": Decimal("1.16"),
            "NGN": Decimal("2100.5"),
        }
        assert result.source == "http:provider"

    def test_uses_the_timestamp_when_no_date_is_present(self) -> None:
        document = json.loads(_payload())
        del document["date"]
        document["timestamp"] = 1_790_000_000

        result = parse_provider_payload(
            json.dumps(document).encode(),
            expected_base="GBP",
            quotes=["USD"],
            source="http:provider",
            now=NOW,
        )

        assert result.as_of == datetime.fromtimestamp(1_790_000_000, tz=UTC)

    def test_defaults_to_now_without_a_timestamp(self) -> None:
        document = json.loads(_payload())
        del document["date"]

        result = parse_provider_payload(
            json.dumps(document).encode(),
            expected_base="GBP",
            quotes=["USD"],
            source="http:provider",
            now=NOW,
        )

        assert result.as_of == datetime(2026, 10, 27, tzinfo=UTC)

    def test_rejects_a_different_base(self) -> None:
        with pytest.raises(RateProviderError, match="quoted USD"):
            parse_provider_payload(
                _payload(base="USD"),
                expected_base="GBP",
                quotes=["EUR"],
                source="http:provider",
            )

    def test_rejects_a_missing_quote(self) -> None:
        with pytest.raises(RateProviderError, match="did not return a rate for NGN"):
            parse_provider_payload(
                _payload(rates={"USD": 1.27}),
                expected_base="GBP",
                quotes=["USD", "NGN"],
                source="http:provider",
            )

    def test_rejects_non_json(self) -> None:
        with pytest.raises(RateProviderError, match="not valid JSON"):
            parse_provider_payload(
                b"<html>nope</html>",
                expected_base="GBP",
                quotes=["USD"],
                source="http:provider",
            )

    def test_rejects_a_non_object(self) -> None:
        with pytest.raises(RateProviderError, match="JSON object"):
            parse_provider_payload(
                b"[]", expected_base="GBP", quotes=["USD"], source="http:provider"
            )

    def test_rejects_a_missing_rates_object(self) -> None:
        with pytest.raises(RateProviderError, match="no rates object"):
            parse_provider_payload(
                b'{"base": "GBP"}',
                expected_base="GBP",
                quotes=["USD"],
                source="http:provider",
            )

    @pytest.mark.parametrize("rate", [0, -1])
    def test_rejects_a_non_positive_rate(self, rate: int) -> None:
        with pytest.raises(RateProviderError):
            parse_provider_payload(
                _payload(rates={"USD": rate}),
                expected_base="GBP",
                quotes=["USD"],
                source="http:provider",
            )

    def test_rejects_an_invalid_date(self) -> None:
        with pytest.raises(RateProviderError, match="invalid date"):
            parse_provider_payload(
                _payload(date="not-a-date"),
                expected_base="GBP",
                quotes=["USD"],
                source="http:provider",
            )

    def test_ignores_a_quote_equal_to_the_base(self) -> None:
        result = parse_provider_payload(
            _payload(rates={"GBP": 1, "USD": 1.27}),
            expected_base="GBP",
            quotes=["GBP", "USD"],
            source="http:provider",
        )

        assert "GBP" not in result.rates

    def test_rejects_an_unsupported_base(self) -> None:
        with pytest.raises(RateProviderError, match="unsupported base"):
            parse_provider_payload(
                _payload(base="XYZ"),
                expected_base="XYZ",
                quotes=["USD"],
                source="http:provider",
            )


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TestHttpRateProvider:
    async def test_sends_the_configured_key_in_a_header_not_the_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["timeout"] = timeout
            return _FakeResponse(_payload())

        monkeypatch.setattr(job, "urlopen", fake_urlopen)
        provider = HttpRateProvider(
            url="https://rates.example.test/latest",
            api_key="secret-key",
            api_key_header="apikey",
        )

        result = await provider.fetch(base_currency="GBP", quotes=["USD", "EUR"])

        assert result.rates["USD"] == Decimal("1.27")
        assert captured["url"].startswith("https://rates.example.test/latest?")
        assert "secret-key" not in captured["url"]
        assert captured["headers"]["Apikey"] == "secret-key"
        assert captured["timeout"] == 10

    async def test_wraps_network_failures(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
            raise URLError("connection refused")

        monkeypatch.setattr(job, "urlopen", fake_urlopen)
        provider = HttpRateProvider(url="https://rates.example.test/latest")

        with pytest.raises(RateProviderError, match="request failed"):
            await provider.fetch(base_currency="GBP", quotes=["USD"])

    def test_rejects_a_non_http_url(self) -> None:
        with pytest.raises(ValueError, match="HTTP"):
            HttpRateProvider(url="file:///etc/passwd")

    def test_name_contains_only_the_host(self) -> None:
        provider = HttpRateProvider(url="https://user:pass@rates.example.test/latest?key=x")

        assert provider.name == "http:rates.example.test"
