"""Add account_id column to multi-account tables.

Revision ID: 0002
Revises: 0001_initial
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_add_account_id"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_TABLES = [
    "execution_runs",
    "broker_positions_snapshots",
    "risk_decisions",
    "portfolio_targets",
    "corporate_actions_applications",
    "portfolio_cash_ledger",
]


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(table, sa.Column("account_id", sa.String(32), nullable=True, server_default="default"))
        op.create_index(f"idx_{table}_account_id", table, ["account_id"])
    # backfill existing rows
    for table in _TABLES:
        op.execute(f"UPDATE {table} SET account_id = 'default' WHERE account_id IS NULL")


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"idx_{table}_account_id", table_name=table)
        op.drop_column(table, "account_id")

