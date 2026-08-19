"""Equity-side schema: securities, baskets, membership, prices, basket returns.

The honesty problem on this side is that almost no listed name derives more
than low single-digit revenue from humanoids. purity_grade is therefore a
required field on every basket, and it travels with every number the API
returns.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from robotics_radar.models.base import Base, TimestampMixin, utcnow
from robotics_radar.models.constraint import _pg_enum
from robotics_radar.models.enums import Bucket, CoverageStatus, PurityGrade, ReturnWindow


class Security(Base, TimestampMixin):
    """A listed company.

    display_ticker is Bloomberg style ("6324 JP") and is what the UI shows.
    source_symbol is whatever string the price API actually accepts, which is
    a different namespace entirely. These are never conflated: writing a
    Bloomberg ticker into an API call is how you silently price the wrong
    instrument.

    source_symbol and data_source are nullable because Phase 0 price-source
    verification has not run. A security with no confirmed source carries
    coverage_status='unavailable' and is excluded from basket pricing rather
    than guessed at.
    """

    __tablename__ = "securities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    display_ticker: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    exchange_mic: Mapped[str | None] = mapped_column(String(10), nullable=True)
    local_code: Mapped[str] = mapped_column(String(30), nullable=False)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False)

    data_source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_symbol: Mapped[str | None] = mapped_column(String(60), nullable=True)
    coverage_status: Mapped[CoverageStatus] = mapped_column(
        _pg_enum(CoverageStatus, "coverage_status"),
        nullable=False,
        default=CoverageStatus.unavailable,
    )

    memberships: Mapped[list[BasketMember]] = relationship(back_populates="security")


class Basket(Base, TimestampMixin):
    """A set of listed names mapped to one constraint.

    bucket is nullable: demand-side baskets are not constraints and do not sit
    in a constraint bucket. is_demand_side distinguishes them.
    """

    __tablename__ = "baskets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    node_id: Mapped[int | None] = mapped_column(
        ForeignKey("nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bucket: Mapped[Bucket | None] = mapped_column(_pg_enum(Bucket, "bucket"), nullable=True)
    constraint_label: Mapped[str] = mapped_column(String(200), nullable=False)
    purity_grade: Mapped[PurityGrade] = mapped_column(
        _pg_enum(PurityGrade, "purity_grade"), nullable=False
    )
    is_demand_side: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_shared_node: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    thesis_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    caveat_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    members: Mapped[list[BasketMember]] = relationship(back_populates="basket")


class BasketMember(Base):
    """Membership, with history.

    removed_at is NULL for a live member. A security belonging to several
    baskets is expected and correct -- see the overlap view.
    """

    __tablename__ = "basket_members"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basket_id: Mapped[int] = mapped_column(
        ForeignKey("baskets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    added_at: Mapped[date] = mapped_column(Date, nullable=False)
    removed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    basket: Mapped[Basket] = relationship(back_populates="members")
    security: Mapped[Security] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("basket_id", "security_id", "added_at", name="uq_basket_member_spell"),
    )


class Price(Base):
    """Daily close, local and USD.

    fx_rate is stored alongside so a USD close can always be decomposed back
    into its local close and the rate used. Without that, a basket move cannot
    be separated into an equity move and a currency move.
    """

    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    security_id: Mapped[int] = mapped_column(
        ForeignKey("securities.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    close_local: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    close_usd: Mapped[float | None] = mapped_column(Numeric(20, 6), nullable=True)
    fx_rate: Mapped[float | None] = mapped_column(Numeric(20, 10), nullable=True)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("security_id", "date", name="uq_prices_security_date"),
        Index("ix_prices_date", "date"),
    )


class FxRate(Base):
    """Daily currency -> USD rate.

    Kept separate from prices so one FX fetch serves every security in that
    currency, and so a missing rate is diagnosable as an FX gap rather than
    looking like a missing price.
    """

    __tablename__ = "fx_rates"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    rate_to_usd: Mapped[float] = mapped_column(Numeric(20, 10), nullable=False)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("currency", "date", name="uq_fx_currency_date"),)


class BenchmarkPrice(Base):
    """Benchmark close. ACWI, not SPY.

    A ~70% non-US board measured against a USD-only benchmark is a currency
    bet wearing a constraint costume, so the benchmark identity is a stored
    field rather than a constant.
    """

    __tablename__ = "benchmark_prices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    close_usd: Mapped[float] = mapped_column(Numeric(20, 6), nullable=False)
    source: Mapped[str] = mapped_column(String(60), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (UniqueConstraint("symbol", "date", name="uq_benchmark_symbol_date"),)


class BasketReturn(Base):
    """Computed basket performance over a window.

    constituents_priced vs constituents_total is not diagnostics -- it is part
    of the number's meaning. A basket computed on 4 of 8 names is a different
    number and every caller must be able to see that.
    """

    __tablename__ = "basket_returns"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    basket_id: Mapped[int] = mapped_column(
        ForeignKey("baskets.id", ondelete="CASCADE"), nullable=False
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    window: Mapped[ReturnWindow] = mapped_column(
        _pg_enum(ReturnWindow, "return_window"), nullable=False
    )
    return_raw: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    return_vs_benchmark: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    breadth: Mapped[float | None] = mapped_column(Numeric(6, 4), nullable=True)
    constituents_priced: Mapped[int] = mapped_column(Integer, nullable=False)
    constituents_total: Mapped[int] = mapped_column(Integer, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint("basket_id", "date", "window", name="uq_basket_returns_key"),
        Index("ix_basket_returns_basket_date", "basket_id", "date"),
    )
