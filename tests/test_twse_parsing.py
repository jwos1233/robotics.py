"""TWSE monthly revenue parser tests against a real saved filing."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from robotics_radar.ingest.base import IngestError, RawResponse
from robotics_radar.ingest.sources.twse_revenue import (
    TwseRevenueFetcher,
    roc_to_date,
    series_name,
)
from robotics_radar.models.enums import FlowDirection
from tests.fixture_loader import require

FIXTURE = "t187ap05_L_11507.json"


@pytest.fixture(scope="module")
def body():
    return require("twse", FIXTURE).read_text()


@pytest.fixture(scope="module")
def observations(body):
    raw = RawResponse(
        url="https://openapi.twse.com.tw/v1/opendata/t187ap05_L",
        params={"period": "2026-07"},
        body=body,
        fetched_at=datetime(2026, 8, 19, tzinfo=UTC),
    )
    return [o.with_unit_value() for o in TwseRevenueFetcher().normalise(raw)]


class TestRocCalendar:
    def test_reporting_month(self):
        """ROC year 115 is Gregorian 2026."""
        assert roc_to_date("11507") == date(2026, 7, 1)

    def test_publication_date(self):
        assert roc_to_date("1150817") == date(2026, 8, 17)

    def test_century_boundary(self):
        assert roc_to_date("09912") == date(2010, 12, 1)

    def test_rejects_unrecognised_length(self):
        with pytest.raises(IngestError, match="unrecognised ROC date"):
            roc_to_date("115")


class TestNormalise:
    def test_only_tracked_companies_are_emitted(self, observations, body):
        assert len(observations) == 7
        assert len(json.loads(body)) > 7  # fixture contains untracked filers

    def test_hiwin_revenue_is_converted_from_thousands(self, observations):
        hiwin = next(o for o in observations if "Hiwin" in o.series_key)
        assert hiwin.value == 2_681_646 * 1000
        assert hiwin.series_key == series_name("Hiwin Technologies")

    def test_release_date_is_distinct_from_the_period(self, observations):
        """The one source that dates its own publication."""
        for o in observations:
            assert o.release_date == date(2026, 8, 17)
            assert o.period_start == date(2026, 7, 1)
            assert o.release_date > o.period_end

    def test_period_end_is_the_last_day_of_the_month(self, observations):
        for o in observations:
            assert o.period_end == date(2026, 7, 31)

    def test_no_unit_value_since_no_quantity_is_disclosed(self, observations):
        for o in observations:
            assert o.unit_value is None
            assert o.quantity is None

    def test_wrong_month_is_refused_rather_than_stored(self, body):
        """Snapshot endpoint: never record a month we did not ask for."""
        raw = RawResponse(
            url="u",
            params={"period": "2026-03"},
            body=body,
            fetched_at=datetime(2026, 8, 19, tzinfo=UTC),
        )
        with pytest.raises(IngestError, match="no historical endpoint"):
            list(TwseRevenueFetcher().normalise(raw))


class TestSeriesSpecs:
    def test_revenue_is_its_own_flow_direction(self):
        """Not 'production' -- a financial figure is not an output volume."""
        for spec in TwseRevenueFetcher().series_specs():
            assert spec.flow_direction is FlowDirection.revenue

    def test_hiwin_is_linked_to_the_linear_motion_node(self):
        spec = next(
            s for s in TwseRevenueFetcher().series_specs() if "Hiwin" in s.name
        )
        assert spec.node_name == "Bearings & Linear Motion"

    def test_every_spec_carries_the_backfill_limitation(self):
        for spec in TwseRevenueFetcher().series_specs():
            assert "cannot be backfilled" in spec.known_limitations


class TestEvidenceGrade:
    def test_disclosed_not_measured(self):
        """A company reporting its own revenue is not a measurement."""
        from robotics_radar.models.enums import EvidenceGrade

        for spec in TwseRevenueFetcher().series_specs():
            assert spec.evidence_grade is EvidenceGrade.disclosed

    def test_customs_sources_remain_measured(self):
        from robotics_radar.ingest.sources.census_imports import CensusImportsFetcher
        from robotics_radar.models.enums import EvidenceGrade

        for spec in CensusImportsFetcher(api_key="t").series_specs():
            assert spec.evidence_grade is EvidenceGrade.measured
