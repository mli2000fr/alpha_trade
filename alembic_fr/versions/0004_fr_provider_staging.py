"""Staging EODHD France indépendant de l'identité et du MIC vérifié.

Revision ID: 0004_fr_provider_staging
Revises: 0003_fr_split_volume
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0004_fr_provider_staging"
down_revision = "0003_fr_split_volume"
branch_labels = None
depends_on = None


def upgrade() -> None:
    actual = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if actual != "alpha_trade_fr":
        raise RuntimeError(f"Migration FR refusée sur {actual!r}")
    sql_path = (Path(__file__).resolve().parents[2] / "database" / "sql" / "fr"
                / "migration_fr_0004_provider_staging.sql")
    for statement in sql_path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Downgrade FR 0004 destructif interdit ; restaurer une sauvegarde vérifiée")
