"""Sprint S12.3 — Table ``broker_statements``.

Stocke les activities Alpaca (`/v2/account/activities`) en vue de la
réconciliation quotidienne avec les fills internes.

Revision ID: 0025_broker_statements
Revises: 0024_audit_chain
"""
from alembic import op
import sqlalchemy as sa


revision = "0025_broker_statements"
down_revision = "0024_audit_chain"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_statements",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("activity_id", sa.String(length=128), nullable=False),
        sa.Column("activity_type", sa.String(length=32), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=True),
        sa.Column("side", sa.String(length=16), nullable=True),
        sa.Column("qty", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("price", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("transaction_time", sa.DateTime, nullable=True),
        sa.Column("raw_json", sa.Text, nullable=False),
        sa.Column(
            "ingested_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.UniqueConstraint("account_id", "activity_id", name="uq_broker_statements_acct_activity"),
    )
    op.create_index(
        "idx_broker_statements_acct_time",
        "broker_statements",
        ["account_id", "transaction_time"],
    )
    op.create_index(
        "idx_broker_statements_symbol_time",
        "broker_statements",
        ["symbol", "transaction_time"],
    )


def downgrade() -> None:
    op.drop_index("idx_broker_statements_symbol_time", table_name="broker_statements")
    op.drop_index("idx_broker_statements_acct_time", table_name="broker_statements")
    op.drop_table("broker_statements")

