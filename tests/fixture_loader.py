"""Load Phase 0 fixtures, skipping cleanly when one has not arrived yet.

Parser tests are written against real saved payloads. Until a payload exists
for a source, its tests skip with a message naming what is missing, so the
suite stays green while making the gap visible rather than hiding it.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def fixture_path(source: str, name: str) -> Path:
    return FIXTURE_DIR / source / name


def require(source: str, name: str) -> Path:
    """Return the fixture path, or skip the test if it is not present."""
    path = fixture_path(source, name)
    if not path.exists():
        pytest.skip(
            f"fixture {source}/{name} not captured yet "
            f"— see tests/fixtures/README.md"
        )
    return path


def load_json(source: str, name: str):
    return json.loads(require(source, name).read_text())


def load_text(source: str, name: str) -> str:
    return require(source, name).read_text()


def available(source: str) -> list[str]:
    """Fixtures captured for a source, ignoring directory placeholders."""
    directory = FIXTURE_DIR / source
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.name != ".gitkeep")
