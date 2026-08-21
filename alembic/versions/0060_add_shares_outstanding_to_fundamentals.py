"""Add shares_outstanding, current_ratio, revenue to stock_fundamentals_daily.

Revision ID: 0060_add_shares_outstanding_to_fundamentals
Revises: 0059_add_stacking_enabled_to_training_batch
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0060_add_shares_outstanding_to_fundamentals"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stock_fundamentals_daily",
        sa.Column(
            "shares_outstanding",
            sa.BigInteger(),
            nullable=True,
            comment="Weighted average shares outstanding (from SEC 10-K/Q filings)",
        ),
    )
    op.add_column(
        "stock_fundamentals_daily",
        sa.Column(
            "current_ratio",
            sa.Float(),
            nullable=True,
            comment="Current ratio = Current Assets / Current Liabilities",
        ),
    )
    op.add_column(
        "stock_fundamentals_daily",
        sa.Column(
            "revenue",
            sa.Float(),
            nullable=True,
            comment="Quarterly revenue (from SEC filings, for PS ratio)",
        ),
    )


def downgrade() -> None:
    op.drop_column("stock_fundamentals_daily", "revenue")
    op.drop_column("stock_fundamentals_daily", "current_ratio")
    op.drop_column("stock_fundamentals_daily", "shares_outstanding")
