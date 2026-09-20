"""Enforce US fact instrument references and legacy double-write guards.

Revision ID: 0088_us_fact_instrument_constraints
Revises: 0087_us_fact_instrument_columns
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0088_us_fact_instrument_constraints"
down_revision: str | None = "0087_us_fact_instrument_columns"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

TABLE_DATES = {
    "stock_metadata": None,
    "stock_bars_daily": "date",
    "stock_bars": "timestamp",
    "stock_quote_snapshots": "quote_date",
    "stock_scores": None,
    "stock_scores_history": "snapshot_date",
    "tradable_universe_history": None,
    "model_predictions": "prediction_date",
    "global_rank_history": "date",
    "global_oracle_labels": "prediction_date",
    "oracle_extreme_predictions": "prediction_date",
    "model_registry": None,
    "model_metrics": None,
    "model_metrics_full": None,
    "model_batch_diagnostics": None,
    "model_directional_oos_metrics": None,
    "champion_history": None,
    "model_governance": None,
    "stock_fundamentals_daily": "trade_date",
    "stock_earnings_calendar": "earnings_date",
    "stock_analyst_consensus_snapshots": "observed_at",
    "stock_analyst_eps_revision_history": "snapshot_date",
    "stock_analyst_eps_trend_history": "snapshot_date",
    "stock_analyst_estimate_history": "snapshot_date",
    "stock_analyst_recommendation_history": "snapshot_date",
    "stock_analyst_target_history": "snapshot_date",
    "ticker_daily_sentiment_features": "trade_date",
    "news_ticker_sentiment": None,
    "corporate_action_source_events": None,
    "corporate_actions_events": "ex_date",
    "corporate_actions_applications": None,
    "sec_filing_raw": "filing_date",
    "sec_corporate_events": "filing_date",
}
CRITICAL_SYMBOL_SQL = (
    "UPPER(TRIM(t.symbol)) REGEXP '^[A-Z0-9][A-Z0-9.\\-]{0,31}$' "
    "AND UPPER(TRIM(t.symbol)) NOT LIKE '\\_\\_%'"
)


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _trigger_sql(table: str, timing: str) -> str:
    trigger = f"trg_iid_{table}_{'bi' if timing == 'INSERT' else 'bu'}"
    identity_scope_clause = (
        "(LOWER(COALESCE(NEW.asset_class,'')) <> 'crypto')"
        if table == "stock_metadata"
        else """(
          EXISTS (
            SELECT 1 FROM stock_metadata sm
            WHERE CONVERT(sm.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(NEW.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
              AND (sm.asset_class IS NULL OR LOWER(sm.asset_class) <> 'crypto')
          )
          OR EXISTS (
            SELECT 1 FROM instruments known_i
            WHERE known_i.market_code='US_EQ'
              AND known_i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          )
        )"""
    )
    identity_required = (
        "UPPER(TRIM(COALESCE(NEW.symbol,''))) REGEXP '^[A-Z0-9][A-Z0-9.\\-]{0,31}$' "
        "AND UPPER(TRIM(COALESCE(NEW.symbol,''))) NOT LIKE '\\_\\_%'"
    )
    return f"""
    CREATE TRIGGER {trigger} BEFORE {timing} ON `{table}` FOR EACH ROW
    BEGIN
      IF NEW.instrument_id IS NULL AND NEW.symbol IS NOT NULL THEN
        IF (
          SELECT COUNT(*) FROM instruments i
          WHERE i.market_code='US_EQ'
            AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
        ) > 1 THEN
          SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='ambiguous legacy US instrument identity';
        END IF;
        SET NEW.instrument_id=(
          SELECT i.instrument_id FROM instruments i
          WHERE i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
          ORDER BY (i.mapping_status='mapped') DESC, i.instrument_id LIMIT 1
        );
      END IF;
      IF NEW.instrument_id IS NULL AND ({identity_required}) AND {identity_scope_clause} THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='unresolved US instrument identity';
      END IF;
      IF NEW.instrument_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM instruments i WHERE i.instrument_id=NEW.instrument_id
          AND i.market_code='US_EQ' AND i.local_symbol=CONVERT(UPPER(TRIM(NEW.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
      ) THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='symbol/instrument identity mismatch';
      END IF;
    END
    """


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_tables()
    trigger_capable = bind.dialect.name in {"mysql", "mariadb"}
    for table, date_column in TABLE_DATES.items():
        if table not in existing:
            continue
        # Fermer d'abord la fenêtre de concurrence : dès ce point, tout ancien
        # producteur qui n'écrit que symbol obtient aussi instrument_id.
        if trigger_capable:
            for suffix, timing in (("bi", "INSERT"), ("bu", "UPDATE")):
                op.execute(f"DROP TRIGGER IF EXISTS trg_iid_{table}_{suffix}")
                op.execute(_trigger_sql(table, timing))
        inspector = sa.inspect(bind)
        index_name = f"ix_iid_{table}"[:64]
        fk_name = f"fk_iid_{table}"[:64]
        existing_indexes = {item["name"] for item in inspector.get_indexes(table)}
        existing_fks = {item.get("name") for item in inspector.get_foreign_keys(table)}
        if index_name in existing_indexes and fk_name in existing_fks:
            continue
        missing = bind.execute(
            sa.text(f"""
            SELECT 1 FROM `{table}` t LEFT JOIN stock_metadata m ON CONVERT(m.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(t.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
            WHERE t.instrument_id IS NULL
              AND ({CRITICAL_SYMBOL_SQL})
              AND m.symbol IS NOT NULL
              AND (m.asset_class IS NULL OR m.asset_class <> 'crypto')
            LIMIT 1
        """)
        ).scalar()
        mismatch = bind.execute(
            sa.text(f"""
            SELECT 1 FROM `{table}` t JOIN instruments i ON i.instrument_id=t.instrument_id
            WHERE i.market_code<>'US_EQ' OR i.local_symbol<>CONVERT(UPPER(TRIM(t.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
            LIMIT 1
        """)
        ).scalar()
        if missing or mismatch:
            raise RuntimeError(f"{table}: instrument backfill incomplete missing={bool(missing)} mismatch={bool(mismatch)}")
        table_columns = {item["name"] for item in inspector.get_columns(table)}
        columns = ["instrument_id"] + ([date_column] if date_column in table_columns else [])
        if index_name not in existing_indexes:
            op.create_index(index_name, table, columns)
        if fk_name not in existing_fks:
            op.create_foreign_key(
                fk_name,
                table,
                "instruments",
                ["instrument_id"],
                ["instrument_id"],
                ondelete="RESTRICT",
            )


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_tables()
    if bind.dialect.name in {"mysql", "mariadb"}:
        for table in TABLE_DATES:
            for suffix in ("bi", "bu"):
                op.execute(f"DROP TRIGGER IF EXISTS trg_iid_{table}_{suffix}")
    for table in reversed(tuple(TABLE_DATES)):
        if table not in existing:
            continue
        op.drop_constraint(f"fk_iid_{table}"[:64], table, type_="foreignkey")
        op.drop_index(f"ix_iid_{table}"[:64], table_name=table)
