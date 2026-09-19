"""Create the canonical market and instrument foundation.

Revision ID: 0084_market_instrument_foundation
Revises: 0083_finra_fractional_short_volume
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from alembic import op

revision: str = "0084_market_instrument_foundation"
down_revision: str | None = "0083_finra_fractional_short_volume"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_SQL_FILES = (
    "markets.sql",
    "instruments.sql",
    "instrument_provider_symbols.sql",
    "instrument_status_history.sql",
    "market_sessions.sql",
    "market_execution_rules.sql",
)

_MARKET_SEED_SQL = """
INSERT IGNORE INTO markets (
    market_code, database_alias, country_code, currency, timezone,
    calendar_id, benchmark_symbol, sector_taxonomy, enabled, live_enabled,
    context_fingerprint
) VALUES
(
    'US_EQ', 'us_primary', 'US', 'USD', 'America/New_York',
    'NYSE', 'SPY', 'GICS', TRUE, TRUE,
    'ac71a3039fb43e25ac732d0393a7748bca85272db35ee89472d46368809546e2'
),
(
    'CN_A', 'cn_primary', 'CN', 'CNY', 'Asia/Shanghai',
    'CN_A', '000300.SH', 'SW_2021', FALSE, FALSE,
    '428aee24c2ae09ab9659af003f823bd1e4b54fad5df53670d520ce49220fa712'
),
(
    'CN_BJ', 'cn_primary', 'CN', 'CNY', 'Asia/Shanghai',
    'CN_BJ', '899050.BJ', 'SW_2021', FALSE, FALSE,
    '92027ad6930ba37ec32cf82fa855a5d6935370cb4322331e23f255c0f752df44'
)
"""

_INSERT_TRIGGER = """
CREATE TRIGGER trg_ips_no_overlap_insert
BEFORE INSERT ON instrument_provider_symbols
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1
        FROM instrument_provider_symbols existing
        WHERE existing.provider = NEW.provider
          AND existing.provider_symbol = NEW.provider_symbol
          AND existing.valid_from <= COALESCE(NEW.valid_to, '9999-12-31')
          AND COALESCE(existing.valid_to, '9999-12-31') >= NEW.valid_from
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'overlapping provider symbol validity';
    END IF;
    IF NEW.is_primary = TRUE AND EXISTS (
        SELECT 1
        FROM instrument_provider_symbols existing
        WHERE existing.instrument_id = NEW.instrument_id
          AND existing.provider = NEW.provider
          AND existing.is_primary = TRUE
          AND existing.valid_from <= COALESCE(NEW.valid_to, '9999-12-31')
          AND COALESCE(existing.valid_to, '9999-12-31') >= NEW.valid_from
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'overlapping primary provider mapping';
    END IF;
END
"""

_UPDATE_TRIGGER = """
CREATE TRIGGER trg_ips_no_overlap_update
BEFORE UPDATE ON instrument_provider_symbols
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1
        FROM instrument_provider_symbols existing
        WHERE existing.mapping_id <> NEW.mapping_id
          AND existing.provider = NEW.provider
          AND existing.provider_symbol = NEW.provider_symbol
          AND existing.valid_from <= COALESCE(NEW.valid_to, '9999-12-31')
          AND COALESCE(existing.valid_to, '9999-12-31') >= NEW.valid_from
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'overlapping provider symbol validity';
    END IF;
    IF NEW.is_primary = TRUE AND EXISTS (
        SELECT 1
        FROM instrument_provider_symbols existing
        WHERE existing.mapping_id <> NEW.mapping_id
          AND existing.instrument_id = NEW.instrument_id
          AND existing.provider = NEW.provider
          AND existing.is_primary = TRUE
          AND existing.valid_from <= COALESCE(NEW.valid_to, '9999-12-31')
          AND COALESCE(existing.valid_to, '9999-12-31') >= NEW.valid_from
    ) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'overlapping primary provider mapping';
    END IF;
END
"""


def _sql_root() -> Path:
    return Path(__file__).resolve().parents[2] / "database" / "sql" / "market"


def _create_mysql_temporal_guards() -> None:
    bind = op.get_bind()
    if bind.dialect.name not in {"mysql", "mariadb"}:
        return
    op.execute("DROP TRIGGER IF EXISTS trg_ips_no_overlap_insert")
    op.execute("DROP TRIGGER IF EXISTS trg_ips_no_overlap_update")
    op.execute(_INSERT_TRIGGER)
    op.execute(_UPDATE_TRIGGER)


def upgrade() -> None:
    root = _sql_root()
    for filename in _SQL_FILES:
        op.execute((root / filename).read_text(encoding="utf-8").strip())
    bind = op.get_bind()
    if bind.dialect.name in {"mysql", "mariadb"}:
        op.execute(_MARKET_SEED_SQL)
    _create_mysql_temporal_guards()


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name in {"mysql", "mariadb"}:
        op.execute("DROP TRIGGER IF EXISTS trg_ips_no_overlap_update")
        op.execute("DROP TRIGGER IF EXISTS trg_ips_no_overlap_insert")
    for table in (
        "market_execution_rules",
        "market_sessions",
        "instrument_status_history",
        "instrument_provider_symbols",
        "instruments",
        "markets",
    ):
        op.execute(f"DROP TABLE IF EXISTS {table}")
