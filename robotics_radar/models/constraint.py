"""Constraint-side schema: nodes, series, observations, raw payloads, tripwires.

Point-in-time correctness is the governing requirement here. Customs data
revises for months after first release, so observations are append-only by
vintage and nothing is ever overwritten in place.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from robotics_radar.models.base import Base, TimestampMixin, utcnow
from robotics_radar.models.enums import (
    Bucket,
    Cadence,
    EvidenceGrade,
    FlowDirection,
    TripwireDirection,
    TripwireMetric,
    TripwireStatus,
)


def _pg_enum(enum_cls, name: str) -> Enum:
    # values_callable keeps the *values* in Postgres (e.g. "import"), not the
    # Python member names (e.g. "import_").
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


class Node(Base, TimestampMixin):
    """A constraint in the buildout.

    severity and break_point_tier are deliberately left NULL. The scoring
    methodology is unsettled; seeding numbers here would poison every
    downstream read. They are nullable columns awaiting a defensible method,
    not fields that failed to populate.
    """

    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    bucket: Mapped[Bucket] = mapped_column(_pg_enum(Bucket, "bucket"), nullable=False)

    break_point_tier: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[float | None] = mapped_column(Numeric(6, 3), nullable=True)

    evidence_grade: Mapped[EvidenceGrade | None] = mapped_column(
        _pg_enum(EvidenceGrade, "evidence_grade"), nullable=True
    )
    methodology_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    series: Mapped[list[Series]] = relationship(back_populates="node")
    tripwires: Mapped[list[Tripwire]] = relationship(back_populates="node")


class Series(Base, TimestampMixin):
    """A single measurable time series attached to a node.

    `geography` is the reporting jurisdiction; `partner_geography` is the
    counterparty (country of origin for imports). The two are separate because
    the roller-screw read is explicitly a by-origin measurement -- US imports
    from Japan and US imports from China are different series sharing a
    reporter.
    """

    __tablename__ = "series"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(300), nullable=False)

    source: Mapped[str] = mapped_column(String(120), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cadence: Mapped[Cadence] = mapped_column(_pg_enum(Cadence, "cadence"), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(60), nullable=True)

    evidence_grade: Mapped[EvidenceGrade] = mapped_column(
        _pg_enum(EvidenceGrade, "evidence_grade"), nullable=False
    )
    geography: Mapped[str] = mapped_column(String(60), nullable=False)
    partner_geography: Mapped[str | None] = mapped_column(String(60), nullable=True)

    tariff_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    tariff_nomenclature: Mapped[str | None] = mapped_column(String(40), nullable=True)
    flow_direction: Mapped[FlowDirection] = mapped_column(
        _pg_enum(FlowDirection, "flow_direction"), nullable=False
    )

    methodology_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    known_limitations: Mapped[str | None] = mapped_column(Text, nullable=True)

    node: Mapped[Node] = relationship(back_populates="series")
    observations: Mapped[list[Observation]] = relationship(back_populates="series")

    __table_args__ = (
        UniqueConstraint(
            "source", "name", "geography", "partner_geography", name="uq_series_ident"
        ),
    )


class Observation(Base):
    """One (series, period, vintage) datapoint.

    Revisions append rather than overwrite: a restatement of the same period
    arrives as a new row with a later vintage_date. Readers that want "the
    number as it stands today" go through latest_observations; readers doing
    revision analysis query this table directly.

    release_date  - when the statistical agency published this vintage
    vintage_date  - the vintage the agency labels this figure with
    retrieved_at  - when we fetched it. Never conflate this with either.
    """

    __tablename__ = "observations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    series_id: Mapped[int] = mapped_column(
        ForeignKey("series.id", ondelete="CASCADE"), nullable=False
    )

    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)

    value: Mapped[float | None] = mapped_column(Numeric(24, 6), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(24, 6), nullable=True)
    quantity_unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unit_value: Mapped[float | None] = mapped_column(Numeric(24, 8), nullable=True)

    vintage_date: Mapped[date] = mapped_column(Date, nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    series: Mapped[Series] = relationship(back_populates="observations")

    __table_args__ = (
        UniqueConstraint(
            "series_id", "period_start", "vintage_date", name="uq_observations_vintage"
        ),
        Index("ix_observations_series_period", "series_id", "period_start"),
    )


class RawPayload(Base):
    """Every response we ever parsed, kept verbatim.

    Being able to prove where a number came from is the product. The payload is
    written *before* parsing, so a parser that crashes still leaves the
    evidence behind to debug against.
    """

    __tablename__ = "raw_payloads"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("ix_raw_payloads_source_fetched", "source", "fetched_at"),)


class Tripwire(Base, TimestampMixin):
    """A falsifiable prediction, logged before the fact.

    The point is to be gradeable later. A tripwire without an observable series
    and a threshold is an opinion, so both are required to move a tripwire off
    `open`.

    This is the mechanism for answering "when does robotics inflect": a dated
    statement, a named series, a metric, a threshold, and a run length -- all
    committed in advance, so the answer cannot be rationalised after the fact.
    """

    __tablename__ = "tripwires"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(
        ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    observable_series_id: Mapped[int | None] = mapped_column(
        ForeignKey("series.id", ondelete="SET NULL"), nullable=True
    )
    direction: Mapped[TripwireDirection | None] = mapped_column(
        _pg_enum(TripwireDirection, "tripwire_direction"), nullable=True
    )
    metric: Mapped[TripwireMetric] = mapped_column(
        _pg_enum(TripwireMetric, "tripwire_metric"),
        nullable=False,
        default=TripwireMetric.yoy_pct,
    )
    threshold: Mapped[float | None] = mapped_column(Numeric(24, 6), nullable=True)
    #: Consecutive qualifying periods required before the tripwire trips. One
    #: month clearing a threshold is noise; a run of them is a signal.
    consecutive_periods: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[TripwireStatus] = mapped_column(
        _pg_enum(TripwireStatus, "tripwire_status"),
        nullable=False,
        default=TripwireStatus.open,
    )

    node: Mapped[Node] = relationship(back_populates="tripwires")
