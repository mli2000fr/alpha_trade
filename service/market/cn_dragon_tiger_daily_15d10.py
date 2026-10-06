"""Prospective, outcome-blind daily D7 matching after the CN decision cutoff.

This research journal only pairs a timely Oracle export with a timely official
Dragon/Tiger snapshot. It never reads future returns, labels or trading state.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from service.market.cn_catalog_contract_17d import validate as validate_cn_catalog
from service.market.cn_dragon_tiger_matched_15d7 import _digest, audit
from service.market.cn_dragon_tiger_schedule_15d6 import is_open, load_calendar
from service.market.cn_oracle_daily_15d9 import verify_published

ROOT = Path(__file__).resolve().parents[2]
SHANGHAI = ZoneInfo("Asia/Shanghai")
BATCH_NAME = "cn_dragon_tiger_daily_match"


def _path(value: str | Path, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def plan(now: datetime, calendar: dict) -> dict:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(SHANGHAI)
    session = local.date().isoformat()
    if not is_open(local.date(), calendar):
        return {"status": "SKIP_CLOSED", "session": session}
    if local.time() < time(9, 20):
        return {"status": "SKIP_BEFORE_CUTOFF", "session": session}
    return {"status": "DUE", "session": session}


def execute(*, batch_config: Path = ROOT / "batch.yaml", now: datetime | None = None,
            dry_run: bool = False) -> dict:
    config = yaml.safe_load(batch_config.read_text(encoding="utf-8")) or {}
    cfg = config.get(BATCH_NAME)
    if not isinstance(cfg, dict):
        raise KeyError(f"Missing batch.yaml section {BATCH_NAME}")
    catalog_identity = validate_cn_catalog(batch_config, config, BATCH_NAME)
    if not cfg.get("enabled") or cfg.get("status") != "RESEARCH_ONLY":
        return {"batch": BATCH_NAME, "status": "SKIP_DISABLED"}
    base = batch_config.resolve().parent
    now = now or datetime.now(UTC)
    scheduled = plan(now, load_calendar(_path(cfg["calendar"], base)))
    if scheduled["status"] != "DUE":
        return {"batch": BATCH_NAME, **scheduled}
    session = scheduled["session"]
    oracle_folder = _path(cfg["oracle_output_root"], base) / session
    candidate_path = oracle_folder / "oracle_top20.parquet"
    output = _path(cfg["output_root"], base) / session
    if (output / "report.json").exists():
        existing = json.loads((output / "report.json").read_text(encoding="utf-8"))
        if (existing.get("candidate_sha256") !=
                verify_published(oracle_folder, decision=now.astimezone(SHANGHAI).date())
                ["candidate_export_sha256"]
                or existing.get("outcomes_loaded") is not False
                or existing.get("database_modified") is not False
                or not (output / "outcome_blind_matches.parquet").exists()):
            raise RuntimeError(f"Existing D7 report/candidate mismatch: {output}")
        return {"batch": BATCH_NAME, **scheduled, "status": "SKIP_ALREADY_MATCHED",
                "database_modified": False, "serving_changed": False}
    if dry_run:
        return {"batch": BATCH_NAME, **scheduled, "candidate_exists": candidate_path.exists(),
                "database_modified": False, "serving_changed": False}

    root = _path(cfg["output_root"], base)
    ledger = root / "runs"
    ledger.mkdir(parents=True, exist_ok=True)
    report = {"batch": BATCH_NAME, "session": session,
              **catalog_identity,
              "started_at_utc": datetime.now(UTC).isoformat(),
              "requested_count": 0, "received_count": 0, "persisted_count": 0,
              "failed_count": 0, "warning_count": 0,
              "database_modified": False, "training_performed": False,
              "serving_changed": False, "trading_enabled": False}
    try:
        published = verify_published(oracle_folder, decision=now.astimezone(SHANGHAI).date())
        report["requested_count"] = int(published["quality"]["top20"])
        result = audit(
            snapshot_root=_path(cfg["snapshot_root"], base),
            calendar_path=_path(cfg["calendar"], base),
            protocol_path=_path(cfg["protocol"], base),
            candidates_path=candidate_path, output=output, now=now,
        )
        report.update(status="COMPLETED_RESEARCH_ONLY", matching_status=result["status"],
                      received_count=int(result["matching"]["candidate_rows"]),
                      persisted_count=int(result["matching"]["matched_pairs"]),
                      candidate_sha256=published["candidate_export_sha256"],
                      d7_report=str(output / "report.json"),
                      d7_report_sha256=_digest(output / "report.json"),
                      d7_pairs_sha256=_digest(output / "outcome_blind_matches.parquet"))
    except Exception as exc:
        report.update(status="FAILED", failed_count=1,
                      error_message=f"{type(exc).__name__}: {exc}")
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    path = ledger / f"run-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    report["report_path"] = str(path)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=(BATCH_NAME,), required=True)
    parser.add_argument("--batch-config", type=Path, default=ROOT / "batch.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    result = execute(batch_config=args.batch_config, dry_run=args.dry_run or args.probe)
    print(json.dumps(result, ensure_ascii=False))
    if args.probe:
        raise SystemExit(0 if result["status"] == "DUE" else 10)
    if result["status"] in {"COMPLETED_RESEARCH_ONLY", "FAILED"}:
        summary = {"batch": BATCH_NAME,
                   "status": "FAILED" if result["status"] == "FAILED" else "SUCCESS",
                   "requested": result["requested_count"], "received": result["received_count"],
                   "persisted": result["persisted_count"], "failed": result["failed_count"],
                   "warning_count": result["warning_count"],
                   "error_message": result.get("error_message", "")}
        print("::alpha_trade_run_summary::" + json.dumps(summary, ensure_ascii=False))
    if result["status"] == "FAILED":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
