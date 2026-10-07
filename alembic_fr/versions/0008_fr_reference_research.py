"""Références de recherche FR : identité, benchmark et secteurs.

Revision ID: 0008_fr_reference_research
Revises: 0007_fr_liquidity_research
"""

from pathlib import Path

from alembic import op

revision = "0008_fr_reference_research"
down_revision = "0007_fr_liquidity_research"
branch_labels = None
depends_on = None


def upgrade() -> None:
    actual = op.get_bind().exec_driver_sql("SELECT DATABASE()").scalar()
    if actual != "alpha_trade_fr":
        raise RuntimeError(f"Migration FR refusée sur {actual!r}")
    path = Path(__file__).resolve().parents[2] / "database/sql/fr/migration_fr_0008_reference_research.sql"
    for statement in path.read_text(encoding="utf-8").split(";\n"):
        if statement.strip():
            op.execute(statement)


def downgrade() -> None:
    raise RuntimeError("Downgrade FR 0008 destructif interdit ; restaurer une sauvegarde vérifiée")
