"""Ingestion entrypoint, invoked by Railway cron.

Usage:
    python -m robotics_radar.scheduler.run <source> [--period YYYY-MM]

One source per invocation so a failure in one is isolated and its cron
schedule is independent. Exits non-zero on failure so Railway records the run
as failed rather than silently succeeding on a no-op.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from robotics_radar.db import session_scope
from robotics_radar.ingest.base import IngestError
from robotics_radar.ingest.register import register_all
from robotics_radar.ingest.registry import FETCHERS, get_fetcher
from robotics_radar.logging import configure_logging, get_logger
from robotics_radar.models.constraint import Series

log = get_logger(__name__)


def previous_month(today: date | None = None) -> date:
    today = today or date.today()
    first = today.replace(day=1)
    prev_end = first.replace(day=1)
    year, month = (prev_end.year, prev_end.month - 1) if prev_end.month > 1 else (
        prev_end.year - 1,
        12,
    )
    return date(year, month, 1)


def parse_period(value: str | None) -> date:
    if value is None:
        return previous_month()
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run one ingestion source.")
    parser.add_argument("source", choices=sorted([*FETCHERS, "register"]))
    parser.add_argument(
        "--period",
        help="Target period as YYYY-MM. Defaults to the previous complete month.",
    )
    args = parser.parse_args(argv)

    configure_logging()
    period = parse_period(args.period)

    if args.source == "register":
        with session_scope() as session:
            count = register_all(session)
        log.info("register_complete", series=count)
        return 0

    fetcher = get_fetcher(args.source)
    log.info("ingest_start", source=fetcher.source_name, period=str(period))

    try:
        with session_scope() as session:
            series_ids = {
                s.name: s.id
                for s in session.query(Series).filter(Series.source == fetcher.source_name)
            }
            rows = fetcher.run(session, series_ids, period)
    except IngestError as exc:
        # Expected while Phase 0 verification is outstanding: a source that
        # cannot produce a trustworthy value refuses rather than guessing.
        log.error(
            "ingest_refused",
            source=fetcher.source_name,
            period=str(period),
            reason=str(exc),
        )
        return 1
    except Exception as exc:  # noqa: BLE001 - top level, must log before exiting
        log.error(
            "ingest_failed",
            source=fetcher.source_name,
            period=str(period),
            error=str(exc),
            exc_info=True,
        )
        return 2

    log.info("ingest_ok", source=fetcher.source_name, period=str(period), rows=rows)
    return 0


if __name__ == "__main__":
    sys.exit(main())
