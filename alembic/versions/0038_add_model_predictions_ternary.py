"""Add model_predictions ternary columns for ML Sprint 3.

Revision ID: 0038_add_model_predictions_ternary
Revises: 0037_add_fractionable_and_fractional_target_shares
"""
from __future__ import annotations

import alembic.op as op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0038_add_model_predictions_ternary"
down_revision = "0037_add_fractionable_and_fractional_target_shares"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(column.get("name") == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    if not _has_table("model_predictions"):
        return

    if not _has_column("model_predictions", "predicted_side"):
        op.add_column(
            "model_predictions",
            sa.Column("predicted_side", sa.String(10), nullable=True, comment="ML Sprint 3 — long | flat | short"),
        )

    if not _has_column("model_predictions", "proba_long"):
        op.add_column(
            "model_predictions",
            sa.Column("proba_long", sa.Float(), nullable=True, comment="ML Sprint 3 — probabilité classe long"),
        )

    if not _has_column("model_predictions", "proba_flat"):
        op.add_column(
            "model_predictions",
            sa.Column("proba_flat", sa.Float(), nullable=True, comment="ML Sprint 3 — probabilité classe flat"),
        )

    if not _has_column("model_predictions", "proba_short"):
        op.add_column(
            "model_predictions",
            sa.Column("proba_short", sa.Float(), nullable=True, comment="ML Sprint 3 — probabilité classe short"),
        )

    # Index on predicted_side
    with op.batch_alter_table("model_predictions") as batch_op:
        try:
            batch_op.create_index("idx_predicted_side", ["predicted_side"])
        except Exception:
            pass  # index may already exist


def downgrade() -> None:
    if not _has_table("model_predictions"):
        return

    with op.batch_alter_table("model_predictions") as batch_op:
        try:
            batch_op.drop_index("idx_predicted_side")
        except Exception:
            pass

    if _has_column("model_predictions", "predicted_side"):
        op.drop_column("model_predictions", "predicted_side")

    if _has_column("model_predictions", "proba_long"):
        op.drop_column("model_predictions", "proba_long")

    if _has_column("model_predictions", "proba_flat"):
        op.drop_column("model_predictions", "proba_flat")

    if _has_column("model_predictions", "proba_short"):
        op.drop_column("model_predictions", "proba_short")
