"""Evaluate tripwires against observed data.

A tripwire is a falsifiable prediction committed before the fact: a named
series, a metric, a threshold, a direction, and how many consecutive periods
must qualify. Evaluation is deliberately mechanical -- given the same data it
always returns the same verdict, so a prediction cannot be rationalised after
the outcome is known.

Two design choices worth stating:

* **Rate, not level, by default.** An inflection is a change in growth rate.
  A tripwire that could only compare levels would answer "is this big" rather
  than "is this turning", which is the wrong question.
* **A run length, not a single crossing.** One month clearing a threshold is
  noise in a monthly series. `consecutive_periods` makes the required
  persistence explicit rather than leaving it to whoever reads the chart.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from robotics_radar.models.constraint import Observation, Tripwire
from robotics_radar.models.enums import TripwireDirection, TripwireMetric, TripwireStatus


@dataclass(frozen=True)
class MetricPoint:
    period: date
    value: float


@dataclass
class TripwireEvaluation:
    """The verdict, with everything needed to check the working."""

    tripwire_id: int
    statement: str
    status: TripwireStatus
    metric: TripwireMetric
    direction: TripwireDirection | None
    threshold: float | None
    consecutive_periods: int
    #: True when the observed run meets or exceeds the required run length.
    tripped: bool
    #: How many consecutive qualifying periods were actually observed.
    observed_run: int
    latest_period: date | None
    latest_value: float | None
    #: Distance from the threshold, signed toward the tripwire's direction.
    distance_to_threshold: float | None
    evaluable: bool
    reason: str


def _latest_by_period(session: Session, series_id: int) -> list[Observation]:
    """Latest vintage of each period, oldest first."""
    stmt = (
        select(Observation)
        .where(Observation.series_id == series_id)
        .order_by(Observation.period_start, Observation.vintage_date.desc())
        .distinct(Observation.period_start)
    )
    return list(session.scalars(stmt))


def metric_series(
    observations: Sequence[Observation], metric: TripwireMetric
) -> list[MetricPoint]:
    """Project observations onto the tripwire's metric.

    Growth metrics compare against a specific earlier period rather than a
    positional offset, so a gap in the series produces a missing comparison
    instead of a silently wrong one.
    """
    points = [
        (o.period_start, float(o.value))
        for o in observations
        if o.value is not None
    ]
    if metric is TripwireMetric.level:
        return [MetricPoint(p, v) for p, v in points]

    lookup = dict(points)
    lag = 12 if metric is TripwireMetric.yoy_pct else 1
    out: list[MetricPoint] = []
    for period, value in points:
        if lag == 12:
            prior_key = date(period.year - 1, period.month, period.day)
        else:
            prior_key = (
                date(period.year - 1, 12, period.day)
                if period.month == 1
                else date(period.year, period.month - 1, period.day)
            )
        prior = lookup.get(prior_key)
        if prior in (None, 0):
            continue
        out.append(MetricPoint(period, (value - prior) / abs(prior) * 100.0))
    return out


def _qualifies(value: float, direction: TripwireDirection, threshold: float) -> bool:
    if direction is TripwireDirection.above:
        return value > threshold
    return value < threshold


def evaluate_tripwire(session: Session, tripwire: Tripwire) -> TripwireEvaluation:
    """Grade one tripwire against the current data."""

    def unevaluable(reason: str) -> TripwireEvaluation:
        return TripwireEvaluation(
            tripwire_id=tripwire.id,
            statement=tripwire.statement,
            status=tripwire.status,
            metric=tripwire.metric,
            direction=tripwire.direction,
            threshold=float(tripwire.threshold) if tripwire.threshold is not None else None,
            consecutive_periods=tripwire.consecutive_periods,
            tripped=False,
            observed_run=0,
            latest_period=None,
            latest_value=None,
            distance_to_threshold=None,
            evaluable=False,
            reason=reason,
        )

    # A prediction with no series or no threshold is an opinion. Say so rather
    # than returning a confident-looking false.
    if tripwire.observable_series_id is None:
        return unevaluable("no observable series attached")
    if tripwire.threshold is None or tripwire.direction is None:
        return unevaluable("no threshold or direction set")

    observations = _latest_by_period(session, tripwire.observable_series_id)
    points = metric_series(observations, tripwire.metric)
    if not points:
        return unevaluable(
            f"no {tripwire.metric.value} values computable from "
            f"{len(observations)} observation(s)"
        )

    threshold = float(tripwire.threshold)
    run = 0
    for point in reversed(points):
        if _qualifies(point.value, tripwire.direction, threshold):
            run += 1
        else:
            break

    latest = points[-1]
    signed = (
        latest.value - threshold
        if tripwire.direction is TripwireDirection.above
        else threshold - latest.value
    )
    tripped = run >= tripwire.consecutive_periods
    return TripwireEvaluation(
        tripwire_id=tripwire.id,
        statement=tripwire.statement,
        status=tripwire.status,
        metric=tripwire.metric,
        direction=tripwire.direction,
        threshold=threshold,
        consecutive_periods=tripwire.consecutive_periods,
        tripped=tripped,
        observed_run=run,
        latest_period=latest.period,
        latest_value=latest.value,
        distance_to_threshold=signed,
        evaluable=True,
        reason=(
            f"{run} of {tripwire.consecutive_periods} consecutive periods qualifying"
            if not tripped
            else f"tripped on a run of {run}"
        ),
    )
