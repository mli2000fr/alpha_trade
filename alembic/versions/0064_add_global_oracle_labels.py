"""Add global_oracle_labels table — Oracle Layer (Sprint S0).

Revision ID: 0064_add_global_oracle_labels
Revises: 0063_add_symbols_to_training_batch

Stores the historical Oracle labels (TARGET, never FEATURE) used to train the
Oracle TOP/BOTTOM models above the Global Model B25 (cf. doc/ml_oracle.md).

One row per (prediction_date, symbol, batch_id, horizon). The column
``oracle_available_date`` is the anti-leakage guard: a label is usable for
training/prediction only once its observation horizon has fully realized
(oracle_exit_date + 1 trading day).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0064_add_global_oracle_labels"
down_revision: Union[str, None] = "0063_add_symbols_to_training_batch"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("global_oracle_labels", schema="alpha_trade"):
        return

    op.create_table(
        "global_oracle_labels",
        sa.Column("prediction_date", sa.Date(), nullable=False,
                  comment="Date D de la prédiction du Global Model"),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("batch_id", sa.String(64), nullable=False,
                  comment="Batch du Global Model (B25)"),
        sa.Column("horizon", sa.Integer(), nullable=False,
                  comment="H20=20 (horizon canonique de la 1ʳᵉ expérience)"),
        sa.Column("future_return", sa.Double(), nullable=True,
                  comment="Rendement futur réalisé adj_close[D+H]/adj_close[D]-1 (target brut)"),
        sa.Column("oracle_pct_rank", sa.Double(), nullable=True,
                  comment="Percentile cross-sectionnel intra-date [0,1]"),
        sa.Column("oracle_decile", sa.SmallInteger(), nullable=True,
                  comment="Décile 1..10 (10 = meilleur rendement futur)"),
        sa.Column("oracle_top10", sa.Boolean(), nullable=True,
                  comment="1 si le titre est dans le TOP 10% cross-sectionnel du jour"),
        sa.Column("oracle_bottom10", sa.Boolean(), nullable=True,
                  comment="1 si le titre est dans le BOTTOM 10% cross-sectionnel du jour"),
        sa.Column("oracle_exit_date", sa.Date(), nullable=True,
                  comment="D + horizon"),
        sa.Column("oracle_available_date", sa.Date(), nullable=True,
                  comment="oracle_exit_date + 1 jour ouvrés — garde anti-leakage"),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("prediction_date", "symbol", "batch_id", "horizon"),
        sa.Index("idx_gol_batch_date", "batch_id", "prediction_date"),
        sa.Index("idx_gol_available_date", "oracle_available_date"),
        schema="alpha_trade",
    )


def downgrade() -> None:
    op.drop_table("global_oracle_labels", schema="alpha_trade")
