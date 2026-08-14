"""Add symbols column to model_training_batch.

Revision ID: 0063_add_symbols_to_training_batch
Revises: 0062_add_horizon_to_model_metrics
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0063_add_symbols_to_training_batch"
down_revision = "0062_add_horizon_to_model_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "model_training_batch",
        sa.Column(
            "symbols",
            sa.String(5000),
            nullable=True,
            comment="Liste des symbols utilises par le batch (separes par virgule).",
        ),
    )


def downgrade() -> None:
    op.drop_column("model_training_batch", "symbols")
