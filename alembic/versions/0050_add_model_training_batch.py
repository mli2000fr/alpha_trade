"""Add ML training batch metadata.

Revision ID: 0050_add_model_training_batch
Revises: 0049_add_model_training_run_batch_id
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0050_add_model_training_batch"
down_revision = "0049_add_model_training_run_batch_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("model_training_batch"):
        return

    op.create_table(
        "model_training_batch",
        sa.Column("batch_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("command_line", sa.Text(), nullable=False),
        sa.Column("command_argv_json", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("symbol_source", sa.String(length=32), nullable=False),
        sa.Column("universe_date", sa.Date(), nullable=True),
        sa.Column("requested_symbol_count", sa.Integer(), nullable=True),
        sa.Column("training_start_date", sa.Date(), nullable=True),
        sa.Column("training_end_date", sa.Date(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("symbols_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("symbols_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("symbols_failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
        comment="Metadonnees par campagne d entrainement ML",
    )
    op.create_index("idx_model_training_batch_status_started", "model_training_batch", ["status", "started_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_training_batch"):
        return

    indexes = {index["name"] for index in inspector.get_indexes("model_training_batch")}
    if "idx_model_training_batch_status_started" in indexes:
        op.drop_index("idx_model_training_batch_status_started", table_name="model_training_batch")
    op.drop_table("model_training_batch")