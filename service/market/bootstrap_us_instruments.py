"""Bootstrap et backfill reprenable des identités instrument US (Sprint 5)."""

from __future__ import annotations

import argparse
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from database.connection import get_sqlalchemy_engine
from database.repositories.instruments import build_instrument_uid

LOGGER = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATE = ROOT / "artifacts" / "audits" / "market_integration" / "sprint_05" / "backfill_state.json"
FACT_TABLES = (
    "stock_metadata",
    "stock_quote_snapshots",
    "stock_scores",
    "stock_scores_history",
    "tradable_universe_history",
    "model_predictions",
    "global_rank_history",
    "global_oracle_labels",
    "oracle_extreme_predictions",
    "model_registry",
    "model_metrics",
    "model_metrics_full",
    "model_batch_diagnostics",
    "model_directional_oos_metrics",
    "champion_history",
    "model_governance",
    "stock_fundamentals_daily",
    "stock_earnings_calendar",
    "stock_analyst_consensus_snapshots",
    "stock_analyst_eps_revision_history",
    "stock_analyst_eps_trend_history",
    "stock_analyst_estimate_history",
    "stock_analyst_recommendation_history",
    "stock_analyst_target_history",
    "ticker_daily_sentiment_features",
    "news_ticker_sentiment",
    "corporate_action_source_events",
    "corporate_actions_events",
    "corporate_actions_applications",
    "sec_filing_raw",
    "sec_corporate_events",
    # Les deux historiques les plus volumineux passent en dernier : les
    # diagnostics/serving retrouvent ainsi leur parité avant la fin du lot long.
    "stock_bars_daily",
    "stock_bars",
)
MIC_BY_EXCHANGE = {
    "NASDAQ": "XNAS",
    "NYSE": "XNYS",
    "AMEX": "XASE",
    "ARCA": "ARCX",
    "BATS": "BATS",
    "OTC": "OTCM",
}
DATE_COLUMNS = ("date", "prediction_date", "trade_date", "snapshot_date", "quote_date", "earnings_date", "as_of_date", "filing_date", "ex_date", "timestamp")
ID_COLUMNS = ("id", "prediction_id", "registry_id", "metric_id", "governance_id")
TICKER_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,31}$")
CRITICAL_SYMBOL_SQL = (
    "UPPER(TRIM(t.symbol)) REGEXP '^[A-Z0-9][A-Z0-9.\\-]{0,31}$' "
    "AND UPPER(TRIM(t.symbol)) NOT LIKE '\\_\\_%'"
)


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema_version": 1, "tables": {}, "started_at": datetime.now(UTC).isoformat()}
    return json.loads(path.read_text(encoding="utf-8"))


def _save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)


