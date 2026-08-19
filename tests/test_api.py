"""API integration tests against a migrated, seeded database.

Skipped unless DATABASE_URL points at one. What is pinned here is the contract
the brief requires: caveats travel with every number, and the endpoints that
were deliberately omitted stay omitted.
"""

from __future__ import annotations


class TestHealth:
    def test_health_reports_database(self, api_client):
        body = api_client.get("/health").json()
        assert body["status"] == "ok"
        assert body["database"] == "ok"


class TestNodes:
    def test_no_node_exposes_a_severity_or_tier(self, api_client):
        for node in api_client.get("/nodes").json():
            assert node["severity"] is None
            assert node["break_point_tier"] is None

    def test_bucket_filter(self, api_client):
        rows = api_client.get("/nodes?bucket=materials").json()
        assert rows
        assert {r["bucket"] for r in rows} == {"materials"}

    def test_unknown_node_404s(self, api_client):
        assert api_client.get("/nodes/999999").status_code == 404


class TestSeries:
    def test_every_series_carries_methodology_and_limitations(self, api_client):
        rows = api_client.get("/series").json()
        assert rows
        for s in rows:
            assert s["methodology_note"], f"{s['name']} has no methodology note"
            assert s["known_limitations"], f"{s['name']} has no known limitations"

    def test_roller_screw_series_declares_the_blind_spot(self, api_client):
        """The intra-Asia hole must be stated on this series, not buried."""
        rows = api_client.get("/series?flow=import").json()
        assert rows
        for s in rows:
            assert "intra-Asia" in s["known_limitations"]
            assert "wrong basin" in s["known_limitations"]

    def test_us_and_eu_lines_are_separate_series_not_blended(self, api_client):
        codes = {s["tariff_code"]: s for s in api_client.get("/series?flow=import").json()}
        assert "8483408000" in codes
        assert "84834030" in codes
        assert codes["8483408000"]["geography"] != codes["84834030"]["geography"]

    def test_observations_default_to_latest_vintage(self, api_client):
        sid = api_client.get("/series").json()[0]["id"]
        body = api_client.get(f"/series/{sid}/observations").json()
        assert body["vintage"] == "latest"
        assert "methodology_note" in body["series"]


class TestBaskets:
    def test_every_basket_carries_purity_and_interpretation(self, api_client):
        rows = api_client.get("/baskets").json()
        assert rows
        for b in rows:
            assert b["purity_grade"] in {"pure", "mixed", "narrative"}
            assert b["interpretation"]

    def test_no_basket_exposes_a_constraint_score(self, api_client):
        """Baskets link a node by name only."""
        for b in api_client.get("/baskets").json():
            assert "severity" not in b
            assert "score" not in b
            assert "break_point_tier" not in b
            assert b["node_name"] is not None or b["node_id"] is None

    def test_narrative_baskets_read_differently_from_pure(self, api_client):
        pure = api_client.get("/baskets?purity=pure").json()
        narrative = api_client.get("/baskets?purity=narrative").json()
        assert pure and narrative
        assert "SENTIMENT" in narrative[0]["interpretation"]
        assert "SENTIMENT" not in pure[0]["interpretation"]

    def test_demand_side_filter(self, api_client):
        rows = api_client.get("/baskets?demand_side=true").json()
        assert {r["name"] for r in rows} == {"Humanoid OEM", "Mobile Manipulation & AMR"}

    def test_detail_returns_roster_and_caveats(self, api_client):
        rows = api_client.get("/baskets?purity=narrative").json()
        bid = next(r["id"] for r in rows if r["name"] == "Linear Actuation & Roller Screws")
        body = api_client.get(f"/baskets/{bid}").json()
        assert len(body["members"]) == 6
        assert "Rollvis" in body["caveat_note"]
        assert body["members"][0]["display_ticker"]

    def test_returns_report_coverage_rather_than_a_fake_zero(self, api_client):
        bid = api_client.get("/baskets").json()[0]["id"]
        body = api_client.get(f"/baskets/{bid}/returns?window=30d").json()
        assert body["return_raw"] is None
        assert body["constituents_total"] > 0
        assert body["constituents_priced"] == 0
        assert body["benchmark_symbol"] == "ACWI"
        assert body["benchmark_symbol"] != "SPY"

    def test_returns_carry_purity_so_the_number_cannot_be_read_bare(self, api_client):
        bid = api_client.get("/baskets").json()[0]["id"]
        body = api_client.get(f"/baskets/{bid}/returns").json()
        assert body["purity_grade"]
        assert body["interpretation"]


class TestOverlap:
    def test_overlap_matrix_surfaces_shared_membership(self, api_client):
        body = api_client.get("/baskets/overlap").json()
        assert body["baskets"] == 25
        assert body["pairs"]
        for p in body["pairs"]:
            assert p["shared_count"] == len(p["shared"])
            assert 0 < p["jaccard"] <= 1

    def test_demand_constraint_dependency_is_visible(self, api_client):
        """002472 CH sits in both Precision Reducers and Humanoid OEM."""
        body = api_client.get("/baskets/overlap").json()
        pair = next(
            p
            for p in body["pairs"]
            if {"Humanoid OEM", "Precision Reducers"} == {p["basket_a"], p["basket_b"]}
        )
        assert "002472 CH" in pair["shared"]


class TestDeliberateOmissions:
    def test_no_what_flipped_endpoint(self, api_client):
        """Requires severity scoring, which does not exist. Omitted, not faked."""
        paths = api_client.get("/openapi.json").json()["paths"]
        assert not any("flip" in p for p in paths)

    def test_no_top_mover_endpoint(self, api_client):
        paths = api_client.get("/openapi.json").json()["paths"]
        assert not any("mover" in p for p in paths)
