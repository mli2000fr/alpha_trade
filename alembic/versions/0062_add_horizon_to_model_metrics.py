"""Add horizon column to model_metrics for multi-horizon training.

Revision ID: 0062_add_horizon_to_model_metrics
Revises: 0061_widen_symbol_columns_for_sector_names
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0062_add_horizon_to_model_metrics"
down_revision = "0061_widen_symbol_columns_for_sector_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_metrics",
        sa.Column(
            "horizon",
            sa.Integer(),
            nullable=True,
            comment="Horizon de prédiction en jours (NULL = single-horizon ou legacy).",
        ),
    )
    # Also add to model_metrics_full (blob table)
    op.add_column(
        "model_metrics_full",
        sa.Column(
            "horizon",
            sa.Integer(),
            nullable=True,
            comment="Horizon de prédiction en jours.",
        ),
    )


def downgrade() -> None:
    op.drop_column("model_metrics_full", "horizon")
    op.drop_column("model_metrics", "horizon")
