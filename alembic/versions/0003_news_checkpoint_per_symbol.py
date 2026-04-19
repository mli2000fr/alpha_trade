"""Store news ingestion checkpoints per symbol.

Revision ID: 0003_news_checkpoint_per_symbol
Revises: 0002_add_account_id
"""
# noinspection PyUnresolvedReferences
from alembic import op
import sqlalchemy as sa

revision = "0003_news_checkpoint_per_symbol"
down_revision = "0002_add_account_id"
branch_labels = None
depends_on = None

_TABLE = "news_ingestion_checkpoint"
_GLOBAL_SYMBOL = "__GLOBAL__"


def upgrade() -> None:
    op.add_column(_TABLE, sa.Column("symbol", sa.String(length=32), nullable=True))
    op.execute(f"UPDATE {_TABLE} SET symbol = '{_GLOBAL_SYMBOL}' WHERE symbol IS NULL")
    op.alter_column(_TABLE, "symbol", existing_type=sa.String(length=32), nullable=False)
    op.drop_constraint("PRIMARY", _TABLE, type_="primary")
    op.create_primary_key("pk_news_ingestion_checkpoint", _TABLE, ["source_name", "symbol"])
    op.create_index("idx_news_ingestion_checkpoint_symbol", _TABLE, ["symbol"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_news_ingestion_checkpoint_symbol", table_name=_TABLE)
    op.drop_constraint("pk_news_ingestion_checkpoint", _TABLE, type_="primary")
    op.execute(
        f"""
        DELETE nic1 FROM {_TABLE} nic1
        INNER JOIN {_TABLE} nic2
            ON nic1.source_name = nic2.source_name
           AND nic1.symbol <> nic2.symbol
           AND nic1.updated_at < nic2.updated_at
        """
    )
    op.execute(
        f"UPDATE {_TABLE} SET symbol = NULL WHERE symbol = '{_GLOBAL_SYMBOL}'"
    )
    op.create_primary_key("PRIMARY", _TABLE, ["source_name"])
    op.drop_column(_TABLE, "symbol")


