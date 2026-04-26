"""Add execution sprint 4 positions and lots.

Revision ID: 0010_add_execution_sprint4_positions
Revises: 0009_add_execution_sprint2_persistence
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_add_execution_sprint4_positions"
down_revision = "0009_add_execution_sprint2_persistence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_positions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("net_qty", sa.Float(), nullable=False),
        sa.Column("avg_entry_price", sa.Float(), nullable=True),
        sa.Column("market_price", sa.Float(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("unrealized_pnl", sa.Float(), nullable=True),
        sa.Column("broker_mode", sa.String(length=10), nullable=True),
        sa.Column("source_exec_run_id", sa.String(length=32), nullable=True),
        sa.Column("position_status", sa.String(length=16), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("last_broker_snapshot_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("uq_ep_account_symbol", "execution_positions", ["account_id", "symbol"], unique=True)
    op.create_index("idx_ep_account_status", "execution_positions", ["account_id", "position_status"])
    op.create_index("idx_ep_source_exec_run", "execution_positions", ["source_exec_run_id"])

    op.create_table(
        "execution_position_lots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("lot_id", sa.String(length=40), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("opened_qty", sa.Float(), nullable=False),
        sa.Column("remaining_qty", sa.Float(), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("open_exec_run_id", sa.String(length=32), nullable=True),
        sa.Column("open_request_id", sa.String(length=32), nullable=True),
        sa.Column("open_fill_id", sa.String(length=32), nullable=True),
        sa.Column("lot_status", sa.String(length=16), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("close_exec_run_id", sa.String(length=32), nullable=True),
        sa.Column("close_request_id", sa.String(length=32), nullable=True),
        sa.Column("close_fill_id", sa.String(length=32), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("exit_price", sa.Float(), nullable=True),
        sa.Column("source_kind", sa.String(length=32), nullable=False, server_default=sa.text("'execution_broker_fill'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("uq_epl_lot_id", "execution_position_lots", ["lot_id"], unique=True)
    op.create_index("idx_epl_account_symbol", "execution_position_lots", ["account_id", "symbol"])
    op.create_index("idx_epl_account_status", "execution_position_lots", ["account_id", "lot_status"])
    op.create_index("idx_epl_open_fill", "execution_position_lots", ["open_fill_id"])


def downgrade() -> None:
    op.drop_index("idx_epl_open_fill", table_name="execution_position_lots")
    op.drop_index("idx_epl_account_status", table_name="execution_position_lots")
    op.drop_index("idx_epl_account_symbol", table_name="execution_position_lots")
    op.drop_index("uq_epl_lot_id", table_name="execution_position_lots")
    op.drop_table("execution_position_lots")

    op.drop_index("idx_ep_source_exec_run", table_name="execution_positions")
    op.drop_index("idx_ep_account_status", table_name="execution_positions")
    op.drop_index("uq_ep_account_symbol", table_name="execution_positions")
    op.drop_table("execution_positions")

