"""Add selector reference data tables and columns.

Revision ID: 0004_add_selector_reference_data
Revises: 0003_news_checkpoint_per_symbol
"""
from alembic import op
import sqlalchemy as sa


revision = "0004_add_selector_reference_data"
down_revision = "0003_news_checkpoint_per_symbol"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("stock_metadata", sa.Column("market_cap", sa.Float(), nullable=True))

    op.create_table(
        "stock_quote_snapshots",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("quote_date", sa.Date(), nullable=False),
        sa.Column("quote_timestamp", sa.DateTime(), nullable=True),
        sa.Column("bid_price", sa.Float(), nullable=True),
        sa.Column("ask_price", sa.Float(), nullable=True),
        sa.Column("bid_size", sa.Float(), nullable=True),
        sa.Column("ask_size", sa.Float(), nullable=True),
        sa.Column("spread_bps", sa.Float(), nullable=True),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "quote_date"),
    )
    op.create_index("idx_quote_date", "stock_quote_snapshots", ["quote_date"])
    op.create_index("idx_spread_bps", "stock_quote_snapshots", ["spread_bps"])

    op.create_table(
        "stock_earnings_calendar",
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("earnings_date", sa.Date(), nullable=False),
        sa.Column("eps_estimate", sa.Float(), nullable=True),
        sa.Column("eps_actual", sa.Float(), nullable=True),
        sa.Column("revenue_estimate", sa.Float(), nullable=True),
        sa.Column("revenue_actual", sa.Float(), nullable=True),
        sa.Column("fiscal_period", sa.String(length=32), nullable=True),
        sa.Column("last_updated", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("symbol", "earnings_date"),
    )
    op.create_index("idx_earnings_date", "stock_earnings_calendar", ["earnings_date"])
    op.create_index("idx_symbol_earnings_date", "stock_earnings_calendar", ["symbol", "earnings_date"])

    for table in ["stock_scores", "stock_scores_history"]:
        op.add_column(table, sa.Column("market_cap", sa.Float(), nullable=True))
        op.add_column(table, sa.Column("beta_126", sa.Float(), nullable=True))
        op.add_column(table, sa.Column("spread_bps", sa.Float(), nullable=True))
        op.add_column(table, sa.Column("earnings_date", sa.Date(), nullable=True))
        op.add_column(table, sa.Column("days_to_earnings", sa.Integer(), nullable=True))
        op.add_column(table, sa.Column("earnings_blackout", sa.Boolean(), nullable=True, server_default=sa.text("0")))


def downgrade() -> None:
    for table in ["stock_scores_history", "stock_scores"]:
        op.drop_column(table, "earnings_blackout")
        op.drop_column(table, "days_to_earnings")
        op.drop_column(table, "earnings_date")
        op.drop_column(table, "spread_bps")
        op.drop_column(table, "beta_126")
        op.drop_column(table, "market_cap")

    op.drop_index("idx_symbol_earnings_date", table_name="stock_earnings_calendar")
    op.drop_index("idx_earnings_date", table_name="stock_earnings_calendar")
    op.drop_table("stock_earnings_calendar")

    op.drop_index("idx_spread_bps", table_name="stock_quote_snapshots")
    op.drop_index("idx_quote_date", table_name="stock_quote_snapshots")
    op.drop_table("stock_quote_snapshots")

    op.drop_column("stock_metadata", "market_cap")

