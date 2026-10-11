"""Extract a strict table allowlist; append missing snapshots without replacing rows.

Only INSERT data from our mysqldump archive is used. DDL, locks, triggers and
session commands from the archive are never executed. IDs are not transferred
into the destination. Existing natural keys always win, including conflicts.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import time
from pathlib import Path

from sqlalchemy import text

TABLES = {
    "analyst_snapshot_collection_run": ["run_id"],
    "stock_analyst_estimate_history": ["provider", "symbol", "snapshot_date", "estimate_type", "horizon_normalized"],
    "stock_analyst_eps_trend_history": ["provider", "symbol", "snapshot_date", "horizon_normalized"],
    "stock_analyst_eps_revision_history": ["provider", "symbol", "snapshot_date", "horizon_normalized"],
    "stock_analyst_target_history": ["provider", "symbol", "snapshot_date"],
    "stock_analyst_recommendation_history": ["provider", "symbol", "snapshot_date", "period_raw"],
}
CREATE = re.compile(r"^CREATE TABLE `([a-z_]+)` \(")
INSERT = re.compile(r"^INSERT INTO `([a-z_]+)` VALUES ")
COLUMN = re.compile(r"^  `([a-z_0-9]+)` ")


def save(path, payload):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def extract(archive: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    if (output / "extraction.json").exists():
        report = json.loads((output / "extraction.json").read_text())
        if report["archive"] != str(archive.resolve()):
            raise ValueError("Different source archive")
        for table, meta in report["tables"].items():
            if hashlib.sha256((output / (table + ".sql")).read_bytes()).hexdigest() != meta["sha256"]:
                raise ValueError("Extract integrity mismatch: " + table)
        return report
    columns = {t: [] for t in TABLES}
    statements = {t: 0 for t in TABLES}
    handles = {t: (output / (t + ".sql")).open("w", encoding="utf-8", newline="\n") for t in TABLES}
    current = None
    raw_bytes = 0
    last = time.monotonic()
    try:
        with archive.open("rb") as source, gzip.GzipFile(fileobj=source) as stream:
            for raw in stream:
                raw_bytes += len(raw)
                # Avoid decoding the rest of the database, including large text payloads.
                if raw.startswith(b"CREATE TABLE "):
                    match = CREATE.match(raw.decode("utf-8"))
                    current = match.group(1) if match and match.group(1) in TABLES else None
                elif current and raw.startswith(b"  `"):
                    match = COLUMN.match(raw.decode("utf-8"))
                    if match:
                        columns[current].append(match.group(1))
                elif raw.startswith(b") ENGINE="):
                    current = None
                elif raw.startswith(b"INSERT INTO `"):
                    prefix = raw[:160].decode("utf-8", errors="replace")
                    match = INSERT.match(prefix)
                    if match and match.group(1) in TABLES:
                        table = match.group(1)
                        if not columns[table]:
                            raise ValueError("Missing archived column layout: " + table)
                        statement = raw.decode("utf-8").rstrip()
                        if not statement.endswith(";"):
                            raise ValueError("Unsupported multiline INSERT")
                        handles[table].write(statement + "\n")
                        statements[table] += 1
                if time.monotonic() - last >= 20:
                    progress = {"status": "EXTRACTING", "compressed_read": source.tell(),
                                "compressed_total": archive.stat().st_size, "uncompressed_read": raw_bytes,
                                "insert_statements": statements}
                    save(output / "progress.json", progress)
                    print(json.dumps(progress), flush=True)
                    last = time.monotonic()
    finally:
        for handle in handles.values():
            handle.close()
    if any(not columns[t] for t in TABLES):
        raise ValueError("Archive missing expected table schemas")
    report = {"archive": str(archive.resolve()), "tables": {
        t: {"columns": columns[t], "insert_statements": statements[t],
            "sha256": hashlib.sha256((output / (t + ".sql")).read_bytes()).hexdigest()}
        for t in TABLES}}
    save(output / "extraction.json", report)
    save(output / "progress.json", {"status": "EXTRACTED"})
    return report


def restore(output: Path, *, write=False):
    from database.connection import get_sqlalchemy_engine
    report = json.loads((output / "extraction.json").read_text())
    results = {}
    engine = get_sqlalchemy_engine(db_name="alpha_trade")
    with engine.connect() as conn:
        conn.exec_driver_sql("SET SESSION sql_mode=CONCAT(@@SESSION.sql_mode, ',NO_AUTO_VALUE_ON_ZERO')")
        conn.commit()
        for table, keys in TABLES.items():
            meta = report["tables"][table]
            extract_path = output / (table + ".sql")
            if hashlib.sha256(extract_path.read_bytes()).hexdigest() != meta["sha256"]:
                raise ValueError("Extract integrity mismatch")
            dest_columns = {r[0] for r in conn.exec_driver_sql(f"SHOW COLUMNS FROM `{table}`")}
            if not set(meta["columns"]) <= dest_columns:
                raise ValueError("Incompatible destination schema: " + table)
            temp = "restore_" + table
            conn.exec_driver_sql(f"CREATE TEMPORARY TABLE `{temp}` LIKE `{table}`")
            quoted = ",".join(f"`{c}`" for c in meta["columns"])
            with extract_path.open(encoding="utf-8") as stream:
                for statement in stream:
                    prefix = f"INSERT INTO `{table}` VALUES "
                    if not statement.startswith(prefix):
                        raise ValueError("Untrusted statement prefix")
                    conn.exec_driver_sql(f"INSERT INTO `{temp}` ({quoted}) VALUES " + statement[len(prefix):])
            join = " AND ".join(f"s.`{c}` <=> d.`{c}`" for c in keys)
            count = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{temp}`").scalar_one()
            existing = conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{temp}` s JOIN `{table}` d ON {join}").scalar_one()
            conflicts = (conn.exec_driver_sql(f"SELECT COUNT(*) FROM `{temp}` s JOIN `{table}` d ON {join} WHERE NOT(s.raw_hash <=> d.raw_hash)").scalar_one()
                         if "raw_hash" in dest_columns else None)
            row = {"archived": count, "existing_keys": existing, "missing": count-existing,
                   "payload_conflicts_kept_current": conflicts, "inserted": 0}
            # Commit temporary loading only; no destination writes yet.
            conn.commit()
            if write:
                backup_path = output / (table + ".before.jsonl.gz")
                if not backup_path.exists():
                    with gzip.open(backup_path, "wt", encoding="utf-8") as backup:
                        for record in conn.execute(text(f"SELECT * FROM `{table}`")).mappings():
                            backup.write(json.dumps(dict(record), default=str) + "\n")
                    conn.commit()
                columns = [c for c in meta["columns"] if c != "id"]
                quoted = ",".join(f"`{c}`" for c in columns)
                selected = ",".join(f"s.`{c}`" for c in columns)
                with conn.begin():
                    result = conn.exec_driver_sql(f"INSERT INTO `{table}` ({quoted}) SELECT {selected} FROM `{temp}` s WHERE NOT EXISTS (SELECT 1 FROM `{table}` d WHERE {join})")
                    row["inserted"] = result.rowcount
            results[table] = row
            print(table, json.dumps(row), flush=True)
            save(output / ("restore.json" if write else "preview.json"), results)
            conn.exec_driver_sql(f"DROP TEMPORARY TABLE `{temp}`")
            conn.commit()
    save(output / "progress.json", {"status": "RESTORED" if write else "PREVIEWED", "tables": results})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--phase", choices=["extract", "preview", "restore"], default="extract")
    args = parser.parse_args()
    extract(args.archive, args.output)
    if args.phase != "extract":
        restore(args.output, write=args.phase == "restore")
