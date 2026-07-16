"""Add explicitly promoted ML serving batch.

Revision ID: 0053_add_model_serving_batch
Revises: 0052_add_model_metrics_pct_columns
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0053_add_model_serving_batch"
down_revision = "0052_add_model_metrics_pct_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("model_serving_batch"):
        return
    op.create_table(
        "model_serving_batch",
        sa.Column("scope", sa.String(length=32), primary_key=True, nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("promoted_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
        comment="Campagne ML promue comme source de serving",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("model_serving_batch"):
        op.drop_table("model_serving_batch")