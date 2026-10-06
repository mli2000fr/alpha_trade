"""Historique et liquidité de recherche France, Sprint 6-B.

Revision ID: 0007_fr_liquidity_research
Revises: 0006_fr_universe_contract
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0007_fr_liquidity_research"
down_revision = "0006_fr_universe_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    actual = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if actual != "alpha_trade_fr":
        raise RuntimeError(f"Migration FR refusée sur {actual!r}")
    sql_path = (
        Path(__file__).resolve().parents[2]
        / "database"
        / "sql"
        / "fr"
        / "migration_fr_0007_liquidity_research.sql"
    )
    for statement in sql_path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade FR 0007 destructif interdit ; restaurer une sauvegarde vérifiée"
    )
