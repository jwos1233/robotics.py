"""Runtime configuration. Everything comes from the environment.

DATABASE_URL is supplied by the Railway Postgres plugin and is never
hardcoded. It has no default on purpose: a localhost fallback turns a missing
variable into a "connection refused to 127.0.0.1" traceback from deep inside
the driver, which reads like a broken database rather than an unset variable.
Missing configuration should say so.

API keys default to None so the app boots without them; a fetcher that needs a
missing key fails loudly at call time rather than at import.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when required configuration is absent or unusable."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str | None = None

    census_api_key: str | None = None
    comtrade_api_key: str | None = None
    estat_app_id: str | None = None
    data_go_kr_key: str | None = None
    equity_api_key: str | None = None

    benchmark_symbol: str = "ACWI"
    max_forward_fill_sessions: int = 3

    log_level: str = "INFO"
    app_env: str = "development"

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise Railway's URL scheme to the psycopg v3 driver."""
        url = self.database_url
        if not url:
            raise ConfigError(MISSING_DATABASE_URL)
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


MISSING_DATABASE_URL = """DATABASE_URL is not set.

The application cannot start without a database. On Railway this variable is
NOT inherited automatically: adding the Postgres plugin exposes DATABASE_URL
on the Postgres service only. Each service that needs it must reference it
explicitly.

  Railway -> your service -> Variables -> New Variable:
      DATABASE_URL = ${{Postgres.DATABASE_URL}}

(substituting the actual name of your Postgres service if it is not
"Postgres"). Do this for BOTH the web service and the scheduler service.

Locally, copy .env.example to .env and set DATABASE_URL there."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
