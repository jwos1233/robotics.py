"""Give tripwires a metric and a run length

An inflection is a change in rate, not a level. A tripwire that can only
compare a level cannot express the question the board exists to answer, and a
single month clearing a threshold is noise rather than signal.

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-08-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

METRIC = sa.Enum("level", "yoy_pct", "mom_pct", name="tripwire_metric")


def upgrade() -> None:
    METRIC.create(op.get_bind(), checkfirst=True)
    op.add_column(
        "tripwires",
        sa.Column("metric", METRIC, nullable=False, server_default="yoy_pct"),
    )
    op.add_column(
        "tripwires",
        sa.Column("consecutive_periods", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("tripwires", "consecutive_periods")
    op.drop_column("tripwires", "metric")
    METRIC.drop(op.get_bind(), checkfirst=True)
