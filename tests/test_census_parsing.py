"""Census parser tests against a real saved payload.

The fixture is a verbatim 2026-06 response for HTS 8483.40.8000. What is
pinned here is the thing that would otherwise silently corrupt the series:
Census mixes individual countries, economic groupings, continent aggregates
and a world total into one undifferentiated response.
"""

from __future__ import annotations

import json

import pytest

from robotics_radar.ingest.sources.census_imports import is_country_code
from tests.fixture_loader import require

FIXTURE = "imports_8483408000_2026-06.json"


@pytest.fixture(scope="module")
def payload():
    return json.loads(require("census", FIXTURE).read_text())


@pytest.fixture(scope="module")
def parsed(payload):
    header, rows = payload[0], payload[1:]
    idx = {k: n for n, k in enumerate(header)}
    return [
        {
            "code": r[idx["CTY_CODE"]],
            "name": r[idx["CTY_NAME"]],
            "value": int(r[idx["GEN_VAL_MO"]] or 0),
            "qty": int(r[idx["GEN_QY1_MO"]] or 0),
            "unit": r[idx["UNIT_QY1"]],
        }
        for r in rows
    ]


class TestCountryFilter:
    def test_aggregates_are_excluded(self):
        # Economic groupings, continent rows, and the world total.
        for code in ("0003", "0022", "0023", "0025", "0026", "-", "4XXX", "5XXX", "1XXX"):
            assert not is_country_code(code), f"{code} should be excluded"

    def test_real_countries_are_kept(self):
        for code in ("5880", "4280", "5830", "5700", "1220", "4419"):
            assert is_country_code(code), f"{code} should be kept"

    def test_countries_reconcile_exactly_to_the_total_row(self, parsed):
        """The whole point: filtered rows must sum to TOTAL, not exceed it."""
        total = next(r for r in parsed if r["code"] == "-")
        countries = [r for r in parsed if is_country_code(r["code"])]
        assert sum(r["value"] for r in countries) == total["value"]
        assert sum(r["qty"] for r in countries) == total["qty"]

    def test_naive_sum_would_massively_double_count(self, parsed):
        """Pins why the filter exists rather than trusting the raw rows."""
        total = next(r for r in parsed if r["code"] == "-")
        naive = sum(r["value"] for r in parsed if r["code"] != "-")
        assert naive > total["value"] * 2


class TestQuantityBasis:
    def test_quantity_is_a_piece_count_not_weight(self, parsed):
        """If this ever changes, the unit value stops meaning $/screw."""
        units = {r["unit"] for r in parsed}
        assert units == {"NO"}, f"expected piece counts only, got {units}"


class TestUnitValueDispersion:
    def test_unit_value_spread_is_extreme(self, parsed):
        """Documents why a blended ASP over this line is not a price signal."""
        uv = [
            r["value"] / r["qty"]
            for r in parsed
            if is_country_code(r["code"]) and r["qty"] > 0
        ]
        assert max(uv) / min(uv) > 1000

    def test_precision_band_origins_cluster(self, parsed):
        """Japan, Germany, Italy and Taiwan agree within a factor of two."""
        by_code = {r["code"]: r for r in parsed}
        band = []
        for code in ("5880", "4280", "4759", "5830"):  # JP, DE, IT, TW
            r = by_code[code]
            band.append(r["value"] / r["qty"])
        assert max(band) / min(band) < 2.0


class TestNormalise:
    """normalise() run against the verbatim 2026-06 response."""

    @pytest.fixture(scope="module")
    def observations(self, payload):
        from datetime import UTC, datetime

        from robotics_radar.ingest.base import RawResponse
        from robotics_radar.ingest.sources.census_imports import CensusImportsFetcher

        raw = RawResponse(
            url="https://api.census.gov/data/timeseries/intltrade/imports/hs",
            params={"time": "2026-06"},
            body=json.dumps(payload),
            fetched_at=datetime(2026, 8, 19, tzinfo=UTC),
        )
        fetcher = CensusImportsFetcher(api_key="test")
        return [o.with_unit_value() for o in fetcher.normalise(raw)]

    def test_emits_tracked_origins_and_the_aggregate(self, observations):
        from robotics_radar.ingest.sources.census_imports import TRACKED_ORIGINS

        assert len(observations) == len(TRACKED_ORIGINS) + 1

    def test_period_bounds_cover_the_whole_month(self, observations):
        from datetime import date

        for o in observations:
            assert o.period_start == date(2026, 6, 1)
            assert o.period_end == date(2026, 6, 30)

    def test_japan_matches_the_payload(self, observations, parsed):
        japan = next(o for o in observations if o.series_key.endswith("from Japan"))
        source = next(r for r in parsed if r["code"] == "5880")
        assert japan.value == source["value"]
        assert japan.quantity == source["qty"]
        assert japan.quantity_unit == "NO"
        assert japan.unit_value == pytest.approx(source["value"] / source["qty"])

    def test_aggregate_carries_no_unit_value(self, observations):
        """The whole point of suppress_unit_value: a mix ratio is not a price."""
        agg = next(o for o in observations if o.series_key.endswith("all origins"))
        assert agg.value == 13_482_077
        assert agg.quantity == 626_176
        assert agg.unit_value is None

    def test_vintage_is_the_fetch_date_not_the_period(self, observations):
        from datetime import date

        assert {o.vintage_date for o in observations} == {date(2026, 8, 19)}
        assert all(o.release_date is None for o in observations)

    def test_rejects_a_response_with_no_country_rows(self):
        from datetime import UTC, datetime

        from robotics_radar.ingest.base import IngestError, RawResponse
        from robotics_radar.ingest.sources.census_imports import CensusImportsFetcher

        body = json.dumps([["CTY_CODE", "CTY_NAME", "GEN_VAL_MO", "GEN_QY1_MO",
                            "UNIT_QY1", "GEN_QY1_MO_FLAG"],
                           ["0022", "OECD", "1", "1", "NO", "-"]])
        raw = RawResponse(url="u", params={"time": "2026-06"}, body=body,
                          fetched_at=datetime(2026, 8, 19, tzinfo=UTC))
        with pytest.raises(IngestError, match="no country rows"):
            list(CensusImportsFetcher(api_key="t").normalise(raw))
