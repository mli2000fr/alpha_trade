"""Preserve fractional FINRA CNMS share volume without rounding.

Revision ID: 0083_finra_fractional_short_volume
Revises: 0082_sec_filing_documents
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0083_finra_fractional_short_volume"
down_revision: str | None = "0082_sec_filing_documents"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    for column in ("short_volume", "short_exempt_volume", "total_volume"):
        op.alter_column(
            "stock_short_volume_daily", column,
            existing_type=sa.BigInteger(),
            type_=sa.Numeric(24, 6),
            existing_nullable=False,
            schema="alpha_trade",
        )


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade would discard fractional FINRA share volumes."
    )
