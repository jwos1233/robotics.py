"""Add 'revenue' to the flow_direction enum

Disclosed company revenue is not production: it is a financial figure over
whatever the company sells, so it needs its own value rather than being
filed under an output measure.

Revision ID: b1c2d3e4f5a6
Revises: 2d6bee1ebe86
Create Date: 2026-08-19
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "2d6bee1ebe86"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TYPE flow_direction ADD VALUE IF NOT EXISTS 'revenue'")


def downgrade() -> None:
    # Postgres cannot drop a value from an enum. Removing it would mean
    # rebuilding the type and rewriting every dependent column, which is not
    # worth doing to undo an additive change.
    pass
