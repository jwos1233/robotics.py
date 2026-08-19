"""Derived metrics.

The point of this layer is to find an inflection without being told what one
looks like, so what matters is that the arithmetic is right and that gaps
never produce a confident wrong answer.
"""

from __future__ import annotations

from datetime import date

import pytest

from robotics_radar.analysis import (
    Point,
    acceleration,
    mom_pct,
    rolling_mean,
    to_points,
    yoy_pct,
    z_scores,
)


def months(start: date, values: list[float]) -> list[Point]:
    out, y, m = [], start.year, start.month
    for v in values:
        out.append(Point(date(y, m, 1), v))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


class TestGrowth:
    def test_yoy_matches_the_same_calendar_month(self):
        pts = months(date(2024, 1, 1), [100] * 12 + [125])
        got = yoy_pct(pts)
        assert got[-1].period == date(2025, 1, 1)
        assert got[-1].value == pytest.approx(25.0)

    def test_gap_produces_no_comparison(self):
        """Positional lags would compare the wrong months instead."""
        pts = [Point(date(2024, 1, 1), 100), Point(date(2025, 3, 1), 150)]
        assert yoy_pct(pts) == []

    def test_mom_crosses_a_year_boundary(self):
        pts = [Point(date(2024, 12, 1), 200), Point(date(2025, 1, 1), 150)]
        assert mom_pct(pts)[0].value == pytest.approx(-25.0)

    def test_negative_base_uses_magnitude(self):
        pts = [Point(date(2024, 1, 1), -100), Point(date(2024, 2, 1), -50)]
        assert mom_pct(pts)[0].value == pytest.approx(50.0)

    def test_zero_base_is_skipped(self):
        pts = [Point(date(2024, 1, 1), 0), Point(date(2024, 2, 1), 10)]
        assert mom_pct(pts) == []


class TestAcceleration:
    def test_steady_growth_has_zero_acceleration(self):
        """Fast and steady is not inflecting -- the whole distinction."""
        vals = [100 * (1.02 ** i) for i in range(26)]
        acc = acceleration(months(date(2024, 1, 1), vals))
        assert acc
        assert all(abs(p.value) < 0.01 for p in acc)

    def test_rising_growth_rate_shows_positive_acceleration(self):
        base = [100] * 13
        ramp = [100 * (1 + 0.05 * i) for i in range(1, 13)]
        acc = acceleration(months(date(2024, 1, 1), base + ramp))
        assert acc
        assert acc[-1].value > 0

    def test_needs_two_years_before_reporting(self):
        assert acceleration(months(date(2024, 1, 1), [100] * 13)) == []


class TestZScores:
    def test_expanding_window_never_uses_the_future(self):
        """A spike must not look ordinary because of what follows it."""
        # A mildly noisy baseline, then a step. Real series are never perfectly
        # flat, and a flat one has no spread to score against at all.
        baseline = [10, 11, 9, 10, 12, 9, 11, 10, 9, 11]
        pts = months(date(2024, 1, 1), baseline + [100] * 7)
        z = z_scores(pts, min_history=8)
        spike = next(p for p in z if p.period == date(2024, 11, 1))
        assert spike.value > 3
        # Scored on prior history only, so the later 100s cannot flatten it.
        assert spike.value > next(
            p.value for p in z if p.period == date(2025, 5, 1)
        )

    def test_short_history_yields_nothing(self):
        assert z_scores(months(date(2024, 1, 1), [1, 2, 3]), min_history=8) == []

    def test_flat_history_is_skipped_not_divided_by_zero(self):
        assert z_scores(months(date(2024, 1, 1), [5] * 12), min_history=8) == []


class TestHelpers:
    def test_to_points_drops_nulls(self):
        pts = to_points([(date(2024, 1, 1), None), (date(2024, 2, 1), 5)])
        assert [p.value for p in pts] == [5]

    def test_rolling_mean_is_trailing(self):
        pts = months(date(2024, 1, 1), [0, 0, 3])
        assert rolling_mean(pts, 3)[-1].value == pytest.approx(1.0)
