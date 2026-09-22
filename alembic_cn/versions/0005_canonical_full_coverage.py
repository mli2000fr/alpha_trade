"""Tables auxiliaires de canonicalisation complète Sprint 7-B.

Revision ID: 0005_canonical_full_coverage
Revises: 0004_canonical_market_pilot
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0005_canonical_full_coverage"
down_revision = "0004_canonical_market_pilot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    database = connection.exec_driver_sql("SELECT DATABASE()").scalar()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur {database!r}")
    path = Path(__file__).resolve().parents[2] / "database" / "sql" / "cn" / "migration_cn_0005_canonical_full_coverage.sql"
    for statement in path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in ("cn_canonical_coverage_metrics", "cn_corporate_actions", "cn_daily_price_limits"):
        op.execute(f"DROP TABLE IF EXISTS `{table}`")
