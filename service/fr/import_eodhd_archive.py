"""Indexe l'archive EODHD FR dans fr_raw_payloads, sans identité ni canonique.

Refuse une archive incomplète ou non auditée. Ne lit jamais le token API.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text

from database.router import build_database_url


def archive_rows(root: Path) -> tuple[dict, list[dict]]:
    root = root.resolve()
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    quality = json.loads((root / "quality_report.json").read_text(encoding="utf-8"))
    if summary["failed"] or summary["completed"] + summary["skipped"] != summary["selected"]:
        raise ValueError("archive incomplète ou en échec")
    if quality["archived"] != summary["selected"] or quality["counts"].get("sha256_mismatch", 0):
        raise ValueError("audit de qualité incomplet ou hash invalide")
    rows = []
    for meta_path in sorted((root / "symbols").glob("*.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("status") != "COMPLETED" or meta.get("window") != summary["window"]:
            continue
        observed = datetime.fromisoformat(meta["collected_at"]).astimezone(UTC).replace(tzinfo=None)
        for kind, item in meta["payloads"].items():
            path = (root / item["file"]).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise ValueError("payload absent ou hors archive")
            rows.append({"provider": "EODHD", "dataset": kind,
                         "request_key": f"{meta['symbol']}:{summary['window'][0]}:{summary['window'][1]}",
                         "sha256": item["sha256"], "uri": str(path),
                         "observed": observed})
    if len(rows) != summary["selected"] * 3:
        raise ValueError("métadonnées de payload incomplètes")
    return summary, rows


def import_archive(root: Path) -> dict:
    summary, rows = archive_rows(root)
    engine = create_engine(build_database_url("fr_primary", "FR_EQ"), pool_pre_ping=True)
    run_key = hashlib.sha256((str(root.resolve()) + str(summary["window"])).encode()).hexdigest()
    run_id = f"fr-eodhd-raw-{run_key[:20]}"
    now = datetime.now(UTC).replace(tzinfo=None)
    try:
        with engine.begin() as conn:
            actual = conn.execute(text("SELECT DATABASE()")).scalar()
            if actual != "alpha_trade_fr":
                raise RuntimeError(f"import FR refusé sur {actual!r}")
            conn.execute(text("""
                INSERT INTO fr_ingestion_runs
                (run_id,provider,dataset,status,requested,received,persisted,failed,warnings,
                 effective_config_hash,started_at,finished_at)
                VALUES (:id,'EODHD','eod_splits_div','RUNNING',:requested,:received,0,0,0,:hash,:now,NULL)
                ON DUPLICATE KEY UPDATE status='RUNNING',requested=VALUES(requested),
                received=VALUES(received),finished_at=NULL
            """), {"id": run_id, "requested": summary["selected"] * 3,
                    "received": len(rows), "hash": run_key, "now": now})
        sql = text("""
            INSERT INTO fr_raw_payloads
            (run_id,provider,dataset,request_key,content_sha256,payload_uri,observed_at,available_at)
            VALUES (:run,:provider,:dataset,:request_key,:sha256,:uri,:observed,:observed)
            ON DUPLICATE KEY UPDATE raw_payload_id=raw_payload_id
        """)
        for offset in range(0, len(rows), 200):
            with engine.begin() as conn:
                conn.execute(sql, [{**row, "run": run_id} for row in rows[offset:offset + 200]])
        with engine.begin() as conn:
            stored = conn.execute(text("SELECT COUNT(*) FROM fr_raw_payloads WHERE run_id=:id"),
                                  {"id": run_id}).scalar()
            conn.execute(text("""
                UPDATE fr_ingestion_runs SET status='COMPLETED',persisted=:stored,
                finished_at=:now WHERE run_id=:id
            """), {"stored": stored, "now": datetime.now(UTC).replace(tzinfo=None), "id": run_id})
        return {"run_id": run_id, "payloads": len(rows), "stored": stored,
                "canonical_bars_written": 0}
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("artifacts/fr/eodhd/backfill_2016"))
    args = parser.parse_args()
    print(json.dumps(import_archive(args.root), ensure_ascii=False))


if __name__ == "__main__":
    main()
