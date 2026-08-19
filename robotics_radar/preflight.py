"""Startup preflight: verify the database is configured and reachable.

Runs before migrations so the two failure modes stay distinguishable:

* **Not configured** -- DATABASE_URL is absent or malformed. This will never
  fix itself, so it fails immediately with the remedy rather than retrying.
* **Not reachable yet** -- the URL is fine but Postgres is not accepting
  connections. On Railway the database can lag the application on a cold
  deploy, so this retries with backoff before giving up.

Without this split, a missing variable and a slow database produce the same
wall of driver traceback, and the deploy log tells you nothing about which one
you have.
"""

from __future__ import annotations

import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from robotics_radar.config import ConfigError, get_settings
from robotics_radar.logging import configure_logging, get_logger

log = get_logger(__name__)

MAX_ATTEMPTS = 12
BASE_DELAY_SECONDS = 1.0
MAX_DELAY_SECONDS = 8.0


def wait_for_database(
    max_attempts: int = MAX_ATTEMPTS,
    base_delay: float = BASE_DELAY_SECONDS,
    sleep=time.sleep,
) -> None:
    """Block until Postgres answers, or raise.

    Raises ConfigError immediately if the URL is missing or malformed --
    retrying a configuration mistake only delays the useful error message.
    """
    settings = get_settings()
    url = settings.sqlalchemy_url  # raises ConfigError when unset

    engine = create_engine(url, pool_pre_ping=True, future=True)
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            log.info("database_ready", attempt=attempt)
            return
        except SQLAlchemyError as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            delay = min(base_delay * 2 ** (attempt - 1), MAX_DELAY_SECONDS)
            log.warning(
                "database_unreachable_retrying",
                attempt=attempt,
                max_attempts=max_attempts,
                retry_in_seconds=delay,
                error=str(exc.__cause__ or exc).splitlines()[0],
            )
            sleep(delay)
        finally:
            engine.dispose()

    raise ConnectionError(
        f"Database did not become reachable after {max_attempts} attempts. "
        f"DATABASE_URL is set, so this is a reachability problem, not a missing "
        f"variable: check that the Postgres service is running and that this "
        f"service can reach it. Last error: {last_error}"
    )


def main() -> int:
    configure_logging(get_settings().log_level)
    try:
        wait_for_database()
    except ConfigError as exc:
        # Configuration, not infrastructure. Print plainly: this message is the
        # whole point of the preflight and must survive log formatting.
        print(f"\nPREFLIGHT FAILED: {exc}\n", file=sys.stderr)
        return 78  # EX_CONFIG
    except ConnectionError as exc:
        print(f"\nPREFLIGHT FAILED: {exc}\n", file=sys.stderr)
        return 75  # EX_TEMPFAIL
    return 0


if __name__ == "__main__":
    sys.exit(main())
