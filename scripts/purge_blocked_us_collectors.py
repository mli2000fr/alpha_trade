"""Narrow purge of Yahoo analyst, FRED and FINRA rows; never CN/FR SQL.

Default: read-only preview. --execute deletes the allowlisted source rows in
small committed chunks. No backup of restricted payloads is created.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from database.router import get_market_engine
from common.config_loader import load_batch_config

TARGETS = [
    ("stock_analyst_estimate_history", "provider = :source", {"source": "yahoo"}),
    ("stock_analyst_eps_trend_history", "provider = :source", {"source": "yahoo"}),
    ("stock_analyst_eps_revision_history", "provider = :source", {"source": "yahoo"}),
    ("stock_analyst_target_history", "provider = :source", {"source": "yahoo"}),
    ("stock_analyst_recommendation_history", "provider = :source", {"source": "yahoo"}),
    ("stock_short_volume_daily", "provider = :source", {"source": "finra_cnms"}),
    ("macro_vintage_observations", "provider = :source", {"source": "fred_alfred"}),
    ("analyst_snapshot_collection_run", "provider = :source", {"source": "yahoo"}),
    ("pit_raw_payloads", "batch_name IN (:fred, :finra)",
     {"fred": "fred_alfred_vintage_sync", "finra": "finra_short_volume_sync"}),
    ("pit_collection_runs", "batch_name IN (:fred, :finra)",
     {"fred": "fred_alfred_vintage_sync", "finra": "finra_short_volume_sync"}),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    cfg = load_batch_config()
    for name in ("analyst_snapshot_collection", "fred_alfred_vintage_sync", "finra_short_volume_sync"):
        section = cfg[name]
        if section.get("enabled") or not str(section.get("status", "")).startswith("BLOCKED_"):
            raise RuntimeError(f"Collector not blocked: {name}")
    engine = get_market_engine("US_EQ", database_alias="us_primary")
    inspector = inspect(engine)
    with engine.connect() as conn:
        if conn.execute(text("SELECT DATABASE()")).scalar() != "alpha_trade":
            raise RuntimeError("Purge allowed only in alpha_trade")
    quote = engine.dialect.identifier_preparer.quote
    target_names = {table for table, _, _ in TARGETS}
    # Do not disable constraints or permit an implicit cascade into other data.
    for table in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table):
            if fk.get("referred_table") in target_names:
                raise RuntimeError(f"Incoming foreign key requires explicit review: {table}/{fk.get('name')}")
    report = {"at": datetime.now(UTC).isoformat(), "database": "alpha_trade",
              "execute": args.execute, "targets": [], "complete": False}
    folder = ROOT / "artifacts/operations/blocked_collectors_purge"
    report_path = folder / (datetime.now(UTC).strftime("us-%Y%m%dT%H%M%S%fZ") + ".json")
    if args.execute:
        folder.mkdir(parents=True, exist_ok=True)
    for table, predicate, params in TARGETS:
        if not inspector.has_table(table):
            raise RuntimeError(f"Missing table: {table}")
        identifier = quote(table)
        query = text(f"SELECT COUNT(*) FROM {identifier} WHERE {predicate}")
        with engine.connect() as conn:
            before = conn.execute(query, params).scalar_one()
            total_before = conn.execute(text(f"SELECT COUNT(*) FROM {identifier}")).scalar_one()
        entry = {"table": table, "predicate": predicate, "parameters": params,
                 "matched_before": before, "other_rows_before": total_before - before, "deleted": 0}
        report["targets"].append(entry)
        if args.execute:
            while True:
                with engine.begin() as conn:
                    count = conn.execute(text(f"DELETE FROM {identifier} WHERE {predicate} LIMIT 10000"), params).rowcount
                entry["deleted"] += count
                report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
                if count == 0:
                    break
        with engine.connect() as conn:
            entry["matched_after"] = conn.execute(query, params).scalar_one()
            total_after = conn.execute(text(f"SELECT COUNT(*) FROM {identifier}")).scalar_one()
        entry["other_rows_after"] = total_after - entry["matched_after"]
        print(json.dumps(entry), flush=True)
        if args.execute and (entry["matched_after"] or entry["other_rows_after"] != entry["other_rows_before"]):
            raise RuntimeError(f"Unexpected remaining/moved rows: {table}")
    report["complete"] = True
    if args.execute:
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"REPORT {report_path}", flush=True)


if __name__ == "__main__":
    main()
