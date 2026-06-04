"""Drop equity_simulated column from stock_macro_indicators_daily (never populated).

Revision ID: 0035_drop_equity_simulated
Revises: 0034_add_stock_macro_indicators_daily
"""

import sqlalchemy as sa

import alembic.op as op

revision = "0035_drop_equity_simulated"
down_revision = "0034_add_stock_macro_indicators_daily"
branch_labels = None
depends_on = None

_TABLE = "stock_macro_indicators_daily"


def upgrade() -> None:
    op.drop_column(_TABLE, "equity_simulated")


def downgrade() -> None:
    op.add_column(_TABLE, sa.Column("equity_simulated", sa.Float(), nullable=True))

