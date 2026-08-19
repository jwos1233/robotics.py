"""Basket return computation.

The rules here are deliberate and several of them are load-bearing:

* Equal weight, never market cap. Cap weighting collapses several of these
  baskets into a single mega-cap and destroys the signal the basket exists to
  carry.
* Every constituent is converted to USD before any return is computed. A
  return averaged across mixed local currencies is not a number.
* The benchmark is ACWI. return_raw and return_vs_benchmark are reported
  separately so a caller can see whether a move was the basket or the market.
* Trading calendars differ across these venues, so everything is aligned onto
  the benchmark's calendar. A stale close is forward-filled for at most
  `max_forward_fill` sessions and then the constituent is marked stale rather
  than silently carrying an old price into a return.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from robotics_radar.models.enums import ReturnWindow

STALE = object()
"""Sentinel: a session where the constituent's last close is too old to use."""


@dataclass(frozen=True)
class AlignedSeries:
    """A constituent's USD closes projected onto the benchmark calendar.

    `stale_sessions` and `unpriced_sessions` are kept apart on purpose. A name
    whose price went stale is a data-freshness problem; a name we have never
    priced at all is a coverage problem. Collapsing them hides which one you
    have.
    """

    values: dict[date, float | None]
    stale_sessions: frozenset[date]
    unpriced_sessions: frozenset[date]

    def get(self, on: date) -> float | None:
        return self.values.get(on)


@dataclass
class BasketReturnResult:
    window: ReturnWindow
    as_of: date
    start: date | None
    return_raw: float | None
    return_vs_benchmark: float | None
    benchmark_return: float | None
    breadth: float | None
    constituents_priced: int
    constituents_total: int
    priced: list[str] = field(default_factory=list)
    stale: list[str] = field(default_factory=list)
    unpriced: list[str] = field(default_factory=list)

    @property
    def coverage_ratio(self) -> float | None:
        if self.constituents_total == 0:
            return None
        return self.constituents_priced / self.constituents_total


def align_to_calendar(
    closes: Mapping[date, float],
    calendar: Sequence[date],
    max_forward_fill: int,
) -> AlignedSeries:
    """Project a constituent's closes onto the benchmark calendar.

    A session with no close of its own inherits the previous close, but only
    for `max_forward_fill` consecutive sessions. Past that the session is
    marked stale and carries None: a holiday run or a halted stock must not
    quietly contribute a flat return.
    """
    values: dict[date, float | None] = {}
    stale: set[date] = set()
    unpriced: set[date] = set()
    last_close: float | None = None
    filled_run = 0

    for session in calendar:
        actual = closes.get(session)
        if actual is not None:
            values[session] = actual
            last_close = actual
            filled_run = 0
            continue

        if last_close is None:
            # No close has ever been seen; nothing to carry forward. This is a
            # coverage gap, not staleness.
            values[session] = None
            unpriced.add(session)
            continue

        filled_run += 1
        if filled_run <= max_forward_fill:
            values[session] = last_close
        else:
            values[session] = None
            stale.add(session)

    return AlignedSeries(
        values=values,
        stale_sessions=frozenset(stale),
        unpriced_sessions=frozenset(unpriced),
    )


def resolve_window_start(
    window: ReturnWindow, as_of: date, calendar: Sequence[date]
) -> date | None:
    """Find the session that a window's return is measured from.

    Windows are expressed in calendar time, then snapped back to the most
    recent benchmark session at or before that point. `1d` is the previous
    session rather than "yesterday", so a Monday reads against Friday.
    """
    sessions = [d for d in calendar if d <= as_of]
    if len(sessions) < 2:
        return None

    if window is ReturnWindow.d1:
        return sessions[-2]

    if window is ReturnWindow.ytd:
        target = date(as_of.year, 1, 1)
        prior = [d for d in sessions if d < target]
        return prior[-1] if prior else None

    days = {ReturnWindow.d7: 7, ReturnWindow.d30: 30}[window]
    target = as_of - timedelta(days=days)
    prior = [d for d in sessions if d <= target]
    return prior[-1] if prior else None


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def compute_basket_return(
    *,
    window: ReturnWindow,
    as_of: date,
    calendar: Sequence[date],
    constituents: Mapping[str, Mapping[date, float]],
    benchmark: Mapping[date, float],
    max_forward_fill: int = 3,
) -> BasketReturnResult:
    """Compute one basket return.

    `constituents` maps a display ticker to its USD closes. Conversion to USD
    happens upstream; this function assumes it has already been done and does
    not attempt to guess a rate.
    """
    total = len(constituents)
    start = resolve_window_start(window, as_of, calendar)

    if start is None:
        return BasketReturnResult(
            window=window,
            as_of=as_of,
            start=None,
            return_raw=None,
            return_vs_benchmark=None,
            benchmark_return=None,
            breadth=None,
            constituents_priced=0,
            constituents_total=total,
            unpriced=sorted(constituents),
        )

    returns: dict[str, float] = {}
    stale: list[str] = []
    unpriced: list[str] = []

    for ticker, closes in constituents.items():
        aligned = align_to_calendar(closes, calendar, max_forward_fill)
        begin, end = aligned.get(start), aligned.get(as_of)
        if begin is None or end is None:
            # Distinguish "we hold prices but they went stale" from "we never
            # had a price at all" -- these are different data problems.
            if start in aligned.stale_sessions or as_of in aligned.stale_sessions:
                stale.append(ticker)
            else:
                unpriced.append(ticker)
            continue
        if begin == 0:
            unpriced.append(ticker)
            continue
        returns[ticker] = end / begin - 1.0

    bench_start, bench_end = benchmark.get(start), benchmark.get(as_of)
    bench_return = (
        bench_end / bench_start - 1.0
        if bench_start not in (None, 0) and bench_end is not None
        else None
    )

    if not returns:
        return BasketReturnResult(
            window=window,
            as_of=as_of,
            start=start,
            return_raw=None,
            return_vs_benchmark=None,
            benchmark_return=bench_return,
            breadth=None,
            constituents_priced=0,
            constituents_total=total,
            stale=sorted(stale),
            unpriced=sorted(unpriced),
        )

    # Equal weight: the plain mean of constituent returns.
    raw = sum(returns.values()) / len(returns)

    basket_sign = _sign(raw)
    if basket_sign == 0:
        breadth = None
    else:
        agreeing = sum(1 for r in returns.values() if _sign(r) == basket_sign)
        breadth = agreeing / len(returns)

    return BasketReturnResult(
        window=window,
        as_of=as_of,
        start=start,
        return_raw=raw,
        return_vs_benchmark=(raw - bench_return) if bench_return is not None else None,
        benchmark_return=bench_return,
        breadth=breadth,
        constituents_priced=len(returns),
        constituents_total=total,
        priced=sorted(returns),
        stale=sorted(stale),
        unpriced=sorted(unpriced),
    )


def top_movers(
    result: BasketReturnResult,
    returns: Mapping[str, float],
    limit: int = 3,
) -> list[tuple[str, float]] | None:
    """Top contributors, or None when coverage is incomplete.

    A top mover computed on partial coverage is wrong and looks precise, which
    is the worst combination. This returns None rather than a best-effort
    ranking whenever any constituent is missing or stale.
    """
    if result.constituents_total == 0:
        return None
    if result.constituents_priced != result.constituents_total:
        return None
    ranked = sorted(returns.items(), key=lambda kv: abs(kv[1]), reverse=True)
    return ranked[:limit]
