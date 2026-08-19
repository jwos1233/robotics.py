from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from robotics_radar.db import get_db
from robotics_radar.models.constraint import Observation, Series
from robotics_radar.models.enums import FlowDirection
from robotics_radar.schemas import ObservationOut, ObservationsResponse, SeriesOut

router = APIRouter(tags=["constraints"])


@router.get("/series", response_model=list[SeriesOut])
def list_series(
    node: int | None = Query(None, description="Filter by node id."),
    geography: str | None = Query(None),
    flow: FlowDirection | None = Query(None),
    db: Session = Depends(get_db),
) -> list[Series]:
    stmt = select(Series).order_by(Series.node_id, Series.name)
    if node is not None:
        stmt = stmt.where(Series.node_id == node)
    if geography is not None:
        stmt = stmt.where(Series.geography == geography)
    if flow is not None:
        stmt = stmt.where(Series.flow_direction == flow)
    return list(db.scalars(stmt))


@router.get("/series/{series_id}/observations", response_model=ObservationsResponse)
def get_observations(
    series_id: int,
    from_: date | None = Query(None, alias="from"),
    to: date | None = Query(None),
    vintage: date | None = Query(
        None,
        description=(
            "Explicit vintage date. Omit for the latest vintage of each period, "
            "which is the default."
        ),
    ),
    db: Session = Depends(get_db),
) -> ObservationsResponse:
    series = db.get(Series, series_id)
    if series is None:
        raise HTTPException(status_code=404, detail=f"series {series_id} not found")

    stmt = select(Observation).where(Observation.series_id == series_id)
    if from_ is not None:
        stmt = stmt.where(Observation.period_start >= from_)
    if to is not None:
        stmt = stmt.where(Observation.period_start <= to)

    if vintage is not None:
        # As the data stood on that vintage: the newest vintage at or before it.
        stmt = stmt.where(Observation.vintage_date <= vintage)

    # One row per period, taking the newest qualifying vintage. Revisions are
    # never overwritten, so this picks rather than mutates.
    stmt = stmt.order_by(
        Observation.period_start, Observation.vintage_date.desc()
    ).distinct(Observation.period_start)

    rows = list(db.scalars(stmt))
    return ObservationsResponse(
        series=SeriesOut.model_validate(series),
        vintage="latest" if vintage is None else vintage.isoformat(),
        observations=[ObservationOut.model_validate(r) for r in rows],
    )
