"""Enumerations shared across the schema.

These are stored as native Postgres enums so that a bad value fails at write
time rather than silently entering the store.
"""

from __future__ import annotations

from enum import StrEnum


class Bucket(StrEnum):
    """Top-level grouping of constraint nodes."""

    actuation = "actuation"
    precision_mfg = "precision_mfg"
    materials = "materials"
    sensing = "sensing"
    compute_power = "compute_power"
    energy = "energy"
    assembly = "assembly"


class EvidenceGrade(StrEnum):
    """How directly a number was observed.

    measured  - read off a primary statistical release
    disclosed - reported by the company or body itself
    inferred  - derived from an adjacent series by a documented rule
    estimated - modelled; the weakest grade
    """

    measured = "measured"
    disclosed = "disclosed"
    inferred = "inferred"
    estimated = "estimated"


class FlowDirection(StrEnum):
    import_ = "import"
    export = "export"
    production = "production"
    orders = "orders"


class Cadence(StrEnum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"


class TripwireStatus(StrEnum):
    open = "open"
    confirmed = "confirmed"
    falsified = "falsified"


class TripwireDirection(StrEnum):
    above = "above"
    below = "below"


class PurityGrade(StrEnum):
    """How much of a basket's return is actually the named constraint.

    pure      - constituents derive material revenue from the constraint
    mixed     - real exposure, diluted by unrelated revenue
    narrative - exposure is thematic; the move is sentiment, not constraint
    """

    pure = "pure"
    mixed = "mixed"
    narrative = "narrative"


class CoverageStatus(StrEnum):
    ok = "ok"
    partial = "partial"
    unavailable = "unavailable"


class ReturnWindow(StrEnum):
    d1 = "1d"
    d7 = "7d"
    d30 = "30d"
    ytd = "ytd"
