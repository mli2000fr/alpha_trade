"""Phase 4.1.c — versionnement FinBERT.

Réf. ``prompt/refactor/plan.md`` Phase 4.1 + ``audit_event_sentiment.md``.

Ajoute la colonne ``model_fingerprint VARCHAR(32) NULL`` à ``news_sentiment``
pour persister un hash stable du checkpoint FinBERT (model_name + revision +
config) consommé pour produire chaque enregistrement.

NULL-able afin de préserver les lignes historiques (backfill séparé).

Revision ID: 0015_finbert_model_fingerprint
Revises: 0014_cleaning_audit_quotes_earnings_runs
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_finbert_model_fingerprint"
down_revision = "0014_cleaning_audit_quotes_earnings_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_sentiment",
        sa.Column(
            "model_fingerprint",
            sa.String(length=32),
            nullable=True,
            comment="SHA256[:16] de model_name + revision + config FinBERT",
        ),
    )
    op.create_index(
        "idx_news_sentiment_model_fingerprint",
        "news_sentiment",
        ["model_fingerprint"],
    )


def downgrade() -> None:
    op.drop_index("idx_news_sentiment_model_fingerprint", table_name="news_sentiment")
    op.drop_column("news_sentiment", "model_fingerprint")