def bootstrap_us_instruments(engine: Engine) -> dict[str, int]:
    """Crée une identité stable pour chaque titre US non crypto du master legacy."""
    with engine.connect() as connection:
        metadata = (
            connection.execute(
                text("""
            SELECT UPPER(TRIM(symbol)) symbol, exchange, company_name, status,
                   MIN(DATE(last_updated)) listing_hint
            FROM stock_metadata
            WHERE asset_class IS NULL OR asset_class <> 'crypto'
            GROUP BY UPPER(TRIM(symbol)), exchange, company_name, status
        """)
            )
            .mappings()
            .all()
        )
    rows = []
    for item in metadata:
        symbol = str(item["symbol"] or "").strip().upper()
        if not symbol:
            continue
        mic = MIC_BY_EXCHANGE.get(str(item["exchange"] or "").strip().upper())
        identity_mic = mic or "PENDING"
        rows.append(
            {
                "uid": build_instrument_uid("US_EQ", identity_mic, symbol),
                "mic": mic,
                "symbol": symbol,
                "name": item["company_name"],
                "status": "mapped" if mic else "mapping_pending",
                "active": str(item["status"] or "").lower() != "inactive",
            }
        )
    insert = text("""
        INSERT INTO instruments (
            instrument_uid,market_code,exchange_mic,local_symbol,display_name,
            instrument_type,currency,mapping_status,is_active
        ) VALUES (:uid,'US_EQ',:mic,:symbol,:name,'equity','USD',:status,:active)
        ON DUPLICATE KEY UPDATE display_name=COALESCE(VALUES(display_name),display_name),
            is_active=VALUES(is_active), updated_at=CURRENT_TIMESTAMP(6)
    """)
    with engine.begin() as connection:
        for start in range(0, len(rows), 1000):
            connection.execute(insert, rows[start : start + 1000])
        connection.execute(
            text("""
            INSERT INTO instrument_provider_symbols (
                instrument_id,provider,provider_symbol,provider_exchange,valid_from,valid_to,is_primary
            )
            SELECT i.instrument_id,'legacy_us_symbol',i.local_symbol,i.exchange_mic,'1900-01-01',NULL,TRUE
            FROM instruments i
            LEFT JOIN instrument_provider_symbols p
              ON p.instrument_id=i.instrument_id AND p.provider='legacy_us_symbol'
             AND p.provider_symbol=i.local_symbol AND p.valid_to IS NULL
            WHERE i.market_code='US_EQ' AND p.mapping_id IS NULL
        """)
        )
    existing = set(inspect(engine).get_table_names())
    known = {row["symbol"] for row in rows}
    historical_symbols: set[str] = set()
    with engine.connect() as connection:
        for table in FACT_TABLES:
            if table not in existing or table == "stock_metadata":
                continue
            columns = {column["name"] for column in inspect(engine).get_columns(table)}
            if "symbol" not in columns:
                continue
            values = connection.execute(
                text(f"SELECT DISTINCT symbol FROM `{table}` WHERE symbol IS NOT NULL")
            ).scalars()
            historical_symbols.update(
                symbol for raw in values if (symbol := str(raw or "").strip().upper()) and TICKER_PATTERN.fullmatch(symbol)
            )
    pending = sorted(historical_symbols - known)
    pending_rows = [
        {
            "uid": build_instrument_uid("US_EQ", "PENDING", symbol),
            "mic": None,
            "symbol": symbol,
            "name": None,
            "status": "mapping_pending",
            "active": False,
        }
        for symbol in pending
    ]
    with engine.begin() as connection:
        for start in range(0, len(pending_rows), 1000):
            connection.execute(insert, pending_rows[start : start + 1000])
        connection.execute(
            text("""
            INSERT INTO instrument_provider_symbols (
                instrument_id,provider,provider_symbol,provider_exchange,valid_from,valid_to,is_primary
            )
            SELECT i.instrument_id,'legacy_us_symbol',i.local_symbol,i.exchange_mic,'1900-01-01',NULL,TRUE
            FROM instruments i
            LEFT JOIN instrument_provider_symbols p
              ON p.instrument_id=i.instrument_id AND p.provider='legacy_us_symbol'
             AND p.provider_symbol=i.local_symbol AND p.valid_to IS NULL
            WHERE i.market_code='US_EQ' AND p.mapping_id IS NULL
        """)
        )
    return {
        "metadata_candidates": len(rows),
        "created_or_refreshed": len(rows) + len(pending_rows),
        "historical_mapping_pending": len(pending_rows),
    }


def _table_strategy(engine: Engine, table: str) -> tuple[str, str | None]:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns(table)}
    indexed_prefixes = {
        tuple(index.get("column_names") or ())[:1]
        for index in inspector.get_indexes(table)
    }
    primary_prefix = tuple(inspector.get_pk_constraint(table).get("constrained_columns") or ())[:1]
    indexed_prefixes.add(primary_prefix)
    if "symbol" in columns and ("symbol",) in indexed_prefixes:
        return "symbol", "symbol"
    for candidate in DATE_COLUMNS:
        if candidate in columns and (candidate,) in indexed_prefixes:
            return "date", candidate
    for candidate in ID_COLUMNS:
        if candidate in columns and (candidate,) in indexed_prefixes:
            return "id", candidate
    return "whole", None


def _update_range(
    engine: Engine,
    table: str,
    predicate: str,
    params: dict[str, Any],
    *,
    symbol_lookup: bool = False,
    straight_join: bool = False,
) -> int:
    join_expression = (
        "i.local_symbol=CONVERT(UPPER(TRIM(t.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci"
    )
    if symbol_lookup and engine.dialect.name in {"mysql", "mariadb"}:
        with engine.connect() as connection:
            collation = connection.execute(
                text("""
                SELECT COLLATION_NAME
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=:table AND COLUMN_NAME='symbol'
            """),
                {"table": table},
            ).scalar()
        if collation:
            join_expression = f"i.local_symbol COLLATE {collation}=t.symbol"
    join_keyword = "STRAIGHT_JOIN" if straight_join else "JOIN"
    statement = text(f"""
        UPDATE `{table}` t
        {join_keyword} instruments i
          ON i.market_code='US_EQ' AND {join_expression}
        SET t.instrument_id=i.instrument_id
        WHERE t.instrument_id IS NULL AND {predicate}
    """)
    with engine.begin() as connection:
        result = connection.execute(statement, params)
        return int(result.rowcount or 0)


def _update_symbol_mappings(engine: Engine, table: str, mappings: list[dict[str, Any]]) -> int:
    if not mappings:
        return 0
    with engine.begin() as connection:
        result = connection.execute(
            text(f"""
            UPDATE `{table}`
            SET instrument_id=:instrument_id
            WHERE instrument_id IS NULL AND symbol=:symbol
        """),
            mappings,
        )
        return int(result.rowcount or 0)


