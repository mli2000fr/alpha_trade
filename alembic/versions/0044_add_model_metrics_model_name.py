"""Add model_name column to model_metrics for LightGBM/CatBoost persistence.

Revision ID: 0044_add_model_metrics_model_name
Revises: 0043_add_vxn_vix3m_move_rvx
"""
from __future__ import annotations

import alembic.op as op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0044_add_model_metrics_model_name"
down_revision = "0043_add_vxn_vix3m_move_rvx"
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


def _has_index(table_name: str, index_name: str) -> bool:
    bind = op.get_bind()
    inspector = inspect(bind)
    return any(idx.get("name") == index_name for idx in inspector.get_indexes(table_name))


def upgrade() -> None:
    if _has_table("model_metrics"):
        if not _has_column("model_metrics", "model_name"):
            op.add_column(
                "model_metrics",
                sa.Column(
                    "model_name",
                    sa.String(32),
                    nullable=False,
                    server_default=sa.text("'lstm_attention'"),
                    comment="lstm_attention|lightgbm|catboost|global_model",
                ),
            )
        if not _has_index("model_metrics", "idx_model_name"):
            op.create_index("idx_model_name", "model_metrics", ["model_name"])


def downgrade() -> None:
    if _has_table("model_metrics"):
        if _has_index("model_metrics", "idx_model_name"):
            op.drop_index("idx_model_name", table_name="model_metrics")
        if _has_column("model_metrics", "model_name"):
            op.drop_column("model_metrics", "model_name")
