"""Stockage brut, actions sur titres et canonique FR sans ingestion implicite.

Revision ID: 0002_fr_prices
Revises: 0001_fr_reference
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0002_fr_prices"
down_revision = "0001_fr_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    actual = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if actual != "alpha_trade_fr":
        raise RuntimeError(f"Migration FR refusée sur {actual!r}")
    sql_path = (Path(__file__).resolve().parents[2] / "database" / "sql" / "fr"
                / "migration_fr_0002_prices.sql")
    for statement in sql_path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Downgrade FR 0002 destructif interdit ; restaurer une sauvegarde vérifiée")
