"""Add execution sprint 2 persistence.

Revision ID: 0009_add_execution_sprint2_persistence
Revises: 0008_add_execution_sprint1_foundations
"""
from alembic import op
import sqlalchemy as sa

revision = "0009_add_execution_sprint2_persistence"
down_revision = "0008_add_execution_sprint1_foundations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "execution_order_requests",
        sa.Column("request_id", sa.String(length=32), primary_key=True),
        sa.Column("exec_run_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("risk_run_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("target_qty", sa.Float(), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("business_key", sa.String(length=64), nullable=False),
        sa.Column("submission_key", sa.String(length=64), nullable=True),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column("parent_request_id", sa.String(length=32), nullable=True),
        sa.Column("intent_role", sa.String(length=20), nullable=False),
        sa.Column("decision_price", sa.Float(), nullable=True),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("trail_percent", sa.Float(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'NEW'")),
        sa.Column("failure_reason", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("uq_eor_account_business_attempt", "execution_order_requests", ["account_id", "business_key", "attempt_no"], unique=True)
    op.create_index("uq_eor_submission_key", "execution_order_requests", ["submission_key"], unique=True)
    op.create_index("idx_eor_exec_run", "execution_order_requests", ["exec_run_id"])
    op.create_index("idx_eor_business_key", "execution_order_requests", ["business_key"])
    op.create_index("idx_eor_parent_request", "execution_order_requests", ["parent_request_id"])
    op.create_index("idx_eor_status", "execution_order_requests", ["status"])

    op.create_table(
        "execution_broker_orders",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("request_id", sa.String(length=32), nullable=False),
        sa.Column("exec_run_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("broker_order_id", sa.String(length=64), nullable=False),
        sa.Column("client_order_id", sa.String(length=64), nullable=True),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("qty", sa.Float(), nullable=False),
        sa.Column("filled_qty", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("avg_fill_price", sa.Float(), nullable=True),
        sa.Column("raw_status", sa.String(length=32), nullable=False),
        sa.Column("normalized_status", sa.String(length=32), nullable=False),
        sa.Column("order_type", sa.String(length=20), nullable=False),
        sa.Column("limit_price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("trail_percent", sa.Float(), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=True),
        sa.Column("raw_response_json", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    )
    op.create_index("uq_ebo_broker_order_id", "execution_broker_orders", ["broker_order_id"], unique=True)
    op.create_index("idx_ebo_request_id", "execution_broker_orders", ["request_id"])
    op.create_index("idx_ebo_exec_run", "execution_broker_orders", ["exec_run_id"])
    op.create_index("idx_ebo_account_status", "execution_broker_orders", ["account_id", "normalized_status"])

    op.create_table(
        "execution_broker_fills",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("fill_id", sa.String(length=32), nullable=False),
        sa.Column("exec_run_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("broker_order_id", sa.String(length=64), nullable=False),
        sa.Column("request_id", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("filled_qty", sa.Float(), nullable=False),
        sa.Column("avg_fill_price", sa.Float(), nullable=False),
        sa.Column("fill_timestamp", sa.DateTime(), nullable=False),
        sa.Column("decision_price", sa.Float(), nullable=True),
        sa.Column("slippage_bps", sa.Float(), nullable=True),
        sa.Column("implementation_shortfall", sa.Float(), nullable=True),
        sa.Column("raw_fill_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("uq_ebf_fill_id", "execution_broker_fills", ["fill_id"], unique=True)
    op.create_index("idx_ebf_exec_run", "execution_broker_fills", ["exec_run_id"])
    op.create_index("idx_ebf_request_id", "execution_broker_fills", ["request_id"])
    op.create_index("idx_ebf_broker_order_id", "execution_broker_fills", ["broker_order_id"])

    op.create_table(
        "broker_account_snapshots",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("exec_run_id", sa.String(length=32), nullable=False),
        sa.Column("account_id", sa.String(length=32), nullable=False),
        sa.Column("broker_mode", sa.String(length=10), nullable=False),
        sa.Column("snapshot_kind", sa.String(length=20), nullable=False),
        sa.Column("equity", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("settled_cash", sa.Float(), nullable=False),
        sa.Column("buying_power", sa.Float(), nullable=False),
        sa.Column("daytrade_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("raw_payload_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_bas_exec_run", "broker_account_snapshots", ["exec_run_id"])
    op.create_index("idx_bas_account_kind", "broker_account_snapshots", ["account_id", "snapshot_kind"])


def downgrade() -> None:
    op.drop_index("idx_bas_account_kind", table_name="broker_account_snapshots")
    op.drop_index("idx_bas_exec_run", table_name="broker_account_snapshots")
    op.drop_table("broker_account_snapshots")

    op.drop_index("idx_ebf_broker_order_id", table_name="execution_broker_fills")
    op.drop_index("idx_ebf_request_id", table_name="execution_broker_fills")
    op.drop_index("idx_ebf_exec_run", table_name="execution_broker_fills")
    op.drop_index("uq_ebf_fill_id", table_name="execution_broker_fills")
    op.drop_table("execution_broker_fills")

    op.drop_index("idx_ebo_account_status", table_name="execution_broker_orders")
    op.drop_index("idx_ebo_exec_run", table_name="execution_broker_orders")
    op.drop_index("idx_ebo_request_id", table_name="execution_broker_orders")
    op.drop_index("uq_ebo_broker_order_id", table_name="execution_broker_orders")
    op.drop_table("execution_broker_orders")

    op.drop_index("idx_eor_status", table_name="execution_order_requests")
    op.drop_index("idx_eor_parent_request", table_name="execution_order_requests")
    op.drop_index("idx_eor_business_key", table_name="execution_order_requests")
    op.drop_index("idx_eor_exec_run", table_name="execution_order_requests")
    op.drop_index("uq_eor_submission_key", table_name="execution_order_requests")
    op.drop_index("uq_eor_account_business_attempt", table_name="execution_order_requests")
    op.drop_table("execution_order_requests")

