"""Add execution sprint 1 foundations.

Revision ID: 0008_add_execution_sprint1_foundations
Revises: 0007_add_run_business_summaries_table
"""
from alembic import op
import sqlalchemy as sa

revision = "0008_add_execution_sprint1_foundations"
down_revision = "0007_add_run_business_summaries_table"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "execution_runs",
        sa.Column("execution_profile", sa.String(length=32), nullable=False, server_default=sa.text("'overnight_cash_swing'")),
    )
    op.add_column(
        "execution_runs",
        sa.Column("submission_window", sa.String(length=16), nullable=False, server_default=sa.text("'both'")),
    )
    op.create_index("idx_er_account_date", "execution_runs", ["account_id", "trade_date"])

    op.create_table(
        "execution_targets_snapshot",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("exec_run_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False, server_default=sa.text("'default'")),
        sa.Column("risk_run_id", sa.String(length=32), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("decision_rank", sa.Integer(), nullable=True),
        sa.Column("side", sa.String(length=10), nullable=True),
        sa.Column("target_shares", sa.Integer(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("target_weight", sa.Float(), nullable=False),
        sa.Column("sector", sa.String(length=60), nullable=True),
        sa.Column("conviction_score", sa.Float(), nullable=True),
        sa.Column("sizing_method", sa.String(length=20), nullable=True),
        sa.Column("kelly_fraction", sa.Float(), nullable=True),
        sa.Column("atr_20", sa.Float(), nullable=True),
        sa.Column("price_asof_date", sa.Date(), nullable=True),
        sa.Column("atr_asof_date", sa.Date(), nullable=True),
        sa.Column("stop_price_initial", sa.Float(), nullable=True),
        sa.Column("risk_per_share", sa.Float(), nullable=True),
        sa.Column("risk_budget_dollars", sa.Float(), nullable=True),
        sa.Column("initial_risk_dollars", sa.Float(), nullable=True),
        sa.Column("target_notional", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_ets_run", "execution_targets_snapshot", ["exec_run_id"])
    op.create_index("idx_ets_account", "execution_targets_snapshot", ["account_id"])
    op.create_index("idx_ets_symbol", "execution_targets_snapshot", ["symbol"])

    op.create_table(
        "execution_locks",
        sa.Column("account_id", sa.String(length=32), nullable=False, primary_key=True),
        sa.Column("locked_by_run_id", sa.String(length=32), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_execution_locks_expires_at", "execution_locks", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_execution_locks_expires_at", table_name="execution_locks")
    op.drop_table("execution_locks")

    op.drop_index("idx_ets_symbol", table_name="execution_targets_snapshot")
    op.drop_index("idx_ets_account", table_name="execution_targets_snapshot")
    op.drop_index("idx_ets_run", table_name="execution_targets_snapshot")
    op.drop_table("execution_targets_snapshot")

    op.drop_index("idx_er_account_date", table_name="execution_runs")
    op.drop_column("execution_runs", "submission_window")
    op.drop_column("execution_runs", "execution_profile")

