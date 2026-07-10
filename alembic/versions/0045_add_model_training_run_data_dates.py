"""Add train_start_date and train_end_date to model_training_run
for look-ahead-free calibration filtering.

Revision ID: 0045_add_model_training_run_data_dates
Revises: 0044_add_model_metrics_model_name
"""
from __future__ import annotations

import alembic.op as op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0045_add_model_training_run_data_dates"
down_revision = "0044_add_model_metrics_model_name"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(col.get("name") == column_name for col in inspector.get_columns(table_name))


def upgrade() -> None:
    if _has_table("model_training_run"):
        if not _has_column("model_training_run", "train_start_date"):
            op.add_column(
                "model_training_run",
                sa.Column("train_start_date", sa.Date(), nullable=True),
            )
        if not _has_column("model_training_run", "train_end_date"):
            op.add_column(
                "model_training_run",
                sa.Column("train_end_date", sa.Date(), nullable=True),
            )


def downgrade() -> None:
    if _has_table("model_training_run"):
        if _has_column("model_training_run", "train_start_date"):
            op.drop_column("model_training_run", "train_start_date")
        if _has_column("model_training_run", "train_end_date"):
            op.drop_column("model_training_run", "train_end_date")
