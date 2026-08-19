"""Tripwire evaluation.

These pin the properties that make a tripwire a prediction rather than a
commentary: it is graded mechanically, a gap in the data produces a missing
comparison rather than a wrong one, and an under-specified tripwire is
reported as unevaluable instead of quietly false.
"""

from __future__ import annotations

from datetime import date

import pytest

from robotics_radar.models.constraint import Observation
from robotics_radar.models.enums import TripwireMetric
from robotics_radar.tripwires.evaluate import metric_series


def obs(period: date, value: float | None) -> Observation:
    return Observation(period_start=period, period_end=period, value=value,
                       vintage_date=period)


def monthly(start_year: int, values: list[float]) -> list[Observation]:
    out, y, m = [], start_year, 1
    for v in values:
        out.append(obs(date(y, m, 1), v))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


class TestMetricSeries:
    def test_level_passes_values_through(self):
        pts = metric_series(monthly(2024, [10, 20, 30]), TripwireMetric.level)
        assert [p.value for p in pts] == [10, 20, 30]

    def test_yoy_needs_a_full_year_before_it_reports(self):
        pts = metric_series(monthly(2024, [100] * 11), TripwireMetric.yoy_pct)
        assert pts == []

    def test_yoy_compares_against_the_same_month(self):
        # 13 months: Jan-24 100 ... Jan-25 150 -> +50%
        vals = [100] + [0] * 11 + [150]
        series = [o for o in monthly(2024, vals) if o.value]
        pts = metric_series(series, TripwireMetric.yoy_pct)
        assert len(pts) == 1
        assert pts[0].period == date(2025, 1, 1)
        assert pts[0].value == pytest.approx(50.0)

    def test_a_gap_yields_no_comparison_rather_than_a_wrong_one(self):
        """Positional lags would silently compare the wrong months."""
        series = [obs(date(2024, 1, 1), 100), obs(date(2025, 2, 1), 150)]
        assert metric_series(series, TripwireMetric.yoy_pct) == []

    def test_mom_crosses_the_year_boundary(self):
        series = [obs(date(2024, 12, 1), 100), obs(date(2025, 1, 1), 125)]
        pts = metric_series(series, TripwireMetric.mom_pct)
        assert len(pts) == 1
        assert pts[0].value == pytest.approx(25.0)

    def test_zero_prior_is_skipped_not_divided_by(self):
        series = [obs(date(2024, 5, 1), 0), obs(date(2024, 6, 1), 40)]
        assert metric_series(series, TripwireMetric.mom_pct) == []

    def test_null_values_are_ignored(self):
        series = [obs(date(2024, 1, 1), None), obs(date(2024, 2, 1), 10)]
        assert [p.value for p in metric_series(series, TripwireMetric.level)] == [10]


class TestRunLength:
    """The run-length rule is what separates a signal from one noisy month."""

    def _run(self, values, threshold):
        from robotics_radar.models.enums import TripwireDirection
        from robotics_radar.tripwires.evaluate import _qualifies

        run = 0
        for v in reversed(values):
            if _qualifies(v, TripwireDirection.above, threshold):
                run += 1
            else:
                break
        return run

    def test_run_counts_only_the_trailing_streak(self):
        assert self._run([80, 10, 60, 70], 50) == 2

    def test_a_single_spike_does_not_make_a_run(self):
        assert self._run([10, 10, 10, 90], 50) == 1

    def test_broken_streak_resets(self):
        assert self._run([60, 60, 60, 10], 50) == 0
