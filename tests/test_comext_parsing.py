"""Comext parser tests against a real saved payload.

Fixture is a verbatim SDMX-CSV response: EU27 imports of CN 8483.40.30 for
2025-06, all partners, both indicators.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime

import pytest

from robotics_radar.ingest.base import IngestError, RawResponse
from robotics_radar.ingest.sources.comext_imports import (
    AGGREGATES,
    QUANTITY_INDICATOR,
    VALUE_INDICATOR,
    ComextImportsFetcher,
    is_real_partner,
)
from tests.fixture_loader import require

FIXTURE = "imports_EU27_84834030_2025-06.csv"


@pytest.fixture(scope="module")
def body():
    return require("comext", FIXTURE).read_text()


@pytest.fixture(scope="module")
def observations(body):
    raw = RawResponse(
        url="https://ec.europa.eu/eurostat/api/comext/dissemination",
        params={"startPeriod": "2025-06"},
        body=body,
        fetched_at=datetime(2026, 8, 19, tzinfo=UTC),
    )
    return [o.with_unit_value() for o in ComextImportsFetcher().normalise(raw)]


class TestIndicators:
    def test_only_value_and_weight_exist(self, body):
        """No supplementary unit: the EU can only ever give EUR/kg."""
        rows = list(csv.DictReader(io.StringIO(body)))
        assert {r["indicators"] for r in rows} == {VALUE_INDICATOR, QUANTITY_INDICATOR}


class TestPartnerFilter:
    def test_aggregates_are_rejected(self):
        for code in AGGREGATES:
            assert not is_real_partner(code)

    def test_pseudo_partners_are_rejected(self):
        """QV/QW are 'not specified' residuals, not countries."""
        for code in ("QV", "QW"):
            assert not is_real_partner(code)

    def test_real_countries_are_accepted(self):
        for code in ("JP", "CH", "TW", "CN", "US", "KR", "DE"):
            assert is_real_partner(code)


class TestNormalise:
    def test_emits_tracked_partners_and_the_extra_eu_aggregate(self, observations):
        names = {o.series_key for o in observations}
        assert any(n.endswith("extra-EU total") for n in names)
        for partner in ("Japan", "Switzerland", "Taiwan", "China"):
            assert any(n.endswith(f"from {partner}") for n in names)

    def test_intra_eu_is_not_emitted(self, observations):
        """Intra-EU trade is members selling to each other: a different question."""
        assert not any("intra" in o.series_key.lower() for o in observations)

    def test_quantity_is_converted_to_kilograms(self, observations, body):
        rows = list(csv.DictReader(io.StringIO(body)))
        raw_100kg = next(
            float(r["OBS_VALUE"])
            for r in rows
            if r["partner"] == "JP" and r["indicators"] == QUANTITY_INDICATOR
        )
        japan = next(o for o in observations if o.series_key.endswith("from Japan"))
        assert japan.quantity == pytest.approx(raw_100kg * 100)
        assert japan.quantity_unit == "KG"

    def test_unit_value_is_euros_per_kilogram(self, observations):
        """Not per screw. The line carries no piece count."""
        japan = next(o for o in observations if o.series_key.endswith("from Japan"))
        assert japan.unit_value == pytest.approx(japan.value / japan.quantity)
        assert 1 < japan.unit_value < 500  # a plausible EUR/kg, not EUR/unit

    def test_period_bounds_cover_the_month(self, observations):
        for o in observations:
            assert o.period_start == date(2025, 6, 1)
            assert o.period_end == date(2025, 6, 30)

    def test_rejects_a_response_with_no_tracked_partners(self):
        body = (
            "DATAFLOW,LAST UPDATE,freq,reporter,partner,product,flow,indicators,"
            "TIME_PERIOD,OBS_VALUE\n"
            "X,Y,M,EU27_2020,BR,84834030,1,VALUE_IN_EUROS,2025-06,100\n"
        )
        raw = RawResponse(url="u", params={"startPeriod": "2025-06"}, body=body,
                          fetched_at=datetime(2026, 8, 19, tzinfo=UTC))
        with pytest.raises(IngestError, match="no tracked partners"):
            list(ComextImportsFetcher().normalise(raw))
