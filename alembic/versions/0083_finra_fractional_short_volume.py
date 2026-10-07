"""Preserve FINRA fractional-share daily short volumes.

Revision ID: 0083_finra_fractional_short_volume
Revises: 0082_sec_filing_documents
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0083_finra_fractional_short_volume"
down_revision: str | None = "0082_sec_filing_documents"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

COLUMNS = ("short_volume", "short_exempt_volume", "total_volume")


def upgrade() -> None:
    for column in COLUMNS:
        op.alter_column(
            "stock_short_volume_daily", column,
            existing_type=sa.BigInteger(),
            type_=sa.Numeric(24, 6),
            existing_nullable=False,
            schema="alpha_trade",
        )


def downgrade() -> None:
    connection = op.get_bind()
    fractional = connection.execute(sa.text("""
        SELECT COUNT(*) FROM alpha_trade.stock_short_volume_daily
        WHERE short_volume <> TRUNCATE(short_volume, 0)
           OR short_exempt_volume <> TRUNCATE(short_exempt_volume, 0)
           OR total_volume <> TRUNCATE(total_volume, 0)
    """)).scalar_one()
    if fractional:
        raise RuntimeError("Export or remove fractional FINRA volumes before downgrading")
    for column in COLUMNS:
        op.alter_column(
            "stock_short_volume_daily", column,
            existing_type=sa.Numeric(24, 6),
            type_=sa.BigInteger(),
            existing_nullable=False,
            schema="alpha_trade",
        )
