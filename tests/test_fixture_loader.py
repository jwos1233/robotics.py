"""The fixture loader must skip, not fail, on a payload that has not arrived."""

from __future__ import annotations

import pytest

from tests.fixture_loader import FIXTURE_DIR, available, require


def test_missing_fixture_skips_with_a_pointer():
    with pytest.raises(pytest.skip.Exception) as exc:
        require("census", "definitely_not_captured.json")
    assert "README" in str(exc.value)


def test_placeholders_are_not_reported_as_fixtures():
    """An empty directory must read as empty, not as one .gitkeep fixture."""
    assert available("census") == [] or ".gitkeep" not in available("census")


def test_every_documented_source_has_a_directory():
    for source in ("census", "comext", "jmtba", "nbs", "estat", "equity", "fx"):
        assert (FIXTURE_DIR / source).is_dir(), f"missing fixture dir for {source}"
