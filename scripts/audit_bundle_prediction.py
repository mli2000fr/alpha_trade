"""Audit en lecture seule de la couverture d'une prédiction bundle ML."""
from __future__ import annotations

import argparse
import json

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

QUERIES = {
    "schema": """
        SELECT
            (SELECT version_num FROM alembic_version LIMIT 1) AS alembic_revision,
            (SELECT CHARACTER_MAXIMUM_LENGTH
             FROM information_schema.COLUMNS
             WHERE TABLE_SCHEMA = 'alpha_trade'
               AND TABLE_NAME = 'model_predictions'
               AND COLUMN_NAME = 'calibration_method') AS calibration_method_length
    """,
    "batch": """
        SELECT batch_id, status, started_at, finished_at, symbol_source,
               requested_symbol_count, symbols_completed, symbols_failed,
               symbols_skipped,
               training_start_date, training_end_date, failure_reason
        FROM model_training_batch WHERE batch_id = :batch_id
    """,
    "directional": """
        SELECT COUNT(*) AS rows_n, COUNT(DISTINCT mp.symbol) AS symbols,
               COUNT(DISTINCT mp.prediction_date) AS dates_n,
               MIN(mp.prediction_date) AS min_date, MAX(mp.prediction_date) AS max_date,
               SUM(mp.direction_long_run_id IS NOT NULL) AS long_rows,
               SUM(mp.direction_short_run_id IS NOT NULL) AS short_rows,
               SUM(mp.direction_long_run_id IS NOT NULL
                   AND mp.direction_short_run_id IS NOT NULL) AS paired_rows,
               SUM(mp.proba_long IS NULL) AS null_long,
               SUM(mp.proba_short IS NULL) AS null_short,
               SUM(mp.proba_flat IS NULL) AS null_flat
        FROM model_predictions AS mp
        JOIN model_training_run AS mtr ON mtr.run_id = mp.run_id
        WHERE mtr.batch_id = :batch_id AND mp.model_role = 'directional_bundle'
    """,
    "directional_raw": """
        SELECT COUNT(*) AS rows_n, COUNT(DISTINCT symbol) AS symbols,
               COUNT(DISTINCT prediction_date) AS dates_n,
               MIN(prediction_date) AS min_date, MAX(prediction_date) AS max_date,
               SUM(direction_long_run_id IS NOT NULL) AS long_rows,
               SUM(direction_short_run_id IS NOT NULL) AS short_rows,
               SUM(direction_long_run_id IS NOT NULL
                   AND direction_short_run_id IS NOT NULL) AS paired_rows
        FROM model_predictions
        WHERE model_role = 'directional_bundle'
          AND (run_id LIKE CONCAT(:batch_id, '%')
               OR direction_long_run_id LIKE CONCAT(:batch_id, '%')
               OR direction_short_run_id LIKE CONCAT(:batch_id, '%'))
    """,
    "training_roles": """
        SELECT COALESCE(model_role, 'NULL') AS model_role,
               COALESCE(status, 'NULL') AS status,
               COUNT(*) AS runs_n, COUNT(DISTINCT symbol) AS symbols
        FROM model_training_run
        WHERE batch_id = :batch_id
        GROUP BY model_role, status
        ORDER BY model_role, status
    """,
    "by_source": """
        SELECT COALESCE(mp.source, 'NULL') AS source,
               COALESCE(mp.model_role, 'NULL') AS model_role,
               COUNT(*) AS rows_n, COUNT(DISTINCT mp.symbol) AS symbols,
               COUNT(DISTINCT mp.prediction_date) AS dates_n,
               MIN(mp.prediction_date) AS min_date, MAX(mp.prediction_date) AS max_date
        FROM model_predictions AS mp
        JOIN model_training_run AS mtr ON mtr.run_id = mp.run_id
        WHERE mtr.batch_id = :batch_id
        GROUP BY mp.source, mp.model_role ORDER BY rows_n DESC
    """,
    "oracle": """
        SELECT COUNT(*) AS rows_n, COUNT(DISTINCT symbol) AS symbols,
               COUNT(DISTINCT prediction_date) AS dates_n,
               MIN(prediction_date) AS min_date, MAX(prediction_date) AS max_date,
               SUM(oracle_extreme10 IS NULL) AS labels_null,
               SUM(future_return IS NULL) AS returns_null,
               MIN(proba_extreme) AS p_min, AVG(proba_extreme) AS p_avg,
               MAX(proba_extreme) AS p_max
        FROM oracle_extreme_predictions WHERE batch_id = :batch_id
    """,
    "sides": """
        SELECT COALESCE(mp.predicted_side, 'NULL') AS side, COUNT(*) AS rows_n,
               AVG(mp.proba_long) AS avg_long, AVG(mp.proba_short) AS avg_short,
               AVG(ABS(mp.proba_long - mp.proba_short)) AS avg_margin
        FROM model_predictions AS mp
        JOIN model_training_run AS mtr ON mtr.run_id = mp.run_id
        WHERE mtr.batch_id = :batch_id AND mp.model_role = 'directional_bundle'
        GROUP BY mp.predicted_side ORDER BY rows_n DESC
    """,
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("batch_id")
    parser.add_argument("--section", choices=sorted(QUERIES))
    args = parser.parse_args()
    engine = get_sqlalchemy_engine()
    result: dict[str, list[dict[str, object]]] = {}
    with engine.connect() as connection:
        selected = ({args.section: QUERIES[args.section]} if args.section else QUERIES)
        for name, query in selected.items():
            rows = connection.execute(text(query), {"batch_id": args.batch_id})
            result[name] = [dict(row._mapping) for row in rows]
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
