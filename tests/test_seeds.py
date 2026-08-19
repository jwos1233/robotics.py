"""Seed-data integrity.

These guard the properties that make the seed trustworthy: referential
integrity, and the absence of the fabricated values the brief forbids.
"""

from __future__ import annotations

from collections import Counter

import pytest
import yaml

from robotics_radar.models.enums import Bucket, CoverageStatus, PurityGrade
from robotics_radar.seeds.load import SEED_DIR


@pytest.fixture(scope="module")
def nodes():
    return yaml.safe_load((SEED_DIR / "nodes.yaml").read_text())


@pytest.fixture(scope="module")
def securities():
    return yaml.safe_load((SEED_DIR / "securities.yaml").read_text())


@pytest.fixture(scope="module")
def baskets():
    return yaml.safe_load((SEED_DIR / "baskets.yaml").read_text())


class TestNodes:
    def test_buckets_are_valid(self, nodes):
        for n in nodes:
            Bucket(n["bucket"])

    def test_names_unique(self, nodes):
        names = [n["name"] for n in nodes]
        assert len(names) == len(set(names))

    def test_no_severity_or_tier_is_seeded(self, nodes):
        """The scoring methodology is unsettled; seeded numbers would poison it."""
        for n in nodes:
            assert "severity" not in n
            assert "break_point_tier" not in n

    def test_dexterous_hands_node_exists(self, nodes):
        """It has a node and deliberately no basket -- no listed pure play."""
        assert any(n["name"] == "Dexterous Hands" for n in nodes)


class TestSecurities:
    def test_display_tickers_unique(self, securities):
        t = [s["display_ticker"] for s in securities]
        assert len(t) == len(set(t))

    def test_no_source_symbol_is_guessed(self, securities):
        """No price provider is confirmed, so no symbol may be invented."""
        for s in securities:
            assert s["source_symbol"] is None
            assert s["data_source"] is None

    def test_all_coverage_unavailable_until_verified(self, securities):
        for s in securities:
            assert CoverageStatus(s["coverage_status"]) is CoverageStatus.unavailable

    def test_display_ticker_and_local_code_are_separate_fields(self, securities):
        """Bloomberg display style must never be reused as an API symbol."""
        jp = next(s for s in securities if s["display_ticker"] == "6324 JP")
        assert jp["local_code"] == "6324"
        assert jp["exchange_mic"] == "XTKS"
        assert jp["currency"] == "JPY"

    def test_china_a_shares_route_to_the_right_exchange(self, securities):
        by_ticker = {s["display_ticker"]: s for s in securities}
        assert by_ticker["688017 CH"]["exchange_mic"] == "XSHG"   # STAR board
        assert by_ticker["600366 CH"]["exchange_mic"] == "XSHG"   # Shanghai main
        assert by_ticker["002472 CH"]["exchange_mic"] == "XSHE"   # Shenzhen
        assert by_ticker["300748 CH"]["exchange_mic"] == "XSHE"   # ChiNext
        assert by_ticker["003021 CH"]["exchange_mic"] == "XSHE"
        for t in ("688017 CH", "002472 CH"):
            assert by_ticker[t]["currency"] == "CNY"
            assert by_ticker[t]["country"] == "CN"

    def test_us_listings_have_no_guessed_venue(self, securities):
        """XNYS vs XNAS was not verifiable offline, so it is left null."""
        nvda = next(s for s in securities if s["display_ticker"] == "NVDA")
        assert nvda["exchange_mic"] is None
        assert nvda["currency"] == "USD"

    def test_bare_on_ticker_survived_yaml_boolean_coercion(self, securities):
        """YAML 1.1 turns an unquoted ON into True. It must stay a string."""
        tickers = [s["display_ticker"] for s in securities]
        assert "ON" in tickers
        assert True not in tickers


class TestBaskets:
    def test_every_member_resolves_to_a_security(self, baskets, securities):
        known = {s["display_ticker"] for s in securities}
        for b in baskets:
            unknown = set(b["members"]) - known
            assert not unknown, f"{b['name']} references unknown tickers {unknown}"

    def test_every_basket_resolves_to_a_node(self, baskets, nodes):
        known = {n["name"] for n in nodes}
        for b in baskets:
            assert b["node"] in known, f"{b['name']} references unknown node {b['node']}"

    def test_purity_grade_present_and_valid_on_every_basket(self, baskets):
        for b in baskets:
            PurityGrade(b["purity_grade"])

    def test_demand_baskets_have_no_constraint_bucket(self, baskets):
        for b in baskets:
            if b.get("is_demand_side"):
                assert b.get("bucket") is None
            else:
                Bucket(b["bucket"])

    def test_no_ticker_repeats_within_one_basket(self, baskets):
        for b in baskets:
            dupes = [t for t, n in Counter(b["members"]).items() if n > 1]
            assert not dupes, f"{b['name']} repeats {dupes}"

    def test_narrative_baskets_named_in_the_brief_are_narrative(self, baskets):
        by_name = {b["name"]: b for b in baskets}
        for name in (
            "Linear Actuation & Roller Screws",
            "Abrasives & Superhard Tooling",
            "Electrical Steel & Laminations",
            "Bearing Steel & Structural",
            "Inertial",
            "BMS & Power Conversion",
            "Humanoid OEM",
        ):
            assert by_name[name]["purity_grade"] == "narrative"

    def test_roller_screw_basket_carries_its_caveat(self, baskets):
        b = next(x for x in baskets if x["name"] == "Linear Actuation & Roller Screws")
        assert "private" in b["caveat_note"].lower()

    def test_shared_node_flags_set(self, baskets):
        shared = {b["name"] for b in baskets if b.get("is_shared_node")}
        assert shared == {"Edge Inference Silicon", "Passives & Interconnect"}

    def test_no_basket_exists_for_dexterous_hands(self, baskets):
        """Rendered as a watchlist entry, not an empty basket."""
        assert not any("Dexterous Hand" in b["name"] for b in baskets)

    def test_known_overlaps_are_present(self, baskets):
        """Overlap is legitimate but makes baskets non-independent."""
        counts = Counter(t for b in baskets for t in b["members"])
        for t in ("002472 CH", "6383 JP", "6762 JP", "ADI", "TXN", "RSW LN", "SHA0 GY"):
            assert counts[t] >= 2, f"{t} expected in at least two baskets"
