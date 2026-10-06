"""Isolated CN database backup runner backed by batch_cn.yaml."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from scripts.backup_db import backup_db

ROOT = Path(__file__).resolve().parents[2]
BATCH_NAME = "cn_db_backup"
CN_DEST = ROOT / "backups" / "cn" / "db"


def run(*, config_path: Path = ROOT / "batch_cn.yaml", dry_run: bool = False,
        force: bool = False) -> dict:
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    cfg = config.get(BATCH_NAME)
    if not isinstance(cfg, dict):
        raise KeyError(f"Missing {BATCH_NAME} section")
    # A manual force may bypass the clock, never the restore-proof gate.
    if cfg.get("status") != "ACTIVE" and not dry_run:
        return {"batch": BATCH_NAME, "status": "SKIP_RESTORE_PROOF_REQUIRED"}
    if not cfg.get("enabled") and not force:
        return {"batch": BATCH_NAME, "status": "SKIP_DISABLED"}
    base = config_path.resolve().parent
    dest = Path(str(cfg.get("dest_dir") or ""))
    dest = dest if dest.is_absolute() else base / dest
    if (str(cfg.get("db")) != "alpha_trade_cn"
            or str(cfg.get("database_alias")) != "cn_primary"
            or str(cfg.get("archive_prefix")) != "alpha_trade_cn"
            or dest.resolve() != CN_DEST.resolve()
            or int(cfg.get("keep", 0)) < 1):
        raise ValueError("CN backup contract must target alpha_trade_cn and backups/cn/db only")
    output = Path(str(cfg.get("output_root") or "artifacts/research/cn_backup_17b"))
    output = output if output.is_absolute() else base / output
    report = {"batch": BATCH_NAME, "started_at_utc": datetime.now(UTC).isoformat(),
              "source_database": "alpha_trade_cn", "destination": str(dest),
              "archive_prefix": "alpha_trade_cn", "dry_run": dry_run,
              "requested_count": 1, "received_count": 0, "persisted_count": 0,
              "failed_count": 0, "warning_count": 0,
              "us_database_modified": False, "database_modified": False,
              "serving_changed": False}
    try:
        result = backup_db(host=str(cfg.get("host") or "localhost"), db="alpha_trade_cn",
                           dest_dir=dest, keep=int(cfg["keep"]), archive_prefix="alpha_trade_cn",
                           include_routines=True, include_triggers=True,
                           mysqldump_path=str(cfg.get("mysqldump_path") or "") or None,
                           dry_run=dry_run)
        report.update(archive=result.dump_path, archive_bytes=result.dump_size_bytes,
                      rotated_files=result.rotated_files, kept_files=result.kept_files)
        if result.errors:
            raise RuntimeError("; ".join(result.errors))
        report.update(status="DRY_RUN" if dry_run else "COMPLETED",
                      received_count=1, persisted_count=0 if dry_run else 1)
    except Exception as exc:
        report.update(status="FAILED", failed_count=1,
                      error_message=f"{type(exc).__name__}: {exc}")
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    if not dry_run:
        folder = output / "runs"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"run-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        report["report_path"] = str(path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=(BATCH_NAME,), required=True)
    parser.add_argument("--batch-config", type=Path, default=ROOT / "batch_cn.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    result = run(config_path=args.batch_config, dry_run=args.dry_run, force=args.force)
    print(json.dumps(result, ensure_ascii=False))
    if result["status"] in {"COMPLETED", "FAILED"}:
        summary = {"batch": BATCH_NAME,
                   "status": "SUCCESS" if result["status"] == "COMPLETED" else "FAILED",
                   "requested": result["requested_count"], "received": result["received_count"],
                   "persisted": result["persisted_count"], "failed": result["failed_count"],
                   "warning_count": result["warning_count"],
                   "error_message": result.get("error_message", "")}
        print("::alpha_trade_run_summary::" + json.dumps(summary, ensure_ascii=False))
    if result["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
