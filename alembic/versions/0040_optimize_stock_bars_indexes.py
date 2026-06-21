"""Optimisation des index pour les tables stock_bars et stock_bars_daily.

Ajoute :
- ``stock_bars_daily.idx_symbol`` pour les SELECT DISTINCT symbol.
- ``stock_bars_daily.idx_datasource_date`` pour le check homogénéité data_source.

Supprime :
- ``stock_bars.idx_stock_bars_symbol_timestamp`` (redondant avec la UNIQUE KEY).

Référence : analyse de performance sync_latest_quotes (2026-06-21).

Revision ID: 0040_optimize_stock_bars_indexes
Revises: 0039_add_model_metrics_ternary
"""
from alembic import op
import sqlalchemy as sa


revision = "0040_optimize_stock_bars_indexes"
down_revision = "0039_add_model_metrics_ternary"
branch_labels = None
depends_on = None


def _index_exists(bind, table: str, index: str) -> bool:
    """Vérifie si un index existe déjà sur une table."""
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(idx["name"] == index for idx in insp.get_indexes(table))


def upgrade() -> None:
    bind = op.get_bind()

    # ── stock_bars_daily : index pour SELECT DISTINCT symbol ──
    if bind.dialect.has_table(bind, "stock_bars_daily"):
        if not _index_exists(bind, "stock_bars_daily", "idx_symbol"):
            op.create_index("idx_symbol", "stock_bars_daily", ["symbol"])

        if not _index_exists(bind, "stock_bars_daily", "idx_datasource_date"):
            op.create_index(
                "idx_datasource_date", "stock_bars_daily", ["data_source", "date"]
            )

    # ── stock_bars : suppression index redondant ──
    if bind.dialect.has_table(bind, "stock_bars"):
        if _index_exists(bind, "stock_bars", "idx_stock_bars_symbol_timestamp"):
            op.drop_index("idx_stock_bars_symbol_timestamp", "stock_bars")


def downgrade() -> None:
    bind = op.get_bind()

    # ── Restauration stock_bars ──
    if bind.dialect.has_table(bind, "stock_bars"):
        if not _index_exists(bind, "stock_bars", "idx_stock_bars_symbol_timestamp"):
            op.create_index(
                "idx_stock_bars_symbol_timestamp", "stock_bars", ["symbol", "timestamp"]
            )

    # ── Suppression stock_bars_daily ──
    if bind.dialect.has_table(bind, "stock_bars_daily"):
        if _index_exists(bind, "stock_bars_daily", "idx_datasource_date"):
            op.drop_index("idx_datasource_date", "stock_bars_daily")

        if _index_exists(bind, "stock_bars_daily", "idx_symbol"):
            op.drop_index("idx_symbol", "stock_bars_daily")
