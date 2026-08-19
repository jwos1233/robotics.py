"""Derived series: growth, acceleration, and departure from a series' own history.

An inflection is not a level and not even a growth rate -- it is growth
*changing*. Detecting it against a hard-coded threshold requires knowing the
answer in advance, which for a market with no history nobody does. So the
comparison here is against each series' own past: how unusual is this reading
for this instrument?

Three layers, in order of what they answer:

* `yoy_pct` -- is it growing? Year-on-year, because month-on-month in monthly
  customs data is dominated by shipment timing.
* `acceleration` -- is the growth rate itself rising? This is the derivative
  that an inflection actually consists of.
* `z_scores` -- is that unusual *for this series*? Self-calibrating, so a
  volatile instrument is not mistaken for an inflecting one.

Every function matches on calendar period rather than array position, so a gap
in the data produces a missing comparison instead of a silently wrong one.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Point:
    period: date
    value: float


def _prior_period(period: date, months: int) -> date:
    total = period.year * 12 + (period.month - 1) - months
    return date(total // 12, total % 12 + 1, 1)


def to_points(pairs: Sequence[tuple[date, float | None]]) -> list[Point]:
    return [Point(p, float(v)) for p, v in pairs if v is not None]


def growth_pct(points: Sequence[Point], months: int) -> list[Point]:
    """Percent change against the reading `months` earlier, matched by period."""
    lookup = {p.period: p.value for p in points}
    out: list[Point] = []
    for p in points:
        prior = lookup.get(_prior_period(p.period, months))
        if prior is None or prior == 0:
            continue
        out.append(Point(p.period, (p.value - prior) / abs(prior) * 100.0))
    return out


def yoy_pct(points: Sequence[Point]) -> list[Point]:
    return growth_pct(points, 12)


def mom_pct(points: Sequence[Point]) -> list[Point]:
    return growth_pct(points, 1)


def acceleration(points: Sequence[Point]) -> list[Point]:
    """Change in year-on-year growth, in percentage points.

    This is the inflection term. A series can grow fast and steadily without
    inflecting; what marks a turn is the growth rate itself moving.
    """
    yoy = yoy_pct(points)
    lookup = {p.period: p.value for p in yoy}
    out: list[Point] = []
    for p in yoy:
        prior = lookup.get(_prior_period(p.period, 1))
        if prior is None:
            continue
        out.append(Point(p.period, p.value - prior))
    return out


def z_scores(points: Sequence[Point], min_history: int = 8) -> list[Point]:
    """How unusual each reading is against the series' own prior history.

    Expanding-window: each point is scored against everything before it, never
    against the future. A reading cannot look unremarkable because of what
    happened after it.
    """
    out: list[Point] = []
    for i, p in enumerate(points):
        history = [q.value for q in points[:i]]
        if len(history) < min_history:
            continue
        spread = statistics.pstdev(history)
        if spread == 0:
            continue
        out.append(Point(p.period, (p.value - statistics.fmean(history)) / spread))
    return out


def rolling_mean(points: Sequence[Point], window: int) -> list[Point]:
    """Trailing mean over `window` periods, for smoothing display only."""
    out: list[Point] = []
    for i, p in enumerate(points):
        chunk = [q.value for q in points[max(0, i - window + 1) : i + 1]]
        out.append(Point(p.period, statistics.fmean(chunk)))
    return out
