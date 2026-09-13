"""Delayed Alpaca option bars and prospective OCC adjustments.

Revision ID: 0079_delayed_options_occ
Revises: 0078_alpaca_opening_window_pit
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0079_delayed_options_occ"
down_revision: str | None = "0078_alpaca_opening_window_pit"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None
SCHEMA = "alpha_trade"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table("stock_option_contract_versions", schema=SCHEMA):
        op.create_table(
            "stock_option_contract_versions",
            sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("contract_symbol", sa.String(64), nullable=False),
            sa.Column("underlying_symbol", sa.String(32), nullable=False),
            sa.Column("root_symbol", sa.String(32)), sa.Column("status", sa.String(24)),
            sa.Column("expiration_date", sa.Date()), sa.Column("strike", sa.Double()),
            sa.Column("option_type", sa.String(8)), sa.Column("exercise_style", sa.String(16)),
            sa.Column("multiplier", sa.Double()), sa.Column("contract_size", sa.Double()),
            sa.Column("open_interest", sa.BigInteger()), sa.Column("open_interest_date", sa.Date()),
            sa.Column("close_price", sa.Double()), sa.Column("close_price_date", sa.Date()),
            sa.Column("deliverables_json", sa.Text()),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("available_at", sa.DateTime(), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.UniqueConstraint("provider", "contract_symbol", "payload_hash", name="uq_socv_provider_contract_hash"),
            sa.Index("idx_socv_underlying_available", "underlying_symbol", "available_at"),
            schema=SCHEMA, mysql_charset="utf8mb4",
        )
    if not inspector.has_table("stock_option_bars_delayed", schema=SCHEMA):
        op.create_table(
            "stock_option_bars_delayed",
            sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("feed", sa.String(32), nullable=False),
            sa.Column("provenance_status", sa.String(32), nullable=False),
            sa.Column("underlying_symbol", sa.String(32), nullable=False),
            sa.Column("contract_symbol", sa.String(64), nullable=False),
            sa.Column("expiration_date", sa.Date()), sa.Column("strike", sa.Double()),
            sa.Column("option_type", sa.String(8)), sa.Column("timeframe", sa.String(12), nullable=False),
            sa.Column("bar_timestamp", sa.DateTime(), nullable=False),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("available_at", sa.DateTime(), nullable=False),
            sa.Column("open", sa.Double(), nullable=False), sa.Column("high", sa.Double(), nullable=False),
            sa.Column("low", sa.Double(), nullable=False), sa.Column("close", sa.Double(), nullable=False),
            sa.Column("volume", sa.BigInteger()), sa.Column("trade_count", sa.BigInteger()),
            sa.Column("vwap", sa.Double()), sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.UniqueConstraint("provider", "feed", "contract_symbol", "timeframe", "bar_timestamp", "payload_hash", name="uq_sobd_identity_hash"),
            sa.Index("idx_sobd_underlying_time", "underlying_symbol", "bar_timestamp"),
            sa.Index("idx_sobd_available", "provider", "available_at"),
            schema=SCHEMA, mysql_charset="utf8mb4",
        )
    if not inspector.has_table("option_contract_adjustments", schema=SCHEMA):
        op.create_table(
            "option_contract_adjustments",
            sa.Column("id", sa.BigInteger(), autoincrement=True, primary_key=True),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("occ_memo_number", sa.String(16), nullable=False),
            sa.Column("published_at", sa.DateTime()), sa.Column("effective_at", sa.DateTime()),
            sa.Column("category", sa.String(128)), sa.Column("title", sa.String(1024), nullable=False),
            sa.Column("source_url", sa.String(1024)), sa.Column("adjustment_type", sa.String(32)),
            sa.Column("old_option_root", sa.String(64)), sa.Column("new_option_root", sa.String(64)),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("available_at", sa.DateTime(), nullable=False),
            sa.Column("payload_hash", sa.String(64), nullable=False),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.UniqueConstraint("provider", "occ_memo_number", "payload_hash", name="uq_oca_provider_memo_hash"),
            sa.Index("idx_oca_published", "published_at"),
            sa.Index("idx_oca_roots", "old_option_root", "new_option_root"),
            schema=SCHEMA, mysql_charset="utf8mb4",
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table_name in ("option_contract_adjustments", "stock_option_bars_delayed", "stock_option_contract_versions"):
        if inspector.has_table(table_name, schema=SCHEMA):
            op.drop_table(table_name, schema=SCHEMA)
