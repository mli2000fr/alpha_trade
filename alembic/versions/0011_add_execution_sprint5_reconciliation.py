"""Add execution sprint 5 reconciliation results.

Revision ID: 0011_add_execution_sprint5_reconciliation
Revises: 0010_add_execution_sprint4_positions
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_add_execution_sprint5_reconciliation"
down_revision = "0010_add_execution_sprint4_positions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_reconciliation_results",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("exec_run_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("target_qty", sa.Float(), nullable=False),
        sa.Column("internal_position_qty", sa.Float(), nullable=False),
        sa.Column("broker_position_qty", sa.Float(), nullable=False),
        sa.Column("position_delta", sa.Float(), nullable=False),
        sa.Column("open_request_buy_qty", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("open_request_sell_qty", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("open_broker_buy_qty", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("open_broker_sell_qty", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("has_open_protection", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("protection_qty", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("reconciliation_status", sa.String(length=20), nullable=False),
        sa.Column("reason_code", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("uq_err_exec_account_symbol", "execution_reconciliation_results", ["exec_run_id", "account_id", "symbol"], unique=True)
    op.create_index("idx_err_account_status", "execution_reconciliation_results", ["account_id", "reconciliation_status"])
    op.create_index("idx_err_exec_run", "execution_reconciliation_results", ["exec_run_id"])
    op.create_index("idx_err_action", "execution_reconciliation_results", ["action"])


def downgrade() -> None:
    op.drop_index("idx_err_action", table_name="execution_reconciliation_results")
    op.drop_index("idx_err_exec_run", table_name="execution_reconciliation_results")
    op.drop_index("idx_err_account_status", table_name="execution_reconciliation_results")
    op.drop_index("uq_err_exec_account_symbol", table_name="execution_reconciliation_results")
    op.drop_table("execution_reconciliation_results")

