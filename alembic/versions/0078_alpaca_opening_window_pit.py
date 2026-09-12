"""Alpaca SIP opening-window bars with append-only PIT versions.

Revision ID: 0078_alpaca_opening_window_pit
Revises: 0077_yahoo_analyst_trends
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0078_alpaca_opening_window_pit"
down_revision: str | None = "0077_yahoo_analyst_trends"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

SCHEMA = "alpha_trade"


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"] for column in inspector.get_columns(
            "stock_opening_window_bars", schema=SCHEMA,
        )
    }
    additions = {
        "feed": sa.Column(
            "feed", sa.String(16), nullable=False, server_default="legacy",
        ),
        "adjustment_mode": sa.Column(
            "adjustment_mode", sa.String(16), nullable=False, server_default="raw",
        ),
        "trade_count": sa.Column("trade_count", sa.BigInteger()),
        "vwap": sa.Column("vwap", sa.Double()),
    }
    for name, column in additions.items():
        if name not in columns:
            op.add_column("stock_opening_window_bars", column, schema=SCHEMA)

    primary = inspector.get_pk_constraint("stock_opening_window_bars", schema=SCHEMA)
    primary_columns = list(primary.get("constrained_columns") or [])
    desired_primary = ["provider", "feed", "symbol", "bar_timestamp"]
    if primary_columns != desired_primary:
        op.drop_constraint(
            str(primary.get("name") or "PRIMARY"), "stock_opening_window_bars",
            schema=SCHEMA, type_="primary",
        )
        op.create_primary_key(
            "pk_stock_opening_window_bars", "stock_opening_window_bars",
            desired_primary, schema=SCHEMA,
        )

    indexes = {
        index["name"] for index in inspector.get_indexes(
            "stock_opening_window_bars", schema=SCHEMA,
        )
    }
    if "idx_sowb_symbol_time" not in indexes:
        op.create_index(
            "idx_sowb_symbol_time", "stock_opening_window_bars",
            ["symbol", "bar_timestamp"], schema=SCHEMA,
        )

    if inspector.has_table("stock_opening_window_bar_versions", schema=SCHEMA):
        return
    op.create_table(
        "stock_opening_window_bar_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("feed", sa.String(16), nullable=False),
        sa.Column("adjustment_mode", sa.String(16), nullable=False, server_default="raw"),
        sa.Column("symbol", sa.String(32), nullable=False),
        sa.Column("bar_timestamp", sa.DateTime(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("open", sa.Double(), nullable=False),
        sa.Column("high", sa.Double(), nullable=False),
        sa.Column("low", sa.Double(), nullable=False),
        sa.Column("close", sa.Double(), nullable=False),
        sa.Column("cumulative_volume", sa.BigInteger()),
        sa.Column("minute_volume", sa.BigInteger()),
        sa.Column("trade_count", sa.BigInteger()),
        sa.Column("vwap", sa.Double()),
        sa.Column("session_name", sa.String(16)),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "feed", "symbol", "bar_timestamp", "payload_hash",
            name="uq_sowbv_identity_hash",
        ),
        sa.Index("idx_sowbv_symbol_time", "symbol", "bar_timestamp"),
        sa.Index("idx_sowbv_available", "provider", "feed", "available_at"),
        schema=SCHEMA, mysql_charset="utf8mb4",
    )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("stock_opening_window_bar_versions", schema=SCHEMA):
        op.drop_table("stock_opening_window_bar_versions", schema=SCHEMA)
    indexes = {
        index["name"] for index in inspector.get_indexes(
            "stock_opening_window_bars", schema=SCHEMA,
        )
    }
    if "idx_sowb_symbol_time" in indexes:
        op.drop_index(
            "idx_sowb_symbol_time", table_name="stock_opening_window_bars",
            schema=SCHEMA,
        )
    primary = inspector.get_pk_constraint("stock_opening_window_bars", schema=SCHEMA)
    if "feed" in (primary.get("constrained_columns") or []):
        op.drop_constraint(
            str(primary.get("name") or "PRIMARY"), "stock_opening_window_bars",
            schema=SCHEMA, type_="primary",
        )
        op.create_primary_key(
            "PRIMARY", "stock_opening_window_bars",
            ["provider", "symbol", "bar_timestamp"], schema=SCHEMA,
        )
    columns = {
        column["name"] for column in inspector.get_columns(
            "stock_opening_window_bars", schema=SCHEMA,
        )
    }
    for column in ("vwap", "trade_count", "adjustment_mode", "feed"):
        if column in columns:
            op.drop_column("stock_opening_window_bars", column, schema=SCHEMA)
