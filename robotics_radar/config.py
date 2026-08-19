"""Runtime configuration. Everything comes from the environment.

DATABASE_URL is supplied by the Railway Postgres plugin and is never
hardcoded. API keys default to None so the app boots without them; a fetcher
that needs a missing key fails loudly at call time rather than at import.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost/robotics_radar"

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
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
