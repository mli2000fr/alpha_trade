"""Add point-in-time tradable universe runs and history.

Revision ID: 0046_add_tradable_universe_history
Revises: 0045_add_model_training_run_data_dates
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0046_add_tradable_universe_history"
down_revision = "0045_add_model_training_run_data_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("tradable_universe_runs"):
        op.create_table(
            "tradable_universe_runs",
            sa.Column("universe_run_id", sa.String(length=64), primary_key=True),
            sa.Column("snapshot_date", sa.Date(), nullable=False),
            sa.Column("capital_preset_key", sa.String(length=64), nullable=False),
            sa.Column("config_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False),
            sa.Column("is_canonical", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("rows_expected", sa.Integer(), nullable=False),
            sa.Column("rows_written", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tradable_rows", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("data_quality_grade", sa.String(length=16), nullable=False, server_default="unknown"),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "idx_universe_runs_asof",
            "tradable_universe_runs",
            ["capital_preset_key", "snapshot_date", "status", "is_canonical"],
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("tradable_universe_history"):
        op.create_table(
            "tradable_universe_history",
            sa.Column("universe_run_id", sa.String(length=64), nullable=False),
            sa.Column("symbol", sa.String(length=32), nullable=False),
            sa.Column("is_tradable", sa.Boolean(), nullable=False),
            sa.Column("tradability_reason_code", sa.String(length=64), nullable=False),
            sa.Column("tradability_reasons_json", sa.JSON(), nullable=True),
            sa.Column("history_days", sa.Integer(), nullable=True),
            sa.Column("bars_available", sa.Boolean(), nullable=True),
            sa.Column("data_source", sa.String(length=32), nullable=True),
            sa.Column("close_price", sa.Float(), nullable=True),
            sa.Column("adv_usd", sa.Float(), nullable=True),
            sa.Column("spread_bps", sa.Float(), nullable=True),
            sa.Column("market_cap", sa.Float(), nullable=True),
            sa.Column("atr_pct_20", sa.Float(), nullable=True),
            sa.Column("earnings_blackout", sa.Boolean(), nullable=True),
            sa.Column("data_quality_grade", sa.String(length=16), nullable=False, server_default="unknown"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["universe_run_id"],
                ["tradable_universe_runs.universe_run_id"],
                name="fk_universe_history_run",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("universe_run_id", "symbol", name="pk_tradable_universe_history"),
        )
        op.create_index(
            "idx_universe_history_scope",
            "tradable_universe_history",
            ["universe_run_id", "is_tradable", "symbol"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("tradable_universe_history"):
        op.drop_table("tradable_universe_history")
    inspector = sa.inspect(bind)
    if inspector.has_table("tradable_universe_runs"):
        op.drop_table("tradable_universe_runs")