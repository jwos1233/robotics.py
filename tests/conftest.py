from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session")
def api_client():
    """TestClient bound to a live database, or skip.

    These are integration tests: they need a migrated, seeded Postgres. Set
    DATABASE_URL to run them. Without one they skip rather than fail, so the
    unit suite stays runnable anywhere.
    """
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set; skipping API integration tests")

    from fastapi.testclient import TestClient

    from robotics_radar.api.main import app
    from robotics_radar.db import get_sessionmaker

    try:
        from sqlalchemy import text

        with get_sessionmaker()() as s:
            s.execute(text("SELECT 1 FROM nodes LIMIT 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"database not migrated/seeded: {exc}")

    return TestClient(app)
