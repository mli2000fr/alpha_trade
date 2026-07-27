"""Add stacking_enabled column to model_training_batch.

Revision ID: 0059
Revises: 0058
Create Date: 2026-07-27

Tracks whether the Global Ranking model was injected as a feature
(``global_rank_3`` / ``global_rank_5``) into per-symbol models during
training.  Controlled by the IHM checkbox "📥 Stacking".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0059"
down_revision: Union[str, None] = "0058"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "model_training_batch",
        sa.Column(
            "stacking_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Global Rank stacking injecté comme feature per-symbol (checkbox IHM)",
        ),
        schema="alpha_trade",
    )


def downgrade() -> None:
    op.drop_column("model_training_batch", "stacking_enabled", schema="alpha_trade")
