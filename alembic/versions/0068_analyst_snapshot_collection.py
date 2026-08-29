"""Add analyst snapshot collection tables (RESEARCH ONLY).

Revision ID: 0068_analyst_snapshot_collection
Revises: 0067_add_model_predictions_source

Collecte PROSPECTIVE d'analyst data Yahoo (EPS/revenue estimates, price targets,
recommendations) — RESEARCH ONLY, aucune intégration PROD (ni Global Rank, ni
Oracle, ni cascade, ni live, ni backtesting PROD).

Principe PIT : chaque ligne est un SNAPSHOT observé à un instant réel
(``observed_at``) et utilisable uniquement à partir de ``available_at``
(prochaine séance de décision après l'observation). Contrat :
``available_at <= decision_cutoff`` pour être utilisable.

Tables :
- ``stock_analyst_estimate_history``      : 1 ligne = (symbole, type EPS/REVENUE,
  horizon, snapshot du jour). Append-only. UNIQUE (provider, symbol,
  snapshot_date, estimate_type, horizon_normalized) → 1 snapshot/jour/horizon.
- ``stock_analyst_target_history``        : 1 ligne = (symbole, snapshot du jour).
  UNIQUE (provider, symbol, snapshot_date).
- ``stock_analyst_recommendation_history``: 1 ligne par period_raw (0m/-1m/-2m/…)
  par symbole/jour. UNIQUE (provider, symbol, snapshot_date, period_raw).
- ``analyst_snapshot_collection_run``     : trace de chaque run de collecte.

``raw_payload_json`` + ``raw_hash`` conservés dans MySQL (aucun stockage fichier).
Idempotence : les UNIQUE + insertion "si absente" ⇒ relancer un run ne crée
jamais de doublon. Append-only : une nouvelle observation = une nouvelle ligne
(interdiction d'UPDATE une ancienne valeur).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT


revision: str = "0068_analyst_snapshot_collection"
down_revision: Union[str, None] = "0067_add_model_predictions_source"
branch_labels: Union[Sequence[str], None] = None
depends_on: Union[Sequence[str], None] = None

_SCHEMA = "alpha_trade"


def _has_table(bind, table: str) -> bool:
    return sa.inspect(bind).has_table(table, schema=_SCHEMA)


def _create_estimate_history(op_) -> None:
    op_.create_table(
        "stock_analyst_estimate_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False,
                  comment="Date NY de l'observation (date de collecte)"),
        sa.Column("observed_at", sa.DateTime(), nullable=False,
                  comment="Moment réel où le collecteur a observé Yahoo (UTC)"),
        sa.Column("available_at", sa.DateTime(), nullable=False,
                  comment="Prochaine séance de décision après observation (UTC)"),
        sa.Column("ingestion_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("estimate_type", sa.String(16), nullable=False,
                  comment="EPS | REVENUE"),
        sa.Column("horizon_raw", sa.String(8), nullable=False,
                  comment="0q | +1q | 0y | +1y (horizon Yahoo)"),
        sa.Column("horizon_normalized", sa.String(24), nullable=False,
                  comment="CURRENT_QUARTER | NEXT_QUARTER | CURRENT_YEAR | NEXT_YEAR"),
        sa.Column("fiscal_period_end", sa.Date(), nullable=True,
                  comment="NULL : Yahoo ne fournit pas l'identité fiscale"),
        sa.Column("fiscal_year", sa.SmallInteger(), nullable=True),
        sa.Column("fiscal_quarter", sa.SmallInteger(), nullable=True),
        sa.Column("relative_horizon_only", sa.Boolean(), nullable=False,
                  server_default=sa.text("1"),
                  comment="True si l'horizon est relatif sans identité fiscale"),
        sa.Column("avg_value", sa.Double(), nullable=True),
        sa.Column("low_value", sa.Double(), nullable=True),
        sa.Column("high_value", sa.Double(), nullable=True),
        sa.Column("analyst_count", sa.Integer(), nullable=True),
        sa.Column("growth_value", sa.Double(), nullable=True),
        sa.Column("raw_payload_json", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
        sa.Column("raw_hash", sa.String(64), nullable=True),
        sa.Column("provider_schema_version", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "symbol", "snapshot_date", "estimate_type",
                            "horizon_normalized",
                            name="uq_est_provider_symbol_date_type_horizon"),
        sa.Index("idx_est_symbol_date", "symbol", "snapshot_date"),
        sa.Index("idx_est_observed_at", "observed_at"),
        sa.Index("idx_est_available_at", "available_at"),
        sa.Index("idx_est_type_horizon", "estimate_type", "horizon_normalized"),
        schema=_SCHEMA,
        mysql_charset="utf8mb4",
    )


def _create_target_history(op_) -> None:
    op_.create_table(
        "stock_analyst_target_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("ingestion_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("current_price", sa.Double(), nullable=True),
        sa.Column("target_low", sa.Double(), nullable=True),
        sa.Column("target_mean", sa.Double(), nullable=True),
        sa.Column("target_median", sa.Double(), nullable=True),
        sa.Column("target_high", sa.Double(), nullable=True),
        sa.Column("analyst_count", sa.Integer(), nullable=True,
                  comment="NULL : Yahoo n'expose pas le nb d'analystes pour les targets"),
        sa.Column("raw_payload_json", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
        sa.Column("raw_hash", sa.String(64), nullable=True),
        sa.Column("provider_schema_version", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "symbol", "snapshot_date",
                            name="uq_tgt_provider_symbol_date"),
        sa.Index("idx_tgt_symbol_date", "symbol", "snapshot_date"),
        sa.Index("idx_tgt_observed_at", "observed_at"),
        sa.Index("idx_tgt_available_at", "available_at"),
        schema=_SCHEMA,
        mysql_charset="utf8mb4",
    )


def _create_recommendation_history(op_) -> None:
    op_.create_table(
        "stock_analyst_recommendation_history",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("ingestion_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("period_raw", sa.String(8), nullable=False,
                  comment="0m | -1m | -2m | -3m (bucket fourni par Yahoo)"),
        sa.Column("strong_buy", sa.Integer(), nullable=True),
        sa.Column("buy", sa.Integer(), nullable=True),
        sa.Column("hold", sa.Integer(), nullable=True),
        sa.Column("sell", sa.Integer(), nullable=True),
        sa.Column("strong_sell", sa.Integer(), nullable=True),
        sa.Column("raw_payload_json", sa.Text().with_variant(LONGTEXT(), "mysql"), nullable=True),
        sa.Column("raw_hash", sa.String(64), nullable=True),
        sa.Column("provider_schema_version", sa.String(16), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider", "symbol", "snapshot_date", "period_raw",
                            name="uq_rec_provider_symbol_date_period"),
        sa.Index("idx_rec_symbol_date", "symbol", "snapshot_date"),
        sa.Index("idx_rec_observed_at", "observed_at"),
        sa.Index("idx_rec_available_at", "available_at"),
        schema=_SCHEMA,
        mysql_charset="utf8mb4",
    )


def _create_collection_run(op_) -> None:
    op_.create_table(
        "analyst_snapshot_collection_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(16), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("requested_symbols", sa.Integer(), nullable=True),
        sa.Column("successful_symbols", sa.Integer(), nullable=True),
        sa.Column("empty_symbols", sa.Integer(), nullable=True),
        sa.Column("failed_symbols", sa.Integer(), nullable=True),
        sa.Column("estimates_rows_inserted", sa.Integer(), nullable=True),
        sa.Column("targets_rows_inserted", sa.Integer(), nullable=True),
        sa.Column("recommendations_rows_inserted", sa.Integer(), nullable=True),
        sa.Column("rate_limit_count", sa.Integer(), nullable=True),
        sa.Column("temporary_error_count", sa.Integer(), nullable=True),
        sa.Column("schema_error_count", sa.Integer(), nullable=True),
        sa.Column("parse_error_count", sa.Integer(), nullable=True),
        sa.Column("eps_coverage", sa.Double(), nullable=True),
        sa.Column("revenue_coverage", sa.Double(), nullable=True),
        sa.Column("target_coverage", sa.Double(), nullable=True),
        sa.Column("recommendation_coverage", sa.Double(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False,
                  server_default=sa.text("'RUNNING'"),
                  comment="RUNNING | COMPLETED | FAILED"),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", name="uq_run_run_id"),
        sa.Index("idx_run_started_at", "started_at"),
        schema=_SCHEMA,
        mysql_charset="utf8mb4",
    )


def upgrade() -> None:
    bind = op.get_bind()
    if not _has_table(bind, "stock_analyst_estimate_history"):
        _create_estimate_history(op)
    if not _has_table(bind, "stock_analyst_target_history"):
        _create_target_history(op)
    if not _has_table(bind, "stock_analyst_recommendation_history"):
        _create_recommendation_history(op)
    if not _has_table(bind, "analyst_snapshot_collection_run"):
        _create_collection_run(op)


def downgrade() -> None:
    for table in ("stock_analyst_estimate_history", "stock_analyst_target_history",
                  "stock_analyst_recommendation_history", "analyst_snapshot_collection_run"):
        op.drop_table(table, schema=_SCHEMA)
