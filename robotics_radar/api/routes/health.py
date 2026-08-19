from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from robotics_radar.config import get_settings
from robotics_radar.db import get_db
from robotics_radar.schemas import HealthOut

router = APIRouter(tags=["ops"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    """Railway health check target.

    Reports database reachability rather than only process liveness: a web
    process that cannot reach Postgres serves nothing useful.
    """
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - health must not raise
        database = "unreachable"
    return HealthOut(
        status="ok" if database == "ok" else "degraded",
        database=database,
        app_env=get_settings().app_env,
    )
