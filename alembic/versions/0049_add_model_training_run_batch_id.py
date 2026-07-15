"""Add a shared batch identifier to ML training runs.

Revision ID: 0049_add_model_training_run_batch_id
Revises: 0048_add_model_directional_oos_metrics, 0048_drop_candidate_columns_from_score_snapshots
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0049_add_model_training_run_batch_id"
down_revision = (
    "0048_add_model_directional_oos_metrics",
    "0048_drop_candidate_columns_from_score_snapshots",
)
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_training_run"):
        return

    columns = {column["name"] for column in inspector.get_columns("model_training_run")}
    if "batch_id" not in columns:
        op.add_column(
            "model_training_run",
            sa.Column(
                "batch_id",
                sa.String(length=64),
                nullable=True,
                comment="Identifiant partage de la campagne d entrainement",
            ),
        )

    indexes = {index["name"] for index in inspector.get_indexes("model_training_run")}
    if "idx_batch_status" not in indexes:
        op.create_index("idx_batch_status", "model_training_run", ["batch_id", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_training_run"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("model_training_run")}
    if "idx_batch_status" in indexes:
        op.drop_index("idx_batch_status", table_name="model_training_run")

    columns = {column["name"] for column in inspector.get_columns("model_training_run")}
    if "batch_id" in columns:
        op.drop_column("model_training_run", "batch_id")