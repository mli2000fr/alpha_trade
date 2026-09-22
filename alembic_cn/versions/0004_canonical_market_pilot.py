"""Socle canonique pilote du Sprint 7-A.

Revision ID: 0004_canonical_market_pilot
Revises: 0003_provider_neutral_staging
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0004_canonical_market_pilot"
down_revision = "0003_provider_neutral_staging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    database = connection.exec_driver_sql("SELECT DATABASE()").scalar()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur {database!r}")
    path = Path(__file__).resolve().parents[2] / "database" / "sql" / "cn" / "migration_cn_0004_canonical_market_pilot.sql"
    sql = path.read_text(encoding="utf-8")
    for statement in sql.split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in (
        "cn_canonicalization_runs",
        "instrument_adjustment_factors",
        "stock_bars_daily",
        "market_sessions",
        "instrument_status_history",
        "instrument_provider_symbols",
        "instruments",
        "markets",
    ):
        op.execute(f"DROP TABLE IF EXISTS `{table}`")
