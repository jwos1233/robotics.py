"""Unit tests for the basket computation rules.

These are the rules a caller relies on being true, so each one is pinned:
equal weighting, staleness handling, breadth, and partial-coverage reporting.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from robotics_radar.baskets.compute import (
    align_to_calendar,
    compute_basket_return,
    resolve_window_start,
    top_movers,
)
from robotics_radar.models.enums import ReturnWindow


def cal(n: int, start: date = date(2026, 1, 5)) -> list[date]:
    """n consecutive weekday sessions, standing in for a benchmark calendar."""
    out: list[date] = []
    d = start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def flat(calendar, value: float) -> dict[date, float]:
    return dict.fromkeys(calendar, value)


class TestAlignToCalendar:
    def test_missing_session_is_forward_filled(self):
        c = cal(5)
        closes = {c[0]: 100.0, c[1]: 101.0, c[3]: 103.0}
        a = align_to_calendar(closes, c, max_forward_fill=3)
        assert a.get(c[2]) == 101.0
        assert c[2] not in a.stale_sessions

    def test_forward_fill_stops_after_limit_and_marks_stale(self):
        c = cal(8)
        closes = {c[0]: 100.0}
        a = align_to_calendar(closes, c, max_forward_fill=3)
        # Three sessions carry the last close...
        assert [a.get(c[i]) for i in (1, 2, 3)] == [100.0, 100.0, 100.0]
        # ...the fourth is stale rather than silently flat.
        assert a.get(c[4]) is None
        assert c[4] in a.stale_sessions

    def test_fresh_close_resets_the_fill_run(self):
        c = cal(9)
        closes = {c[0]: 100.0, c[4]: 110.0}
        a = align_to_calendar(closes, c, max_forward_fill=3)
        assert a.get(c[4]) == 110.0
        assert [a.get(c[i]) for i in (5, 6, 7)] == [110.0, 110.0, 110.0]
        assert a.get(c[8]) is None

    def test_sessions_before_first_close_are_unpriced_not_backfilled(self):
        c = cal(4)
        a = align_to_calendar({c[2]: 50.0}, c, max_forward_fill=3)
        assert a.get(c[0]) is None
        assert c[0] in a.unpriced_sessions
        assert c[0] not in a.stale_sessions


class TestResolveWindowStart:
    def test_1d_is_the_previous_session_not_yesterday(self):
        c = cal(6, start=date(2026, 1, 5))  # Mon 5th .. Mon 12th
        monday = c[5]
        assert monday.weekday() == 0
        assert resolve_window_start(ReturnWindow.d1, monday, c) == c[4]  # prior Friday

    def test_30d_snaps_back_to_a_session(self):
        c = cal(40)
        got = resolve_window_start(ReturnWindow.d30, c[-1], c)
        assert got is not None
        assert got in c
        assert got <= c[-1] - timedelta(days=30)

    def test_ytd_uses_last_session_of_prior_year(self):
        c = [date(2025, 12, 30), date(2025, 12, 31), date(2026, 1, 2), date(2026, 1, 5)]
        assert resolve_window_start(ReturnWindow.ytd, date(2026, 1, 5), c) == date(2025, 12, 31)

    def test_returns_none_without_enough_history(self):
        c = [date(2026, 1, 5)]
        assert resolve_window_start(ReturnWindow.d1, c[0], c) is None


class TestComputeBasketReturn:
    def test_equal_weight_not_cap_weight(self):
        """A mega-cap and a micro-cap must contribute identically."""
        c = cal(3)
        constituents = {
            "MEGA": {c[0]: 1000.0, c[1]: 1000.0, c[2]: 1100.0},   # +10%
            "MICRO": {c[0]: 1.0, c[1]: 1.0, c[2]: 1.2},            # +20%
        }
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[2],
            calendar=c,
            constituents=constituents,
            benchmark=flat(c, 100.0),
        )
        assert r.return_raw == pytest.approx(0.15)  # mean, not 10.0009%

    def test_usd_returns_are_averaged_plainly(self):
        c = cal(2)
        constituents = {
            "A": {c[0]: 10.0, c[1]: 11.0},   # +10%
            "B": {c[0]: 10.0, c[1]: 9.0},    # -10%
        }
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[1],
            calendar=c,
            constituents=constituents,
            benchmark=flat(c, 100.0),
        )
        assert r.return_raw == pytest.approx(0.0)

    def test_benchmark_excess_is_reported_separately(self):
        c = cal(2)
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[1],
            calendar=c,
            constituents={"A": {c[0]: 100.0, c[1]: 110.0}},
            benchmark={c[0]: 100.0, c[1]: 104.0},
        )
        assert r.return_raw == pytest.approx(0.10)
        assert r.benchmark_return == pytest.approx(0.04)
        assert r.return_vs_benchmark == pytest.approx(0.06)

    def test_breadth_flags_a_move_carried_by_one_name(self):
        c = cal(2)
        constituents = {
            "BIG": {c[0]: 100.0, c[1]: 200.0},   # +100%
            "F1": {c[0]: 100.0, c[1]: 99.0},
            "F2": {c[0]: 100.0, c[1]: 99.0},
            "F3": {c[0]: 100.0, c[1]: 99.0},
        }
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[1],
            calendar=c,
            constituents=constituents,
            benchmark=flat(c, 100.0),
        )
        assert r.return_raw > 0
        # One of four names moves with the basket: below the 0.5 flag line.
        assert r.breadth == pytest.approx(0.25)

    def test_breadth_is_one_when_all_agree(self):
        c = cal(2)
        constituents = {
            "A": {c[0]: 100.0, c[1]: 105.0},
            "B": {c[0]: 100.0, c[1]: 103.0},
        }
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[1],
            calendar=c,
            constituents=constituents,
            benchmark=flat(c, 100.0),
        )
        assert r.breadth == pytest.approx(1.0)

    def test_partial_coverage_is_surfaced(self):
        c = cal(8)
        constituents = {
            "PRICED": dict.fromkeys(c, 100.0) | {c[-1]: 110.0},
            "GONE": {c[0]: 100.0},          # goes stale well before as_of
            "NEVER": {},                    # never had a price
        }
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[-1],
            calendar=c,
            constituents=constituents,
            benchmark=flat(c, 100.0),
            max_forward_fill=3,
        )
        assert r.constituents_total == 3
        assert r.constituents_priced == 1
        assert r.coverage_ratio == pytest.approx(1 / 3)
        assert "GONE" in r.stale
        assert "NEVER" in r.unpriced

    def test_stale_price_does_not_contribute_a_flat_return(self):
        """The whole point of the staleness cap: no silent zero-return names."""
        c = cal(8)
        constituents = {
            "LIVE": dict.fromkeys(c, 100.0) | {c[-1]: 120.0},
            "STALE": {c[0]: 100.0},
        }
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[-1],
            calendar=c,
            constituents=constituents,
            benchmark=flat(c, 100.0),
        )
        # If STALE had been carried it would halve this to ~10%.
        assert r.return_raw == pytest.approx(0.20)
        assert r.constituents_priced == 1

    def test_zero_priced_constituents_yields_null_not_zero(self):
        c = cal(3)
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[-1],
            calendar=c,
            constituents={"A": {}, "B": {}},
            benchmark=flat(c, 100.0),
        )
        assert r.return_raw is None
        assert r.breadth is None
        assert r.constituents_priced == 0

    def test_empty_basket_is_handled(self):
        """Dexterous Hands has a node and no members by design."""
        c = cal(3)
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[-1],
            calendar=c,
            constituents={},
            benchmark=flat(c, 100.0),
        )
        assert r.constituents_total == 0
        assert r.return_raw is None
        assert r.coverage_ratio is None


class TestTopMovers:
    def test_refused_on_partial_coverage(self):
        c = cal(8)
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[-1],
            calendar=c,
            constituents={
                "A": dict.fromkeys(c, 100.0) | {c[-1]: 110.0},
                "B": {c[0]: 100.0},
            },
            benchmark=flat(c, 100.0),
        )
        assert r.constituents_priced < r.constituents_total
        assert top_movers(r, {"A": 0.10}) is None

    def test_allowed_on_complete_coverage(self):
        c = cal(2)
        r = compute_basket_return(
            window=ReturnWindow.d1,
            as_of=c[1],
            calendar=c,
            constituents={
                "A": {c[0]: 100.0, c[1]: 110.0},
                "B": {c[0]: 100.0, c[1]: 95.0},
            },
            benchmark=flat(c, 100.0),
        )
        movers = top_movers(r, {"A": 0.10, "B": -0.05}, limit=1)
        assert movers == [("A", pytest.approx(0.10))]
