"""Add model_batch_diagnostics table for live/backtest symbol filtering.

Revision ID: 0054_add_model_batch_diagnostics
Revises: 0053_add_model_serving_batch
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0054_add_model_batch_diagnostics"
down_revision = "0053_add_model_serving_batch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("model_batch_diagnostics"):
        return

    op.create_table(
        "model_batch_diagnostics",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("batch_started_at", sa.DateTime(), nullable=False,
                  comment="Dénormalisé de model_training_batch.started_at"),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("f1_macro_wf", sa.Float(), nullable=False),
        sa.Column("f1_long_wf", sa.Float(), nullable=True),
        sa.Column("f1_short_wf", sa.Float(), nullable=True),
        sa.Column("f1_flat_wf", sa.Float(), nullable=True),
        sa.Column("rank_type", sa.String(length=20), nullable=False,
                  comment="top|bottom|zero_short|weak_long|weak_short"),
        sa.Column("rank_position", sa.Integer(), nullable=True,
                  comment="1..N pour top/bottom, NULL pour zero_short/weak_*"),
        sa.Column("threshold_used", sa.Float(), nullable=True,
                  comment="Seuil utilisé pour weak_long / weak_short"),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        mysql_charset="utf8mb4",
        mysql_engine="InnoDB",
        comment="Diagnostics ML par batch pour filtrage live/backtest",
    )

    op.create_index("idx_batch_diag_batch_rank", "model_batch_diagnostics",
                    ["batch_id", "rank_type"])
    op.create_index("idx_batch_diag_symbol", "model_batch_diagnostics",
                    ["symbol"])
    op.create_index("idx_batch_diag_started", "model_batch_diagnostics",
                    ["batch_started_at"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("model_batch_diagnostics"):
        return

    indexes = {idx["name"] for idx in inspector.get_indexes("model_batch_diagnostics")}
    for idx_name in ("idx_batch_diag_batch_rank", "idx_batch_diag_symbol", "idx_batch_diag_started"):
        if idx_name in indexes:
            op.drop_index(idx_name, table_name="model_batch_diagnostics")

    op.drop_table("model_batch_diagnostics")
