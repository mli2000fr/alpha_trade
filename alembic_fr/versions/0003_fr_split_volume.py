"""Séparer le volume ajusté des splits EODHD du volume brut inconnu.

Revision ID: 0003_fr_split_volume
Revises: 0002_fr_prices
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0003_fr_split_volume"
down_revision = "0002_fr_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    actual = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if actual != "alpha_trade_fr":
        raise RuntimeError(f"Migration FR refusée sur {actual!r}")
    sql_path = (Path(__file__).resolve().parents[2] / "database" / "sql" / "fr"
                / "migration_fr_0003_split_volume.sql")
    for statement in sql_path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Downgrade FR 0003 destructif interdit ; restaurer une sauvegarde vérifiée")
