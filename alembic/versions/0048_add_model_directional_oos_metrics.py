"""Add point-in-time directional OOS metrics for Kelly sizing.

Revision ID: 0048_add_model_directional_oos_metrics
Revises: 0047_add_selection_rank_to_risk_execution
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0048_add_model_directional_oos_metrics"
down_revision = "0047_add_selection_rank_to_risk_execution"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("model_directional_oos_metrics"):
        return
    op.create_table(
        "model_directional_oos_metrics",
        sa.Column("run_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("side", sa.String(length=8), nullable=False),
        sa.Column("split_name", sa.String(length=16), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("hit_rate", sa.Float(), nullable=False),
        sa.Column("payoff", sa.Float(), nullable=False),
        sa.Column("tail_loss", sa.Float(), nullable=True),
        sa.Column("trade_count", sa.Integer(), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["run_id"], ["model_training_run.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "symbol", "side", "split_name"),
        sa.CheckConstraint("side IN ('long', 'short')", name="ck_directional_oos_side"),
        sa.CheckConstraint("hit_rate >= 0 AND hit_rate <= 1", name="ck_directional_oos_hit_rate"),
        sa.CheckConstraint("payoff > 0", name="ck_directional_oos_payoff"),
        sa.CheckConstraint("trade_count > 0", name="ck_directional_oos_trade_count"),
    )
    op.create_index(
        "idx_directional_oos_metrics_pit",
        "model_directional_oos_metrics",
        ["symbol", "side", "as_of_date", "split_name"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("model_directional_oos_metrics"):
        op.drop_table("model_directional_oos_metrics")
