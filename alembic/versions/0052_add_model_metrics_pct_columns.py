"""Add true/pred percentage columns to model_metrics.

Revision ID: 0052_add_model_metrics_pct_columns
Revises: 0051_add_comment_to_model_training_batch
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0052_add_model_metrics_pct_columns"
down_revision = "0051_add_comment_to_model_training_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_metrics"):
        return

    columns = {col["name"] for col in inspector.get_columns("model_metrics")}

    new_columns = [
        ("true_short_pct", "Pourcentage reel de la classe short"),
        ("true_flat_pct", "Pourcentage reel de la classe flat"),
        ("true_long_pct", "Pourcentage reel de la classe long"),
        ("pred_short_pct", "Pourcentage predit de la classe short"),
        ("pred_flat_pct", "Pourcentage predit de la classe flat"),
        ("pred_long_pct", "Pourcentage predit de la classe long"),
    ]

    for col_name, col_comment in new_columns:
        if col_name not in columns:
            op.add_column(
                "model_metrics",
                sa.Column(col_name, sa.Float(), nullable=True, comment=col_comment),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_metrics"):
        return

    columns = {col["name"] for col in inspector.get_columns("model_metrics")}

    cols_to_drop = [
        "true_short_pct", "true_flat_pct", "true_long_pct",
        "pred_short_pct", "pred_flat_pct", "pred_long_pct",
    ]

    for col_name in cols_to_drop:
        if col_name in columns:
            op.drop_column("model_metrics", col_name)
