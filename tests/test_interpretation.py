"""A narrative basket must never read like a pure one."""

from __future__ import annotations

from robotics_radar.api.interpretation import coverage_caveat, interpretation_for
from robotics_radar.models.enums import PurityGrade


def test_narrative_and_pure_do_not_read_identically():
    pure = interpretation_for(PurityGrade.pure, False)
    narrative = interpretation_for(PurityGrade.narrative, False)
    mixed = interpretation_for(PurityGrade.mixed, False)
    assert len({pure, narrative, mixed}) == 3


def test_narrative_says_sentiment_not_constraint():
    text = interpretation_for(PurityGrade.narrative, False).lower()
    assert "sentiment" in text
    assert "not constraint" in text


def test_demand_side_is_called_out():
    text = interpretation_for(PurityGrade.narrative, True)
    assert "demand-side" in text


def test_every_interpretation_carries_the_forward_map_caveat():
    for grade in PurityGrade:
        for demand in (True, False):
            assert "not a live tightness gauge" in interpretation_for(grade, demand)


def test_partial_coverage_caveat_states_the_ratio():
    assert "4 of 8" in coverage_caveat(4, 8)


def test_empty_basket_caveat_is_by_design():
    assert "by design" in coverage_caveat(0, 0)
