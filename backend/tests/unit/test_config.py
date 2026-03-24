"""Settings must fail loudly at startup rather than silently later."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import get_settings


def _clear_cache() -> None:
    """Settings are cached; tests must clear between environment changes."""
    get_settings.cache_clear()


def test_settings_load_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-long-secret-key-value")
    monkeypatch.setenv("APP_ENV", "staging")
    _clear_cache()

    settings = get_settings()

    assert settings.app_env == "staging"
    assert settings.secret_key.get_secret_value() == "a-sufficiently-long-secret-key-value"
    assert str(settings.database_url).startswith("postgresql+asyncpg://")


def test_missing_required_config_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    _clear_cache()

    with pytest.raises(ValidationError):
        get_settings()


def test_unknown_app_env_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-long-secret-key-value")
    monkeypatch.setenv("APP_ENV", "not-a-real-environment")
    _clear_cache()

    with pytest.raises(ValidationError):
        get_settings()


def test_cors_origins_parsed_from_comma_separated_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-long-secret-key-value")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:5173, https://staging.example.com")
    _clear_cache()

    assert get_settings().cors_origins == [
        "http://localhost:5173",
        "https://staging.example.com",
    ]


def test_wildcard_cors_rejected_outside_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Section 10: no `*` CORS in staging/production."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-long-secret-key-value")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    _clear_cache()

    with pytest.raises(ValidationError):
        get_settings()


def test_local_environment_gets_vite_default_cors_origins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A fresh checkout must be able to call the API from Vite without a CORS wall."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-long-secret-key-value")
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    _clear_cache()

    origins = get_settings().cors_origins

    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:4173" in origins


def test_deployed_environments_get_no_local_cors_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost:5432/db")
    monkeypatch.setenv("SECRET_KEY", "a-sufficiently-long-secret-key-value")
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    _clear_cache()

    assert get_settings().cors_origins == []
