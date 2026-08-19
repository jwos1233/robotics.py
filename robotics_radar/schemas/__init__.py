"""Pydantic response models.

The governing rule on this side is that the caveats travel with the number.
Every series response carries methodology_note and known_limitations; every
basket response carries purity_grade, breadth and the priced/total ratio.
None of those are optional extras a caller can forget to ask for.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from robotics_radar.models.enums import (
    Bucket,
    Cadence,
    CoverageStatus,
    EvidenceGrade,
    FlowDirection,
    PurityGrade,
    ReturnWindow,
    TripwireDirection,
    TripwireMetric,
    TripwireStatus,
)


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    bucket: Bucket
    break_point_tier: int | None = Field(
        None,
        description=(
            "Always null. Scoring methodology is unsettled; no tier is seeded "
            "rather than seeding a fabricated one."
        ),
    )
    severity: float | None = Field(
        None, description="Always null, for the same reason as break_point_tier."
    )
    evidence_grade: EvidenceGrade | None = None
    methodology_note: str | None = None


class SeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    node_id: int
    name: str
    source: str
    source_url: str | None = None
    cadence: Cadence
    unit: str | None = None
    evidence_grade: EvidenceGrade
    geography: str
    partner_geography: str | None = None
    tariff_code: str | None = None
    tariff_nomenclature: str | None = None
    flow_direction: FlowDirection
    methodology_note: str | None = None
    known_limitations: str | None = None


class ObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_start: date
    period_end: date
    value: float | None = None
    quantity: float | None = None
    quantity_unit: str | None = None
    unit_value: float | None = None
    vintage_date: date
    release_date: date | None = None
    retrieved_at: datetime


class ObservationsResponse(BaseModel):
    series: SeriesOut
    vintage: str = Field(description="'latest' or the explicit vintage date requested.")
    observations: list[ObservationOut]


class SecurityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_ticker: str = Field(description="Bloomberg style, e.g. '6324 JP'. For display only.")
    exchange_mic: str | None = None
    local_code: str
    isin: str | None = None
    name: str
    currency: str
    country: str
    coverage_status: CoverageStatus


class BasketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    node_id: int | None = None
    node_name: str | None = Field(
        None,
        description=(
            "Linked constraint node, by name only. No constraint score is "
            "attached to a basket."
        ),
    )
    bucket: Bucket | None = None
    constraint_label: str
    purity_grade: PurityGrade
    is_demand_side: bool
    is_shared_node: bool
    thesis_note: str | None = None
    caveat_note: str | None = None
    constituents_total: int
    constituents_priceable: int = Field(
        description="Members with a confirmed price source (coverage_status='ok')."
    )
    interpretation: str = Field(
        description="How this basket's moves should and should not be read."
    )


class BasketDetailOut(BasketOut):
    members: list[SecurityOut]


class BasketReturnOut(BaseModel):
    basket_id: int
    basket_name: str
    purity_grade: PurityGrade
    is_demand_side: bool
    window: ReturnWindow
    as_of: date | None = None
    return_raw: float | None = None
    return_vs_benchmark: float | None = None
    benchmark_symbol: str
    breadth: float | None = None
    breadth_flag: bool = Field(
        description="True when breadth is below 0.5: the move is one or two names."
    )
    constituents_priced: int
    constituents_total: int
    coverage_ratio: float | None = None
    interpretation: str
    caveat_note: str | None = None


class MetricPointOut(BaseModel):
    period: date
    value: float


class MetricsResponse(BaseModel):
    """Derived series for one instrument.

    Every layer is computed from the observations, never configured, so two
    callers cannot disagree about what a growth rate is.
    """

    series: SeriesOut
    smoothing_window: int
    level: list[MetricPointOut]
    yoy_pct: list[MetricPointOut]
    mom_pct: list[MetricPointOut]
    acceleration: list[MetricPointOut] = Field(
        description="Change in year-on-year growth, in percentage points. The inflection term."
    )
    yoy_z_score: list[MetricPointOut] = Field(
        description="How unusual the growth rate is against this series' own prior history."
    )
    note: str


class TripwireOut(BaseModel):
    """A falsifiable prediction, with its current verdict.

    `status` is the recorded human judgement; `tripped` is the mechanical
    evaluation against today's data. They are separate on purpose -- a
    tripwire can be tripping without anyone yet having confirmed it, and
    conflating the two would let the record be rewritten by the data.
    """

    id: int
    node_id: int
    node_name: str | None = None
    statement: str
    series_id: int | None = None
    series_name: str | None = None
    metric: TripwireMetric
    direction: TripwireDirection | None = None
    threshold: float | None = None
    consecutive_periods: int
    review_date: date | None = None
    status: TripwireStatus
    tripped: bool
    observed_run: int = Field(description="Consecutive qualifying periods observed.")
    latest_period: date | None = None
    latest_value: float | None = None
    distance_to_threshold: float | None = Field(
        None, description="Signed toward the tripwire's direction; negative means short of it."
    )
    evaluable: bool = Field(
        description="False when the tripwire lacks a series or threshold, i.e. is an opinion."
    )
    reason: str


class OverlapPair(BaseModel):
    basket_a_id: int
    basket_a: str
    basket_b_id: int
    basket_b: str
    shared: list[str]
    shared_count: int
    jaccard: float


class OverlapResponse(BaseModel):
    note: str
    baskets: int
    pairs: list[OverlapPair]


class HealthOut(BaseModel):
    status: str
    database: str
    app_env: str
