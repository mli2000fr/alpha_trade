"""Ajoute la persistance selector enrichie et l'explicabilité candidat.

Revision ID: 0029_selector_explainability_persistence
Revises: 0028_news_ticker_sentiment
"""
import sqlalchemy as sa

from alembic import op

revision = "0029_selector_explainability_persistence"
down_revision = "0028_news_ticker_sentiment"
branch_labels = None
depends_on = None


SELECTOR_EXPLAINABILITY_COLUMNS: tuple[tuple[str, sa.Column], ...] = (
    ("candidate_rank", sa.Column("candidate_rank", sa.Integer(), nullable=True)),
    ("raw_final_score", sa.Column("raw_final_score", sa.Float(), nullable=True)),
    ("normalized_total_score", sa.Column("normalized_total_score", sa.Float(), nullable=True)),
    ("normalized_rsi", sa.Column("normalized_rsi", sa.Float(), nullable=True)),
    ("total_score_neutralized", sa.Column("total_score_neutralized", sa.Float(), nullable=True)),
    (
        "relative_strength_index_neutralized",
        sa.Column("relative_strength_index_neutralized", sa.Float(), nullable=True),
    ),
    ("trend_vcp_component", sa.Column("trend_vcp_component", sa.Float(), nullable=True)),
    ("total_score_component", sa.Column("total_score_component", sa.Float(), nullable=True)),
    ("rsi_component", sa.Column("rsi_component", sa.Float(), nullable=True)),
    ("atr_pct_20", sa.Column("atr_pct_20", sa.Float(), nullable=True)),
    ("weekly_trend_score", sa.Column("weekly_trend_score", sa.Float(), nullable=True)),
    ("high_52w_proximity", sa.Column("high_52w_proximity", sa.Float(), nullable=True)),
    ("volatility_ratio", sa.Column("volatility_ratio", sa.Float(), nullable=True)),
    ("selector_signal_mode", sa.Column("selector_signal_mode", sa.String(length=32), nullable=True)),
    ("selection_explanation", sa.Column("selection_explanation", sa.String(length=255), nullable=True)),
)


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table)


def _has_column(bind, table: str, column: str) -> bool:
    inspector = sa.inspect(bind)
    if not inspector.has_table(table):
        return False
    return any(col["name"] == column for col in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    for table in ("stock_scores", "stock_scores_history"):
        if not _has_table(bind, table):
            continue
        for column_name, column in SELECTOR_EXPLAINABILITY_COLUMNS:
            if not _has_column(bind, table, column_name):
                op.add_column(table, column.copy())


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("stock_scores_history", "stock_scores"):
        if not _has_table(bind, table):
            continue
        for column_name, _ in reversed(SELECTOR_EXPLAINABILITY_COLUMNS):
            if _has_column(bind, table, column_name):
                op.drop_column(table, column_name)


