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
