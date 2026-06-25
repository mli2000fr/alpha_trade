"""Ajoute ``vxn``, ``vix3m``, ``move``, ``rvx`` à ``stock_macro_indicators_daily``.

Quatre nouveaux indicateurs de volatilité implicite :
- ``vxn``   : Nasdaq-100 Volatility Index (CBOE)
- ``vix3m`` : VIX 3-Month (term structure)
- ``move``  : ICE BofA Bond Volatility Index
- ``rvx``   : Russell 2000 Volatility Index (Small Caps)

Revision ID: 0043_add_vxn_vix3m_move_rvx
Revises: 0042_add_sma_to_history
"""
from alembic import op
import sqlalchemy as sa


revision = "0043_add_vxn_vix3m_move_rvx"
down_revision = "0042_add_sma_to_history"
branch_labels = None
depends_on = None

_NEW_COLUMNS = {
    "vxn": "Nasdaq-100 Volatility Index (CBOE VXN).",
    "vix3m": "VIX 3-Month (term structure, contango/backwardation).",
    "move": "ICE BofA Bond Volatility Index (MOVE).",
    "rvx": "Russell 2000 Volatility Index (CBOE RVX).",
}


def _has_column(bind, table: str, column: str) -> bool:
    insp = sa.inspect(bind)
    if not insp.has_table(table):
        return False
    return any(col["name"] == column for col in insp.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    table = "stock_macro_indicators_daily"
    if not bind.dialect.has_table(bind, table):
        return

    for col_name, comment in _NEW_COLUMNS.items():
        if not _has_column(bind, table, col_name):
            op.add_column(
                table,
                sa.Column(col_name, sa.Float(), nullable=True, comment=comment),
            )
        try:
            op.create_index(
                f"idx_stock_macro_indicators_daily_{col_name}",
                table,
                [col_name],
            )
        except Exception:
            pass  # l'index existe peut-être déjà


def downgrade() -> None:
    bind = op.get_bind()
    table = "stock_macro_indicators_daily"
    if not bind.dialect.has_table(bind, table):
        return

    for col_name in _NEW_COLUMNS:
        try:
            op.drop_index(
                f"idx_stock_macro_indicators_daily_{col_name}",
                table_name=table,
            )
        except Exception:
            pass
        if _has_column(bind, table, col_name):
            op.drop_column(table, col_name)
