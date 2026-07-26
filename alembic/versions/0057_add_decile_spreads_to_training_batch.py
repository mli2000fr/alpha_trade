"""Add decile_spread_h3/h5/h10 to model_training_batch

Revision ID: 0057
Revises: 0056
Create Date: 2026-07-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0057"
down_revision: Union[str, None] = "0056"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_training_batch",
        sa.Column("decile_spread_h3", sa.Double(), nullable=True,
                  comment="Decile Spread H3 : rendement Top 10% − Bottom 10%"),
        schema="alpha_trade",
    )
    op.add_column(
        "model_training_batch",
        sa.Column("decile_spread_h5", sa.Double(), nullable=True),
        schema="alpha_trade",
    )
    op.add_column(
        "model_training_batch",
        sa.Column("decile_spread_h10", sa.Double(), nullable=True),
        schema="alpha_trade",
    )


def downgrade() -> None:
    op.drop_column("model_training_batch", "decile_spread_h3", schema="alpha_trade")
    op.drop_column("model_training_batch", "decile_spread_h5", schema="alpha_trade")
    op.drop_column("model_training_batch", "decile_spread_h10", schema="alpha_trade")
