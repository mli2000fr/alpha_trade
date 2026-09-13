"""Add prospective FINRA consolidated daily short-volume storage.

Revision ID: 0076_finra_short_volume
Revises: 0075_forward_pit_collection
"""
from collections.abc import Sequence

from alembic import op

revision: str = "0076_finra_short_volume"
down_revision: str | None = "0075_forward_pit_collection"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS alpha_trade.stock_short_volume_daily (
          id BIGINT AUTO_INCREMENT PRIMARY KEY,
          provider VARCHAR(32) NOT NULL,
          trade_date DATE NOT NULL,
          symbol VARCHAR(32) NOT NULL,
          market VARCHAR(16) NOT NULL,
          short_volume BIGINT NOT NULL,
          short_exempt_volume BIGINT NOT NULL,
          total_volume BIGINT NOT NULL,
          observed_at DATETIME(6) NOT NULL,
          available_at DATETIME(6) NOT NULL,
          payload_hash VARCHAR(64) NOT NULL,
          run_id VARCHAR(64) NOT NULL,
          is_correction BOOLEAN NOT NULL DEFAULT 0,
          UNIQUE KEY uq_ssvd_provider_date_symbol_market_hash
            (provider, trade_date, symbol, market, payload_hash),
          INDEX idx_ssvd_symbol_available(symbol, available_at),
          INDEX idx_ssvd_trade_date(trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS alpha_trade.stock_short_volume_daily")
