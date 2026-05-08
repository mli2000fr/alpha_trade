"""Sprint relevance scoring — colonnes ``relevance_score`` / ``relevance_components`` sur ``news_ticker_map``.

Réf. ``prompt/sentiment/add_Finnhub_impl.md`` (Niveau 2 & 3 — pertinence
article→symbole). Ajoute :

* ``relevance_score FLOAT NULL`` : pertinence calculée par
  :mod:`event_sentiment.relevance` lorsque le mode est ``"scored"``. NULL
  pour les autres modes / les lignes historiques (rétro-compat). Le
  consommateur downstream applique ``COALESCE(relevance_score, 1.0)``.
* ``relevance_components JSON NULL`` : audit trail des composantes
  (``name_in_headline``, ``ticker_in_text``, ``primary_bonus``,
  ``multi_ticker_penalty``, ``relevance_version``).
* index ``idx_news_ticker_map_relevance`` : utile pour filtrer en aval
  par seuil de pertinence.

Migration NULL-able pour ne PAS imposer de backfill rétroactif.

Revision ID: 0027_news_ticker_map_relevance
Revises: 0026_champion_history
"""
from alembic import op
import sqlalchemy as sa


revision = "0027_news_ticker_map_relevance"
down_revision = "0026_champion_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "news_ticker_map",
        sa.Column(
            "relevance_score",
            sa.Float(),
            nullable=True,
            comment="Score [0,1] de pertinence article->symbole (mode 'scored').",
        ),
    )
    op.add_column(
        "news_ticker_map",
        sa.Column(
            "relevance_components",
            sa.JSON(),
            nullable=True,
            comment="Audit trail des composantes du score.",
        ),
    )
    op.create_index(
        "idx_news_ticker_map_relevance",
        "news_ticker_map",
        ["relevance_score"],
    )


def downgrade() -> None:
    op.drop_index("idx_news_ticker_map_relevance", table_name="news_ticker_map")
    op.drop_column("news_ticker_map", "relevance_components")
    op.drop_column("news_ticker_map", "relevance_score")

