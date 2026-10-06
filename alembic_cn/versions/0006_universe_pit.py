"""Univers chinois quotidien point-in-time, Sprint 8.

Revision ID: 0006_universe_pit
Revises: 0005_canonical_full_coverage
"""

from pathlib import Path

from alembic import op

revision = "0006_universe_pit"
down_revision = "0005_canonical_full_coverage"
branch_labels = None
depends_on = None


def upgrade() -> None:
    database = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if database != "alpha_trade_cn":
        raise RuntimeError(f"Migration CN refusée sur {database!r}")
    path = Path(__file__).resolve().parents[2] / "database" / "sql" / "cn" / "migration_cn_0006_universe_pit.sql"
    for statement in path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    for table in ("cn_universe_execution_audit", "cn_universe_decisions", "cn_universe_runs"):
        op.execute(f"DROP TABLE IF EXISTS `{table}`")
