from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_fundamentals_reference_sql_keeps_providers_independent() -> None:
    sql = (
        ROOT / "database/sql/stock/stock_fundamentals_daily.sql"
    ).read_text(encoding="utf-8")
    assert "uq_sfd_symbol_date_source (symbol, trade_date, source)" in sql
    assert "uq_symbol_date (symbol, trade_date)" not in sql


def test_multi_provider_migration_follows_current_head() -> None:
    migration = (
        ROOT / "alembic/versions/0073_fundamentals_multi_provider_identity.py"
    ).read_text(encoding="utf-8")
    assert 'down_revision: str | None = "0072_oracle_label_quality"' in migration
    assert '"symbol", "trade_date", "source"' in migration
