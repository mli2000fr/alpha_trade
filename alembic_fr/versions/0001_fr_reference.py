"""Socle FR_EQ : instruments, symboles, statuts, séances et runs.

Revision ID: 0001_fr_reference
Revises: None
"""
from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0001_fr_reference"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    actual = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if actual != "alpha_trade_fr":
        raise RuntimeError(f"Migration FR refusée sur {actual!r}")
    sql_path = (Path(__file__).resolve().parents[2] / "database" / "sql" / "fr"
                / "migration_fr_0001_reference.sql")
    for statement in sql_path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Downgrade FR 0001 destructif interdit ; restaurer une sauvegarde vérifiée")
