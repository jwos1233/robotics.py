"""Backfill a source over a range of periods in one process.

Running the per-period CLI in a shell loop spends most of its time on
interpreter startup and connection setup. This walks the range inside one
process and one connection pool instead.

Usage:
    python -m robotics_radar.scheduler.backfill census --from 2023-01 --to 2026-06

Failures do not abort the run: a period that fails is logged and counted, and
the walk continues. A customs series with one unavailable month is still worth
having, and stopping at the first gap would make backfilling long ranges
impractical. The summary reports what failed so the gaps are never silent.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from robotics_radar.db import session_scope
from robotics_radar.ingest.base import IngestError
from robotics_radar.ingest.registry import FETCHERS, get_fetcher
from robotics_radar.logging import configure_logging, get_logger
from robotics_radar.models.constraint import Series

log = get_logger(__name__)


def month_range(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("--to must not precede --from")
    periods, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        periods.append(date(year, month, 1))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return periods


def parse_month(value: str) -> date:
    year, month = value.split("-")
    return date(int(year), int(month), 1)


def backfill(source: str, start: date, end: date) -> tuple[int, list[str]]:
    fetcher = get_fetcher(source)
    periods = month_range(start, end)
    written, failures = 0, []

    with session_scope() as session:
        series_ids = {
            s.name: s.id
            for s in session.query(Series).filter(Series.source == fetcher.source_name)
        }
        if not series_ids:
            raise IngestError(
                f"{fetcher.source_name}: no series registered. Run "
                f"'scheduler.run register' first."
            )

    for period in periods:
        label = f"{period.year:04d}-{period.month:02d}"
        try:
            # One transaction per period: a failure rolls back only that month.
            with session_scope() as session:
                written += fetcher.run(session, series_ids, period)
        except Exception as exc:  # noqa: BLE001 - recorded, then the walk continues
            failures.append(label)
            log.warning("backfill_period_failed", source=source, period=label, error=str(exc))

    log.info(
        "backfill_complete",
        source=source,
        periods=len(periods),
        rows=written,
        failed=len(failures),
    )
    return written, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill one source over a month range.")
    parser.add_argument("source", choices=sorted(FETCHERS))
    parser.add_argument("--from", dest="start", required=True, help="YYYY-MM")
    parser.add_argument("--to", dest="end", required=True, help="YYYY-MM")
    args = parser.parse_args(argv)

    configure_logging()
    written, failures = backfill(args.source, parse_month(args.start), parse_month(args.end))
    if failures:
        print(f"rows={written}; failed periods: {', '.join(failures)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
