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

import os
from functools import lru_cache
from urllib.parse import quote

from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigError(RuntimeError):
    """Raised when required configuration is absent or unusable."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Primary. On Railway this is the private-network URL.
    database_url: str | None = None
    # Railway also publishes a public URL. It works but routes over the public
    # internet and is billed as egress, so it is only used if nothing else is
    # available, and it says so when it is.
    database_public_url: str | None = None
    # Standard libpq parts. If the Postgres plugin is linked but DATABASE_URL
    # was never referenced, these are usually what is actually present.
    pghost: str | None = None
    pgport: int | None = None
    pguser: str | None = None
    pgpassword: str | None = None
    pgdatabase: str | None = None

    census_api_key: str | None = None
    comtrade_api_key: str | None = None
    estat_app_id: str | None = None
    data_go_kr_key: str | None = None
    equity_api_key: str | None = None

    benchmark_symbol: str = "ACWI"
    max_forward_fill_sessions: int = 3

    log_level: str = "INFO"
    app_env: str = "development"

    def resolve_database_url(self) -> tuple[str, str]:
        """Return (url, which-source-it-came-from).

        Three accepted sources, in order of preference. All three are standard
        ways a Postgres connection reaches a container, so honouring the
        fallbacks turns several common Railway wiring mistakes into a working
        deploy rather than a crash loop.
        """
        if self.database_url:
            return self.database_url, "DATABASE_URL"

        if self.pghost and self.pguser and self.pgdatabase:
            port = self.pgport or 5432
            password = f":{quote(self.pgpassword, safe='')}" if self.pgpassword else ""
            url = (
                f"postgresql://{quote(self.pguser, safe='')}{password}"
                f"@{self.pghost}:{port}/{self.pgdatabase}"
            )
            return url, "PGHOST/PGUSER/PGDATABASE"

        if self.database_public_url:
            return self.database_public_url, "DATABASE_PUBLIC_URL"

        raise ConfigError(missing_database_url_message())

    @property
    def database_url_source(self) -> str:
        return self.resolve_database_url()[1]

    @property
    def sqlalchemy_url(self) -> str:
        """Normalise Railway's URL scheme to the psycopg v3 driver."""
        url, _ = self.resolve_database_url()
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url


DB_ENV_PREFIXES = ("DATABASE", "PG", "POSTGRES")


def visible_database_env_vars() -> list[str]:
    """Names (never values) of database-ish variables present in the process.

    This is the diagnostic that distinguishes "the Postgres service is not
    linked to this service at all" from "it is linked but DATABASE_URL was
    never referenced". Values are deliberately not printed: several of these
    hold credentials.
    """
    return sorted(
        name
        for name in os.environ
        if any(name.upper().startswith(prefix) for prefix in DB_ENV_PREFIXES)
    )


def missing_database_url_message() -> str:
    seen = visible_database_env_vars()

    if seen:
        found = (
            "Database-related variables that ARE visible to this service:\n"
            + "\n".join(f"      {name}" for name in seen)
            + "\n\n  So the Postgres service is reachable from here, but none of the\n"
            "  three accepted forms is complete. This app accepts, in order:\n"
            "      1. DATABASE_URL\n"
            "      2. PGHOST + PGUSER + PGDATABASE (+ PGPORT, PGPASSWORD)\n"
            "      3. DATABASE_PUBLIC_URL\n"
        )
    else:
        found = (
            "NO database-related variables are visible to this service at all\n"
            "  (nothing starting with DATABASE, PG or POSTGRES).\n\n"
            "  That means the Postgres service is not wired to this one -- check\n"
            "  that a Postgres database actually exists in this project and in\n"
            "  THIS environment, not just in another environment.\n"
        )

    return f"""No database connection is configured.

  {found}
  To fix, add a variable on THIS service (not on the Postgres service):

      Railway -> select this service -> Variables -> New Variable
          DATABASE_URL = ${{{{Postgres.DATABASE_URL}}}}

  Replace "Postgres" with the exact name of your Postgres service as shown in
  the Railway canvas. The reference resolves only within the same project and
  environment, and a typo in the service name resolves to nothing rather than
  raising, which looks exactly like this error.

  Set it on BOTH the web service and the scheduler service -- each cron
  invocation is a separate container and needs its own copy.

  Locally: copy .env.example to .env and set DATABASE_URL there."""


@lru_cache
def get_settings() -> Settings:
    return Settings()
