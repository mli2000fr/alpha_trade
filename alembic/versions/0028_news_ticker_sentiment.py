"""Sprint Niveau 4 — Table ``news_ticker_sentiment`` (FinBERT contextualisé).

Réf. ``prompt/sentiment/add_Finnhub_impl.md`` (Niveau 4 — re-scoring FinBERT
par couple ``(article, symbol)``). La table est **additive** : aucune
modification de ``news_sentiment`` (rétro-compat). Le consommateur downstream
applique ``COALESCE(nts.X, ns.X)`` dans ``load_feature_frames``.

* PK composite ``(article_id, symbol)`` ;
* FK ``article_id → news_raw`` (CASCADE) + FK composite
  ``(article_id, symbol) → news_ticker_map`` (CASCADE) ;
* ``scoring_version`` (defaut ``'contextual_v1'``) versionne le prompt
  contextuel pour invalider et re-scorer en cas d'évolution.

Revision ID: 0028_news_ticker_sentiment
Revises: 0027_news_ticker_map_relevance
"""
from alembic import op
import sqlalchemy as sa


revision = "0028_news_ticker_sentiment"
down_revision = "0027_news_ticker_map_relevance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "news_ticker_sentiment",
        sa.Column("article_id", sa.String(length=128), nullable=False),
        sa.Column("symbol", sa.String(length=100), nullable=False),
        sa.Column("model_name", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=50), nullable=False),
        sa.Column(
            "text_strategy",
            sa.Enum(
                "contextual_company",
                "contextual_symbol_only",
                "contextual_headline_only",
                name="nts_text_strategy",
            ),
            nullable=False,
        ),
        sa.Column("text_hash", sa.CHAR(length=64), nullable=False),
        sa.Column("truncated", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("max_length_tokens", sa.Integer(), nullable=False),
        sa.Column(
            "sentiment_label",
            sa.Enum("positive", "neutral", "negative", name="nts_sentiment_label"),
            nullable=False,
        ),
        sa.Column("positive_score", sa.Float(precision=53), nullable=False),
        sa.Column("neutral_score", sa.Float(precision=53), nullable=False),
        sa.Column("negative_score", sa.Float(precision=53), nullable=False),
        sa.Column("sentiment_confidence", sa.Float(precision=53), nullable=False),
        sa.Column("sentiment_net_score", sa.Float(precision=53), nullable=False),
        sa.Column(
            "inference_status",
            sa.Enum("success", "failed", name="nts_inference_status"),
            nullable=False,
            server_default="success",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("model_fingerprint", sa.String(length=32), nullable=True),
        sa.Column(
            "scoring_version",
            sa.String(length=30),
            nullable=False,
            server_default="contextual_v1",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("article_id", "symbol"),
        sa.ForeignKeyConstraint(
            ["article_id"], ["news_raw.article_id"], ondelete="CASCADE", name="fk_nts_article"
        ),
        sa.ForeignKeyConstraint(
            ["article_id", "symbol"],
            ["news_ticker_map.article_id", "news_ticker_map.symbol"],
            ondelete="CASCADE",
            name="fk_nts_ticker_map",
        ),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_index("idx_nts_symbol_label", "news_ticker_sentiment", ["symbol", "sentiment_label"])
    op.create_index("idx_nts_net", "news_ticker_sentiment", ["sentiment_net_score"])
    op.create_index("idx_nts_fingerprint", "news_ticker_sentiment", ["model_fingerprint"])
    op.create_index("idx_nts_scoring_version", "news_ticker_sentiment", ["scoring_version"])


def downgrade() -> None:
    op.drop_index("idx_nts_scoring_version", table_name="news_ticker_sentiment")
    op.drop_index("idx_nts_fingerprint", table_name="news_ticker_sentiment")
    op.drop_index("idx_nts_net", table_name="news_ticker_sentiment")
    op.drop_index("idx_nts_symbol_label", table_name="news_ticker_sentiment")
    op.drop_table("news_ticker_sentiment")

