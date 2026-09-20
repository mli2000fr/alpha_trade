"""Add nullable instrument identity to canonical US facts.

Revision ID: 0087_us_fact_instrument_columns
Revises: 0086_market_calendar_pit
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0087_us_fact_instrument_columns"
down_revision: str | None = "0086_market_calendar_pit"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

FACT_TABLES = (
    "stock_metadata",
    "stock_bars_daily",
    "stock_bars",
    "stock_quote_snapshots",
    "stock_scores",
    "stock_scores_history",
    "tradable_universe_history",
    "model_predictions",
    "global_rank_history",
    "global_oracle_labels",
    "oracle_extreme_predictions",
    "model_registry",
    "model_metrics",
    "model_metrics_full",
    "model_batch_diagnostics",
    "model_directional_oos_metrics",
    "champion_history",
    "model_governance",
    "stock_fundamentals_daily",
    "stock_earnings_calendar",
    "stock_analyst_consensus_snapshots",
    "stock_analyst_eps_revision_history",
    "stock_analyst_eps_trend_history",
    "stock_analyst_estimate_history",
    "stock_analyst_recommendation_history",
    "stock_analyst_target_history",
    "ticker_daily_sentiment_features",
    "news_ticker_sentiment",
    "corporate_action_source_events",
    "corporate_actions_events",
    "corporate_actions_applications",
    "sec_filing_raw",
    "sec_corporate_events",
)


def _existing_tables() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return set(inspector.get_table_names())


def upgrade() -> None:
    existing = _existing_tables()
    for table in FACT_TABLES:
        if table in existing:
            op.add_column(table, sa.Column("instrument_id", mysql.BIGINT(unsigned=True), nullable=True))


def downgrade() -> None:
    existing = _existing_tables()
    for table in reversed(FACT_TABLES):
        if table in existing and "instrument_id" in {
            column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)
        }:
            op.drop_column(table, "instrument_id")
