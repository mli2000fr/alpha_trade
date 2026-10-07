"""Versionner la classification des barres staging FR.

Revision ID: 0005_fr_staging_quality_version
Revises: 0004_fr_provider_staging
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0005_fr_staging_quality_version"
down_revision = "0004_fr_provider_staging"
branch_labels = None
depends_on = None


def upgrade() -> None:
    actual = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if actual != "alpha_trade_fr":
        raise RuntimeError(f"Migration FR refusée sur {actual!r}")
    sql_path = (Path(__file__).resolve().parents[2] / "database" / "sql" / "fr"
                / "migration_fr_0005_staging_quality_version.sql")
    for statement in sql_path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Downgrade FR 0005 destructif interdit ; restaurer une sauvegarde vérifiée")