def _update_symbol_range(
    engine: Engine,
    table: str,
    lower: int,
    upper: int,
    *,
    workers: int = 4,
) -> int:
    """Backfill par recherches ticker indexées, sans scan complet de la table.

    MySQL choisit systématiquement la grande table de faits comme première
    table d'un ``UPDATE ... JOIN``, même avec un intervalle très sélectif sur
    ``instruments``. Un ``executemany`` conserve de petites transactions tout
    en faisant une recherche directe dans l'index historique ``symbol``.
    """
    with engine.connect() as connection:
        mappings = connection.execute(
            text("""
            SELECT instrument_id, local_symbol
            FROM instruments
            WHERE market_code='US_EQ'
              AND instrument_id > :lower AND instrument_id <= :upper
            ORDER BY instrument_id
        """),
            {"lower": lower, "upper": upper},
        ).mappings().all()
    parameters = [
        {"instrument_id": int(row["instrument_id"]), "symbol": row["local_symbol"]}
        for row in mappings
    ]
    worker_count = min(max(1, workers), len(parameters))
    if worker_count == 1:
        return _update_symbol_mappings(engine, table, parameters)
    chunks = [parameters[index::worker_count] for index in range(worker_count)]
    with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="iid-backfill") as executor:
        return sum(executor.map(lambda chunk: _update_symbol_mappings(engine, table, chunk), chunks))


