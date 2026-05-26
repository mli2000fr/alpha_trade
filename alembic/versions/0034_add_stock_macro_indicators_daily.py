"""Add daily macro indicators storage table.

Revision ID: 0034_add_stock_macro_indicators_daily
Revises: 0033_news_checkpoint_stage_timestamps
"""

# noinspection PyUnresolvedReferences
import sqlalchemy as sa

from alembic import op

revision = "0034_add_stock_macro_indicators_daily"
down_revision = "0033_news_checkpoint_stage_timestamps"
branch_labels = None
depends_on = None

_TABLE = "stock_macro_indicators_daily"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("vix", sa.Float(), nullable=True),
        sa.Column("vix9d", sa.Float(), nullable=True),
        sa.Column("ten_y", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("trade_date"),
    )
    op.create_index("idx_stock_macro_indicators_daily_vix", _TABLE, ["vix"])
    op.create_index("idx_stock_macro_indicators_daily_vix9d", _TABLE, ["vix9d"])
    op.create_index("idx_stock_macro_indicators_daily_ten_y", _TABLE, ["ten_y"])


def downgrade() -> None:
    op.drop_index("idx_stock_macro_indicators_daily_ten_y", table_name=_TABLE)
    op.drop_index("idx_stock_macro_indicators_daily_vix9d", table_name=_TABLE)
    op.drop_index("idx_stock_macro_indicators_daily_vix", table_name=_TABLE)
    op.drop_table(_TABLE)


