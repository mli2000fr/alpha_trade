"""Ajoute ``sma_50`` et ``sma_200`` à ``stock_scores_history``.

Permet le calcul complet du ``short_score`` (4 facteurs) et sa calibration
walk-forward.

Revision ID: 0042_add_sma_to_history
Revises: 0041_add_short_score_to_history
"""
from alembic import op
import sqlalchemy as sa


revision = "0042_add_sma_to_history"
down_revision = "0041_add_short_score_to_history"
branch_labels = None
depends_on = None


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "stock_scores_history"):
        return

    if not _has_column(bind, "stock_scores_history", "sma_50"):
        op.add_column(
            "stock_scores_history",
            sa.Column(
                "sma_50",
                sa.Float(),
                nullable=True,
                comment="Moyenne mobile 50 jours (prix de clôture ajusté).",
            ),
        )

    if not _has_column(bind, "stock_scores_history", "sma_200"):
        op.add_column(
            "stock_scores_history",
            sa.Column(
                "sma_200",
                sa.Float(),
                nullable=True,
                comment="Moyenne mobile 200 jours (prix de clôture ajusté).",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "stock_scores_history"):
        return

    if _has_column(bind, "stock_scores_history", "sma_200"):
        op.drop_column("stock_scores_history", "sma_200")
    if _has_column(bind, "stock_scores_history", "sma_50"):
        op.drop_column("stock_scores_history", "sma_50")