def _advance_months(value: date, months: int) -> date:
    absolute = value.year * 12 + value.month - 1 + months
    return date(absolute // 12, absolute % 12 + 1, 1)


def backfill_us_facts(
    engine: Engine,
    state_path: Path = DEFAULT_STATE,
    *,
    id_chunk: int = 250_000,
    symbol_chunk: int = 500,
    symbol_workers: int = 4,
    date_chunk_months: int = 1,
) -> dict[str, Any]:
    state = _load_state(state_path)
    existing = set(inspect(engine).get_table_names())
    for table in FACT_TABLES:
        if table not in existing:
            continue
        table_state = state["tables"].setdefault(table, {"status": "PENDING", "updated": 0})
        if table_state.get("status") == "COMPLETED":
            continue
        strategy, column = _table_strategy(engine, table)
        if table_state.get("strategy") != strategy:
            table_state.pop("cursor", None)
        table_state["strategy"] = strategy
        LOGGER.info("Backfill %s strategy=%s column=%s", table, strategy, column)
        if strategy == "symbol":
            with engine.connect() as connection:
                maximum = int(
                    connection.execute(
                        text("SELECT COALESCE(MAX(instrument_id),0) FROM instruments WHERE market_code='US_EQ'")
                    ).scalar()
                    or 0
                )
            cursor = int(table_state.get("cursor", 0))
            while cursor < maximum:
                upper = min(maximum, cursor + max(1, symbol_chunk))
                table_state["updated"] += _update_symbol_range(
                    engine,
                    table,
                    cursor,
                    upper,
                    workers=symbol_workers,
                )
                cursor = upper
                table_state["cursor"] = cursor
                _save_state(state_path, state)
        elif strategy == "date" and column:
            with engine.connect() as connection:
                bounds = connection.execute(text(f"SELECT MIN(`{column}`),MAX(`{column}`) FROM `{table}`")).one()
            if bounds[0] is not None:
                cursor = date.fromisoformat(table_state.get("cursor") or str(bounds[0]))
                maximum = bounds[1]
                while cursor <= maximum:
                    following = _advance_months(cursor, max(1, date_chunk_months))
                    table_state["updated"] += _update_range(
                        engine,
                        table,
                        f"t.`{column}` >= :start AND t.`{column}` < :end",
                        {"start": cursor, "end": following},
                    )
                    cursor = following
                    table_state["cursor"] = cursor.isoformat()
                    _save_state(state_path, state)
        elif strategy == "id" and column:
            with engine.connect() as connection:
                maximum = int(
                    connection.execute(text(f"SELECT COALESCE(MAX(`{column}`),0) FROM `{table}`")).scalar() or 0
                )
            cursor = int(table_state.get("cursor", 0))
            while cursor < maximum:
                upper = min(maximum, cursor + id_chunk)
                table_state["updated"] += _update_range(
                    engine,
                    table,
                    f"t.`{column}` > :lower AND t.`{column}` <= :upper",
                    {"lower": cursor, "upper": upper},
                )
                cursor = upper
                table_state["cursor"] = cursor
                _save_state(state_path, state)
        else:
            table_state["updated"] += _update_range(engine, table, "1=1", {}, straight_join=True)
        table_state["status"] = "COMPLETED"
        table_state["completed_at"] = datetime.now(UTC).isoformat()
        _save_state(state_path, state)
    state["completed_at"] = datetime.now(UTC).isoformat()
    _save_state(state_path, state)
    return state


def reconcile_us_facts(engine: Engine, state_path: Path) -> dict[str, Any]:
    """Effectue un scan unique par table après création des mappings historiques.

    Le backfill principal privilégie les index et les petites transactions. Une
    seconde exécution par dates rescannerait toutefois plusieurs fois les mêmes
    dizaines de millions de lignes. Après le bootstrap historique, un seul scan
    reprend toutes les lignes encore nulles et reste reprenable table par table.
    """
    state = _load_state(state_path)
    existing = set(inspect(engine).get_table_names())
    for table in FACT_TABLES:
        if table not in existing:
            continue
        table_state = state["tables"].setdefault(table, {"status": "PENDING", "updated": 0})
        if table_state.get("status") == "COMPLETED":
            continue
        LOGGER.info("Reconcile %s single_scan", table)
        table_state["strategy"] = "single_scan_reconciliation"
        table_state["updated"] += _update_range(engine, table, "1=1", {}, straight_join=True)
        table_state["status"] = "COMPLETED"
        table_state["completed_at"] = datetime.now(UTC).isoformat()
        _save_state(state_path, state)
    state["completed_at"] = datetime.now(UTC).isoformat()
    _save_state(state_path, state)
    return state


def audit_us_fact_coverage(engine: Engine) -> dict[str, Any]:
    existing = set(inspect(engine).get_table_names())
    report: dict[str, Any] = {"generated_at": datetime.now(UTC).isoformat(), "tables": {}}
    with engine.connect() as connection:
        for table in FACT_TABLES:
            if table not in existing:
                continue
            if table == "stock_metadata":
                where = "asset_class IS NULL OR asset_class <> 'crypto'"
                total = connection.execute(text(f"SELECT COUNT(*) FROM `{table}` WHERE {where}")).scalar()
                missing = connection.execute(
                    text(f"SELECT COUNT(*) FROM `{table}` WHERE ({where}) AND instrument_id IS NULL")
                ).scalar()
            else:
                total = connection.execute(text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
                missing = connection.execute(
                    text(f"""
                    SELECT COUNT(*) FROM `{table}` t
                    LEFT JOIN stock_metadata m ON CONVERT(m.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci=CONVERT(t.symbol USING utf8mb4) COLLATE utf8mb4_unicode_ci
                    WHERE t.instrument_id IS NULL
                      AND ({CRITICAL_SYMBOL_SQL})
                      AND m.symbol IS NOT NULL
                      AND (m.asset_class IS NULL OR m.asset_class <> 'crypto')
                """)
                ).scalar()
            mismatch = connection.execute(
                text(f"""
                SELECT COUNT(*) FROM `{table}` t JOIN instruments i ON i.instrument_id=t.instrument_id
                WHERE i.market_code<>'US_EQ' OR i.local_symbol<>CONVERT(UPPER(TRIM(t.symbol)) USING utf8mb4) COLLATE utf8mb4_unicode_ci
            """)
            ).scalar()
            report["tables"][table] = {
                "rows": int(total or 0),
                "missing_critical": int(missing or 0),
                "mismatch": int(mismatch or 0),
                "coverage": 1.0 if not total else 1.0 - (int(missing or 0) / int(total)),
            }
    report["gate"] = (
        "PASS"
        if all(row["missing_critical"] == 0 and row["mismatch"] == 0 for row in report["tables"].values())
        else "FAIL"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("bootstrap", "backfill", "reconcile", "audit", "all"),
        default="all",
    )
    parser.add_argument("--state-path", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--id-chunk", type=int, default=250_000)
    parser.add_argument("--symbol-chunk", type=int, default=500)
    parser.add_argument("--symbol-workers", type=int, default=4)
    parser.add_argument("--date-chunk-months", type=int, default=1)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    engine = get_sqlalchemy_engine()
    if args.mode in {"bootstrap", "all"}:
        print(json.dumps(bootstrap_us_instruments(engine), sort_keys=True))
    if args.mode in {"backfill", "all"}:
        backfill_us_facts(
            engine,
            args.state_path,
            id_chunk=args.id_chunk,
            symbol_chunk=args.symbol_chunk,
            symbol_workers=args.symbol_workers,
            date_chunk_months=args.date_chunk_months,
        )
    if args.mode == "reconcile":
        reconcile_us_facts(engine, args.state_path)
    if args.mode in {"audit", "all"}:
        report = audit_us_fact_coverage(engine)
        output = args.state_path.with_name("coverage_report.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps({"gate": report["gate"], "report": str(output)}, sort_keys=True))
        if report["gate"] != "PASS":
            raise SystemExit(2)


if __name__ == "__main__":
    main()
