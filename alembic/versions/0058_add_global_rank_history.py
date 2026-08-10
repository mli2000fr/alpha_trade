"""Add global_rank_history table for cascade ML architecture.

Revision ID: 0058
Revises: 0057
Create Date: 2026-07-27

Stores global ranking predictions generated during "10. ML Predict" —
one row per (symbol, date, batch_id).  The cascade backtest/live reads
this table as the single source of truth for cross-sectional ranks.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0058"
down_revision: Union[str, None] = "0057"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("global_rank_history", schema="alpha_trade"):
        return

    op.create_table(
        "global_rank_history",
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("global_rank_3", sa.Double(), nullable=True,
                  comment="Rang cross-sectional H3 [0,1] — 1=meilleur"),
        sa.Column("global_rank_5", sa.Double(), nullable=True,
                  comment="Rang cross-sectional H5 [0,1]"),
        sa.Column("global_rank_10", sa.Double(), nullable=True,
                  comment="Rang cross-sectional H10 [0,1]"),
        sa.Column("global_rank_15", sa.Double(), nullable=True,
                  comment="Rang cross-sectional H15 [0,1]"),
        sa.Column("global_rank_20", sa.Double(), nullable=True,
                  comment="Rang cross-sectional H20 [0,1]"),
        sa.Column("batch_id", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("symbol", "date", "batch_id"),
        sa.Index("idx_grh_date", "date"),
        sa.Index("idx_grh_batch_date", "batch_id", "date"),
        schema="alpha_trade",
    )


def downgrade() -> None:
    op.drop_table("global_rank_history", schema="alpha_trade")
