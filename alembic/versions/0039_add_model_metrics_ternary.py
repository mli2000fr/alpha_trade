"""Add ternary metrics columns for ML Sprint 7.

Revision ID: 0039_add_model_metrics_ternary
Revises: 0038_add_model_predictions_ternary
"""
from __future__ import annotations

import alembic.op as op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0039_add_model_metrics_ternary"
down_revision = "0038_add_model_predictions_ternary"
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
    # model_governance
    if _has_table("model_governance"):
        if not _has_column("model_governance", "num_classes"):
            op.add_column("model_governance", sa.Column("num_classes", sa.SmallInteger(), nullable=True, server_default=sa.text("2"), comment="ML Sprint 7 — 2=binaire, 3=ternaire"))
        if not _has_column("model_governance", "val_f1_macro"):
            op.add_column("model_governance", sa.Column("val_f1_macro", sa.Float(), nullable=True, comment="ML Sprint 7 — F1 macro ternaire"))
        if not _has_column("model_governance", "test_f1_macro"):
            op.add_column("model_governance", sa.Column("test_f1_macro", sa.Float(), nullable=True, comment="ML Sprint 7 — F1 macro ternaire"))

    # model_metrics
    if _has_table("model_metrics"):
        if not _has_column("model_metrics", "f1_macro"):
            op.add_column("model_metrics", sa.Column("f1_macro", sa.Float(), nullable=True, comment="ML Sprint 7 — F1 macro ternaire"))
        if not _has_column("model_metrics", "f1_short"):
            op.add_column("model_metrics", sa.Column("f1_short", sa.Float(), nullable=True, comment="ML Sprint 7 — F1 classe short"))
        if not _has_column("model_metrics", "f1_flat"):
            op.add_column("model_metrics", sa.Column("f1_flat", sa.Float(), nullable=True, comment="ML Sprint 7 — F1 classe flat"))
        if not _has_column("model_metrics", "f1_long"):
            op.add_column("model_metrics", sa.Column("f1_long", sa.Float(), nullable=True, comment="ML Sprint 7 — F1 classe long"))


def downgrade() -> None:
    if _has_table("model_governance"):
        for col in ("test_f1_macro", "val_f1_macro", "num_classes"):
            if _has_column("model_governance", col):
                op.drop_column("model_governance", col)

    if _has_table("model_metrics"):
        for col in ("f1_long", "f1_flat", "f1_short", "f1_macro"):
            if _has_column("model_metrics", col):
                op.drop_column("model_metrics", col)
