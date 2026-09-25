"""Index des exceptions pour le gate d'univers CN Sprint 8.

Revision ID: 0007_universe_audit_indexes
Revises: 0006_universe_pit
"""

from pathlib import Path

from alembic import op

revision = "0007_universe_audit_indexes"
down_revision = "0006_universe_pit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    database = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur {database!r}")
    path = Path(__file__).resolve().parents[2] / "database" / "sql" / "cn" / "migration_cn_0007_universe_audit_indexes.sql"
    for statement in path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    op.execute("DROP INDEX ix_cn_limits_policy_date ON cn_daily_price_limits")
    op.execute("DROP INDEX ix_cn_daily_status_date ON stock_bars_daily")
