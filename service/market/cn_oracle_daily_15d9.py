"""Research-only CN after-close collection and next-session Oracle journal.

One run may resume existing source chunks, but never recreates a published
decision or backdates a missed forecast. No serving or trading integration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import msvcrt
import sys
import uuid
from datetime import UTC, date, datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from database.router import get_market_engine
from dataIntegrityEngine.cn_sprint7c_incremental import prepare, run_all
from modelFactory.cn_oracle_prospective_15d8 import check as oracle_check
from modelFactory.cn_oracle_prospective_15d8 import run as oracle_run
from service.market.cn_canonicalizer import read_pilot_manifest
from service.market.cn_catalog_contract_17d import validate as validate_cn_catalog
from service.market.cn_dragon_tiger_schedule_15d6 import adjacent_open, is_open, load_calendar

ROOT = Path(__file__).resolve().parents[2]
SHANGHAI = ZoneInfo("Asia/Shanghai")
BATCH_NAME = "cn_oracle_prospective_daily"


def _path(value: str | Path, *, base: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def plan(now: datetime, calendar: dict, *, earliest: time = time(18, 0)) -> dict:
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(SHANGHAI)
    if not is_open(local.date(), calendar):
        return {"status": "SKIP_CLOSED", "session": local.date().isoformat()}
    if local.time() < earliest:
        return {"status": "SKIP_BEFORE_CLOSE", "session": local.date().isoformat()}
    decision = adjacent_open(local.date(), calendar, 1)
    cutoff = datetime.combine(decision, time(9, 15), SHANGHAI)
    if now >= cutoff:
        raise RuntimeError("Next CN decision cutoff has already passed")
    return {"status": "DUE", "session": local.date().isoformat(),
            "decision": decision.isoformat(), "cutoff_utc": cutoff.astimezone(UTC).isoformat()}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_published(folder: Path, *, decision: date) -> dict:
    report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
    export = folder / "oracle_top20.parquet"
    if (report.get("status") != "PROSPECTIVE_RESEARCH_ONLY"
            or report.get("decision_date") != decision.isoformat()
            or report.get("candidate_export_sha256") != _digest(export)):
        raise RuntimeError(f"Existing Oracle export is invalid: {folder}")
    score = datetime.fromisoformat(report["score_available_at_utc"])
    published = datetime.fromisoformat(report["export_published_at_utc"])
    cutoff = datetime.fromisoformat(report["decision_cutoff_utc"])
    if not (score <= published < cutoff):
        raise RuntimeError(f"Existing Oracle export missed decision cutoff: {folder}")
    return report


def _verify_manifest_chunks(manifest: Path, chunks_root: Path) -> int:
    index = json.loads((chunks_root / "index.json").read_text(encoding="utf-8"))
    expected = read_pilot_manifest(manifest)
    chunks = index.get("chunks") or []
    if (len(expected) != index.get("symbol_count") or len(chunks) != index.get("chunk_count")
            or not chunks):
        raise RuntimeError("Incomplete CN daily chunk index")
    observed = []
    for name in chunks:
        path = chunks_root / name
        if path.resolve().parent != chunks_root.resolve():
            raise RuntimeError("CN daily chunk escapes its directory")
        observed.extend(read_pilot_manifest(path))
    if sorted(observed) != expected or len(observed) != len(expected):
        raise RuntimeError("CN daily chunks differ from the immutable manifest")
    return len(chunks)


def _write_report(root: Path, report: dict) -> Path:
    folder = root / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"run-{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{uuid.uuid4().hex[:8]}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, default=str)
    return path


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
    calendar = load_calendar(_path(cfg["calendar"], base=base))
    decision = plan(now, calendar)
    if decision["status"] != "DUE":
        return {"batch": BATCH_NAME, **decision}
    if dry_run:
        existing_folder = _path(cfg["oracle_output_root"], base=base) / decision["decision"]
        if existing_folder.exists():
            verify_published(existing_folder, decision=date.fromisoformat(decision["decision"]))
            return {"batch": BATCH_NAME, **decision, "status": "SKIP_ALREADY_PUBLISHED",
                    "database_modified": False, "training_performed": False,
                    "serving_changed": False}
        return {"batch": BATCH_NAME, **decision, "database_modified": False,
                "training_performed": False, "serving_changed": False}

    session = date.fromisoformat(decision["session"])
    decision_day = date.fromisoformat(decision["decision"])
    output_root = _path(cfg["output_root"], base=base)
    oracle_folder = _path(cfg["oracle_output_root"], base=base) / decision["decision"]
    output_root.mkdir(parents=True, exist_ok=True)
    lock_path = output_root / f"{session}.lock"
    with lock_path.open("a+b") as lock:
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            raise RuntimeError("Another CN Oracle daily run is active") from exc
        try:
            return _execute_locked(cfg, base, output_root, oracle_folder,
                                   session, decision_day, decision, catalog_identity)
        finally:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)


def _execute_locked(cfg: dict, base: Path, output_root: Path, oracle_folder: Path,
                    session: date, decision_day: date, decision: dict,
                    catalog_identity: dict) -> dict:
    report = {"batch": BATCH_NAME, "session": session.isoformat(),
              **catalog_identity,
              "decision": decision_day.isoformat(), "cutoff_utc": decision["cutoff_utc"],
              "started_at_utc": datetime.now(UTC).isoformat(),
              "database_modified": False, "training_performed": False,
              "serving_changed": False, "trading_enabled": False,
              "requested_count": 0, "received_count": 0, "persisted_count": 0,
              "failed_count": 0, "warning_count": 0}
    try:
        if oracle_folder.exists():
            existing = verify_published(oracle_folder, decision=decision_day)
            report.update(status="SKIP_ALREADY_PUBLISHED", existing_export=str(oracle_folder),
                          existing_candidates=int(existing["quality"]["top20"]))
        else:
            manifest = _path(cfg["manifest_root"], base=base) / f"canonical_incremental_{session}.txt"
            chunks_root = _path(cfg["chunks_root"], base=base) / session.isoformat()
            collection_root = _path(cfg["collection_root"], base=base) / session.isoformat()
            if manifest.exists() != chunks_root.exists():
                raise RuntimeError("Daily CN manifest/chunks partially prepared; manual audit required")
            engine = get_market_engine("CN_A", database_alias="cn_primary")
            if engine.url.database != "alpha_trade_cn":
                raise RuntimeError("CN daily collection refused outside alpha_trade_cn")
            try:
                if not manifest.exists():
                    prepare(engine, start=session, end=session, manifest=manifest,
                            chunks_root=chunks_root, chunk_size=int(cfg.get("chunk_size", 25)),
                            seed_manifest=_path(cfg["seed_manifest"], base=base),
                            allow_same_day_after_close=True)
                chunks = _verify_manifest_chunks(manifest, chunks_root)
                collection = run_all(engine, start=session, end=session,
                                     chunks_root=chunks_root, output_root=collection_root,
                                     allow_same_day_after_close=True)
            finally:
                engine.dispose()
            report.update(requested_count=len(read_pilot_manifest(manifest)),
                          collection_chunks=chunks, collection_state=collection["state"],
                          completed_chunks=collection["completed_chunks"])
            if collection["status"] != "COMPLETED" or collection["completed_chunks"] != chunks:
                raise RuntimeError("CN daily source collection is incomplete")
            preflight = oracle_check(decision_day=decision_day)
            report["preflight"] = preflight
            report["received_count"] = int(preflight["known_bar_rows"])
            if preflight["status"] != "READY_TO_SCORE":
                raise RuntimeError(f"CN Oracle preflight blocked: {preflight['reasons']}")
            result = oracle_run(decision_day=decision_day)
            published = verify_published(oracle_folder, decision=decision_day)
            report.update(status="COMPLETED_RESEARCH_ONLY",
                          candidate_export=published["candidate_export"],
                          persisted_count=int(result["quality"]["top20"]),
                          score_available_at_utc=published["score_available_at_utc"])
    except Exception as exc:
        report.update(status="FAILED", failed_count=1,
                      error_message=f"{type(exc).__name__}: {exc}")
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    report["report_path"] = str(_write_report(output_root, report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch", choices=(BATCH_NAME,), required=True)
    parser.add_argument("--batch-config", type=Path, default=ROOT / "batch.yaml")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--probe", action="store_true",
                        help="Read-only scheduler preflight; exit 10 when not due")
    args = parser.parse_args()
    # BaoStock's SDK prints Chinese transport errors; do not mask a network
    # failure with the Windows cp1252 console encoding.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    result = execute(batch_config=args.batch_config, dry_run=args.dry_run or args.probe)
    print(json.dumps(result, ensure_ascii=False, default=str))
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
