"""Add stock_fundamentals_daily table for ML fundamental features.

Revision ID: 0055_add_stock_fundamentals_daily
Revises: 0054_add_model_batch_diagnostics
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0055_add_stock_fundamentals_daily"
down_revision = "0054_add_model_batch_diagnostics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("stock_fundamentals_daily"):
        return

    op.create_table(
        "stock_fundamentals_daily",
        # ── PK ──
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),

        # ── Keys ──
        sa.Column("symbol", sa.String(length=20), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False,
                  comment="UTC timestamp of the EODHD API fetch"),

        # ── Valuation ──
        sa.Column("pe_ratio", sa.Float(), nullable=True,
                  comment="Trailing P/E (Highlights.PERatio)"),
        sa.Column("forward_pe", sa.Float(), nullable=True,
                  comment="Forward P/E (Valuation.ForwardPE)"),
        sa.Column("peg_ratio", sa.Float(), nullable=True,
                  comment="PEG ratio (Highlights.PEGRatio)"),
        sa.Column("pb_ratio", sa.Float(), nullable=True,
                  comment="Price/Book MRQ (Valuation.PriceBookMRQ)"),
        sa.Column("ps_ratio", sa.Float(), nullable=True,
                  comment="Price/Sales TTM (Valuation.PriceSalesTTM)"),
        sa.Column("ev_to_ebitda", sa.Float(), nullable=True,
                  comment="EV/EBITDA (Valuation.EnterpriseValueEbitda)"),

        # ── Profitability ──
        sa.Column("roe", sa.Float(), nullable=True,
                  comment="Return on Equity TTM (Highlights.ReturnOnEquityTTM)"),
        sa.Column("roa", sa.Float(), nullable=True,
                  comment="Return on Assets TTM (Highlights.ReturnOnAssetsTTM)"),
        sa.Column("net_margin", sa.Float(), nullable=True,
                  comment="Net profit margin (Highlights.ProfitMargin)"),
        sa.Column("operating_margin", sa.Float(), nullable=True,
                  comment="Operating margin TTM (Highlights.OperatingMarginTTM)"),
        sa.Column("gross_margin", sa.Float(), nullable=True,
                  comment="Gross margin = GrossProfitTTM / RevenueTTM"),

        # ── Growth ──
        sa.Column("eps_growth_yoy", sa.Float(), nullable=True,
                  comment="Quarterly earnings growth YoY (Highlights.QuarterlyEarningsGrowthYOY)"),
        sa.Column("revenue_growth_yoy", sa.Float(), nullable=True,
                  comment="Quarterly revenue growth YoY (Highlights.QuarterlyRevenueGrowthYOY)"),

        # ── Health ──
        sa.Column("debt_to_equity", sa.Float(), nullable=True,
                  comment="Total Debt / Equity (from Balance_Sheet quarterly)"),
        sa.Column("current_ratio", sa.Float(), nullable=True,
                  comment="Current assets / Current liabilities (from Balance_Sheet quarterly)"),

        # ── Yield ──
        sa.Column("dividend_yield", sa.Float(), nullable=True,
                  comment="Dividend yield % (Highlights.DividendYield)"),

        # ── Market ──
        sa.Column("market_cap", sa.Float(), nullable=True,
                  comment="Market capitalization (Highlights.MarketCapitalization)"),
        sa.Column("beta", sa.Float(), nullable=True,
                  comment="Beta (Technicals.Beta)"),
        sa.Column("eps", sa.Float(), nullable=True,
                  comment="Earnings per share (Highlights.EarningsShare)"),
        sa.Column("book_value_per_share", sa.Float(), nullable=True,
                  comment="Book value per share (Highlights.BookValue)"),
        sa.Column("ebitda", sa.Float(), nullable=True,
                  comment="EBITDA (Highlights.EBITDA)"),

        # ── Estimates (forward-looking, PIT-OK car publication date connue) ──
        sa.Column("eps_estimate_current", sa.Float(), nullable=True,
                  comment="EPS estimate current year (Highlights.EPSEstimateCurrentYear)"),
        sa.Column("eps_estimate_next", sa.Float(), nullable=True,
                  comment="EPS estimate next year (Highlights.EPSEstimateNextYear)"),

        # ── Metadata ──
        sa.Column("source", sa.String(length=32), nullable=False, server_default="EODHD",
                  comment="Data provider: EODHD, Finnhub, Yahoo Finance"),

        # ── Constraints ──
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "trade_date", name="uq_symbol_date"),
    )

    # ── Indexes ──
    op.create_index("idx_sfd_symbol", "stock_fundamentals_daily", ["symbol"])
    op.create_index("idx_sfd_date", "stock_fundamentals_daily", ["trade_date"])
    op.create_index("idx_sfd_symbol_date", "stock_fundamentals_daily", ["symbol", "trade_date"])


def downgrade() -> None:
    op.drop_table("stock_fundamentals_daily")
