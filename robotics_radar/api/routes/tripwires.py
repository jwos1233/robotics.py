from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from robotics_radar.db import get_db
from robotics_radar.models.constraint import Node, Series, Tripwire
from robotics_radar.models.enums import TripwireStatus
from robotics_radar.schemas import TripwireOut
from robotics_radar.tripwires import evaluate_tripwire

router = APIRouter(tags=["constraints"])


def _to_out(db: Session, tw: Tripwire) -> TripwireOut:
    ev = evaluate_tripwire(db, tw)
    node = db.get(Node, tw.node_id)
    series = db.get(Series, tw.observable_series_id) if tw.observable_series_id else None
    return TripwireOut(
        id=tw.id,
        node_id=tw.node_id,
        node_name=node.name if node else None,
        statement=tw.statement,
        series_id=tw.observable_series_id,
        series_name=series.name if series else None,
        metric=ev.metric,
        direction=ev.direction,
        threshold=ev.threshold,
        consecutive_periods=ev.consecutive_periods,
        review_date=tw.review_date,
        status=tw.status,
        tripped=ev.tripped,
        observed_run=ev.observed_run,
        latest_period=ev.latest_period,
        latest_value=ev.latest_value,
        distance_to_threshold=ev.distance_to_threshold,
        evaluable=ev.evaluable,
        reason=ev.reason,
    )


@router.get("/tripwires", response_model=list[TripwireOut])
def list_tripwires(
    node: int | None = Query(None, description="Filter by node id."),
    status: TripwireStatus | None = Query(None),
    tripped: bool | None = Query(None, description="Filter by current evaluation."),
    db: Session = Depends(get_db),
) -> list[TripwireOut]:
    stmt = select(Tripwire).order_by(Tripwire.review_date.nulls_last(), Tripwire.id)
    if node is not None:
        stmt = stmt.where(Tripwire.node_id == node)
    if status is not None:
        stmt = stmt.where(Tripwire.status == status)
    rows = [_to_out(db, tw) for tw in db.scalars(stmt)]
    if tripped is not None:
        rows = [r for r in rows if r.tripped == tripped]
    return rows


@router.get("/tripwires/{tripwire_id}", response_model=TripwireOut)
def get_tripwire(tripwire_id: int, db: Session = Depends(get_db)) -> TripwireOut:
    tw = db.get(Tripwire, tripwire_id)
    if tw is None:
        raise HTTPException(status_code=404, detail=f"tripwire {tripwire_id} not found")
    return _to_out(db, tw)
