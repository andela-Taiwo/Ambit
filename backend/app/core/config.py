"""Application settings.

Config is environment-variable driven and validated at import time, so a
misconfigured deployment fails to boot instead of failing later at request
time (plan Section 6).
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict
from pydantic_settings.sources import PydanticBaseSettingsSource

AppEnv = Literal["local", "test", "ci", "staging", "production"]

#: Settings read from the environment as `a, b, c` rather than a JSON array.
COMMA_SEPARATED_FIELDS = frozenset({"cors_origins", "exchange_rate_quotes"})

#: Vite's default dev and preview origins. Applied only when APP_ENV=local and
#: no explicit CORS_ORIGINS is supplied, so a fresh checkout can talk to the
#: local API without a confusing browser-only failure. Deployed environments
#: must still configure their origins explicitly.
LOCAL_DEV_CORS_ORIGINS: tuple[str, ...] = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://[::1]:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://[::1]:4173",
)


class _CommaSeparatedEnvSource(EnvSettingsSource):
    """Env source that leaves designated list fields as raw strings.

    Returning the string unchanged hands normalisation to the field validator,
    which splits on commas.
    """

    def prepare_field_value(
        self,
        field_name: str,
        field: FieldInfo,
        value: object,
        value_is_complex: bool,
    ) -> object:
        if field_name in COMMA_SEPARATED_FIELDS and isinstance(value, str):
            return value
        return super().prepare_field_value(field_name, field, value, value_is_complex)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: AppEnv = "local"
    log_level: str = "INFO"

    database_url: str = Field(..., description="Async SQLAlchemy DSN")
    secret_key: SecretStr = Field(..., min_length=16)

    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 1_209_600

    cors_origins: list[str] = Field(default_factory=list)
    sentry_dsn: str | None = None

    # Exchange-rate provider. The job is opt-in: without a URL it logs and
    # exits successfully rather than inventing rates.
    exchange_rate_api_url: str | None = None
    exchange_rate_api_key: SecretStr | None = None
    exchange_rate_api_key_header: str = "apikey"
    exchange_rate_base_currency: str = "GBP"
    exchange_rate_quotes: list[str] = Field(default_factory=lambda: ["USD", "EUR", "NGN"])

    @field_validator("database_url")
    @classmethod
    def _require_async_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("database_url must use the postgresql+asyncpg:// driver")
        return value

    @field_validator("exchange_rate_base_currency")
    @classmethod
    def _require_three_letter_currency(cls, value: str) -> str:
        normalised = value.strip().upper()
        if len(normalised) != 3 or not normalised.isalpha():
            raise ValueError("exchange_rate_base_currency must be a 3-letter code")
        return normalised

    @field_validator("exchange_rate_quotes", mode="before")
    @classmethod
    def _normalise_quotes(cls, value: object) -> object:
        if isinstance(value, str):
            parts = [part.strip().upper() for part in value.split(",") if part.strip()]
            return parts
        return value

    @field_validator("exchange_rate_quotes")
    @classmethod
    def _require_three_letter_quotes(cls, value: list[str]) -> list[str]:
        for code in value:
            if len(code) != 3 or not code.isalpha():
                raise ValueError(f"Invalid currency code in exchange_rate_quotes: {code!r}")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_comma_separated(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Read list-valued settings as comma-separated strings, not JSON.

        pydantic-settings otherwise JSON-decodes complex types straight from the
        environment, which would reject the plain `a,b` form used in .env files
        and deployment config before any validator could normalise it.
        """
        return (
            init_settings,
            _CommaSeparatedEnvSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )

    @model_validator(mode="after")
    def _apply_local_cors_defaults_and_forbid_wildcards(self) -> Settings:
        if self.app_env == "local" and not self.cors_origins:
            self.cors_origins = list(LOCAL_DEV_CORS_ORIGINS)
        if "*" in self.cors_origins and self.app_env in ("staging", "production"):
            raise ValueError("wildcard CORS origin is not allowed in staging or production")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor; call `.cache_clear()` in tests."""
    return Settings()
