"""Add ic_rank column to model_training_batch for Global Ranking Model metric.

Revision ID: 0056_add_ic_rank_to_training_batch
Revises: 0055_add_stock_fundamentals_daily
Create Date: 2026-07-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0056_add_ic_rank_to_training_batch"
down_revision: Union[str, None] = "0055_add_stock_fundamentals_daily"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_training_batch",
        sa.Column(
            "ic_rank",
            sa.DOUBLE(),
            nullable=True,
            comment="IC Rank (Spearman) moyen du Global Ranking Model sur le walk-forward",
        ),
        schema="alpha_trade",
    )


def downgrade() -> None:
    op.drop_column("model_training_batch", "ic_rank", schema="alpha_trade")
