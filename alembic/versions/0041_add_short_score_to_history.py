"""Ajoute ``short_score`` à ``stock_scores_history``.

Permet de persister le score baissier dédié (RSI, SMA, trend) dans l'historique
pour le walk-forward long+short.

Revision ID: 0041_add_short_score_to_history
Revises: 0040_optimize_stock_bars_indexes
"""
from alembic import op
import sqlalchemy as sa


revision = "0041_add_short_score_to_history"
down_revision = "0040_optimize_stock_bars_indexes"
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

    if not _has_column(bind, "stock_scores_history", "short_score"):
        op.add_column(
            "stock_scores_history",
            sa.Column(
                "short_score",
                sa.Float(),
                nullable=True,
                comment="Score baissier dédié (0-1). Null = pas encore backfillé. "
                        "Basé sur trend_score, RSI, SMA50, SMA200.",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    if not bind.dialect.has_table(bind, "stock_scores_history"):
        return

    if _has_column(bind, "stock_scores_history", "short_score"):
        op.drop_column("stock_scores_history", "short_score")
