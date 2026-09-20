"""Add segmented multi-market sessions.

Revision ID: 0086_market_calendar_pit
Revises: 0085_market_scope_parents
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0086_market_calendar_pit"
down_revision: str | None = "0085_market_scope_parents"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("market_sessions", sa.Column("session_segments_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("market_sessions", "session_segments_json")
