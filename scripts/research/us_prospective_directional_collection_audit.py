"""Read-only coverage audit of prospective US collections; no training or SQL writes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine


TABLES = {
    "stock_borrow_status_snapshots": ("symbol", "available_at", "observed_at"),
    "stock_option_snapshots": ("underlying_symbol", "available_at", "observed_at"),
    "stock_option_bars_delayed": ("underlying_symbol", "available_at", "bar_timestamp"),
    "stock_option_contract_versions": ("underlying_symbol", "available_at", "observed_at"),
    "stock_opening_window_bars": ("symbol", "available_at", "bar_timestamp"),
    "sec_filing_raw": ("symbol", "available_at", "filing_date"),
    "sec_corporate_events": ("symbol", "available_at", "filing_date"),
    "sec_ownership_snapshots": ("issuer_symbol", "available_at", "report_period"),
    "security_master_snapshots": ("symbol", "available_at", "snapshot_date"),
    "corporate_action_source_events": ("symbol", "available_at", "effective_date"),
    "stock_fundamentals_daily": ("symbol", "fetched_at", "trade_date"),
    "stock_earnings_calendar": ("symbol", "last_updated", "earnings_date"),
    "stock_quote_snapshots": ("symbol", "last_updated", "quote_date"),
    "ticker_daily_sentiment_features": ("symbol", "updated_at", "trade_date"),
    "stock_analyst_estimate_history": ("symbol", "available_at", "snapshot_date"),
    "stock_analyst_eps_trend_history": ("symbol", "available_at", "snapshot_date"),
    "stock_analyst_eps_revision_history": ("symbol", "available_at", "snapshot_date"),
    "stock_analyst_target_history": ("symbol", "available_at", "snapshot_date"),
    "stock_analyst_recommendation_history": ("symbol", "available_at", "snapshot_date"),
    "stock_analyst_consensus_snapshots": ("symbol", "available_at", "observed_at"),
    "stock_short_volume_daily": ("symbol", "available_at", "trade_date"),
}


def query(conn, sql, symbols=None, **params):
    statement = text(sql)
    if symbols is not None:
        statement = statement.bindparams(bindparam("symbols", expanding=True))
        params["symbols"] = symbols
    return [dict(row) for row in conn.execute(statement, params).mappings()]


def run(args):
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    universe_bytes = Path(args.universe).read_bytes()
    symbols = sorted(set(re.split(r"[,;\s]+", universe_bytes.decode("utf-8-sig").strip())))
    symbols = [symbol.upper() for symbol in symbols if symbol]
    config = yaml.safe_load(Path("batch.yaml").read_text(encoding="utf-8-sig"))
    report = {
        "audit_at_utc": datetime.now(timezone.utc).isoformat(),
        "start": args.start,
        "end_exclusive": args.end,
        "universe": args.universe,
        "universe_sha256": hashlib.sha256(universe_bytes).hexdigest(),
        "universe_count": len(symbols),
        "sql_mode": "SELECT_ONLY",
        "tables": {},
        "batch_config": {
            name: {key: entry.get(key) for key in ("enabled", "status", "tables", "provider")}
            for name, entry in config.items() if isinstance(entry, dict)
        },
    }
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        # This connection cannot issue DML, even accidentally.
        conn.execute(text("SET SESSION TRANSACTION READ ONLY"))
        report["server_clock"] = query(conn, "SELECT UTC_TIMESTAMP() AS clock_utc, NOW() AS clock_session")
        for table, (symbol_col, observed, event) in TABLES.items():
            print(f"Inventory {table}", flush=True)
            global_rows = query(conn, f"SELECT COUNT(*) AS rows_total, MIN({observed}) AS first_observed, MAX({observed}) AS last_observed FROM alpha_trade.{table}")[0]
            scoped = query(conn, f"""SELECT COUNT(*) AS rows_in_universe,
                COUNT(DISTINCT {symbol_col}) AS symbols,
                COUNT(DISTINCT DATE({observed})) AS observation_days,
                MIN({observed}) AS first_observed, MAX({observed}) AS last_observed,
                MIN({event}) AS first_event, MAX({event}) AS last_event
                FROM alpha_trade.{table} WHERE {symbol_col} IN :symbols
                AND {observed} >= :start AND {observed} < :end""",
                symbols, start=args.start, end=args.end)[0]
            daily = query(conn, f"""SELECT DATE({observed}) AS day, COUNT(*) AS rows_count,
                COUNT(DISTINCT {symbol_col}) AS symbols
                FROM alpha_trade.{table} WHERE {symbol_col} IN :symbols
                AND {observed} >= :start AND {observed} < :end
                GROUP BY DATE({observed}) ORDER BY day""", symbols, start=args.start, end=args.end)
            report["tables"][table] = {"global": global_rows, "recent": scoped, "daily": daily,
                "coverage_pct": scoped["symbols"] / len(symbols) * 100,
                "observation_column": observed, "event_column": event}
        report["news"] = query(conn, """SELECT nr.effective_trade_date AS day,
            COUNT(*) AS sentiment_rows, COUNT(DISTINCT nts.symbol) AS symbols,
            SUM(nts.inference_status='success') AS successes,
            SUM(nts.inference_status='failed') AS failures,
            MIN(GREATEST(nr.created_at,nts.created_at)) AS first_observed,
            MAX(GREATEST(nr.updated_at,nts.updated_at)) AS last_updated
            FROM alpha_trade.news_ticker_sentiment nts
            JOIN alpha_trade.news_raw nr ON nr.article_id=nts.article_id
            WHERE nts.symbol IN :symbols AND nr.effective_trade_date >= :start
            AND nr.effective_trade_date < :end GROUP BY nr.effective_trade_date
            ORDER BY day""", symbols, start=args.start, end=args.end)
        report["collection_runs"] = query(conn, """SELECT batch_name,status,COUNT(*) AS runs,
            MIN(started_at) AS first_run,MAX(started_at) AS last_run,
            SUM(requested_count) AS requested,SUM(received_count) AS received,
            SUM(persisted_count) AS persisted,SUM(failed_count) AS failed
            FROM alpha_trade.pit_collection_runs WHERE started_at>=:start AND started_at<:end
            GROUP BY batch_name,status ORDER BY batch_name,status""", start=args.start,end=args.end)
        report["bars"] = query(conn, """SELECT date,COUNT(*) AS rows_count,
            SUM(COALESCE(is_filled,1)=0 AND close>0 AND volume>0) AS nonfilled_positive,
            COUNT(DISTINCT symbol) AS symbols FROM alpha_trade.stock_bars_daily
            WHERE symbol IN :symbols AND date>=:start AND date<:end
            GROUP BY date ORDER BY date""", symbols, start=args.start,end=args.end)
        report["oracle_predictions"] = query(conn, """SELECT batch_id,
            COUNT(*) AS rows_count, COUNT(DISTINCT symbol) AS symbols,
            MIN(prediction_date) AS first_date,MAX(prediction_date) AS last_date,
            COUNT(DISTINCT prediction_date) AS days
            FROM alpha_trade.oracle_extreme_predictions
            WHERE symbol IN :symbols AND prediction_date>=:start AND prediction_date<:end
            GROUP BY batch_id ORDER BY rows_count DESC""",symbols,start=args.start,end=args.end)
        report["sec_documents"] = query(conn, """SELECT document_type,COUNT(*) AS documents,
            COUNT(DISTINCT accession_number) AS accessions,MIN(available_at) AS first_observed,
            MAX(available_at) AS last_observed FROM alpha_trade.sec_filing_documents
            WHERE available_at>=:start AND available_at<:end GROUP BY document_type""",start=args.start,end=args.end)
        conn.rollback()
    engine.dispose()
    (output / "inventory.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"output": str(output), "universe_count": len(symbols),
        "coverage": {name: value["recent"] for name,value in report["tables"].items()},
        "bars": report["bars"], "oracle_predictions": report["oracle_predictions"]},default=str),flush=True)
    return report


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--universe",default="config/univers_batch/univers_filtred_tradable.txt")
    parser.add_argument("--start",default="2026-09-10")
    parser.add_argument("--end",default="2026-10-11")
    parser.add_argument("--output-dir",default="artifacts/research/us_prospective_directional_audit/20261010-v1")
    run(parser.parse_args())
