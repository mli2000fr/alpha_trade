"""Scheduled research observations of SSE/SZSE Dragon/Tiger, never serving."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from service.market.cn_catalog_contract_17d import validate as validate_cn_catalog
from service.market.cn_dragon_tiger_prospective_15d5 import prior_observations
from service.market.cn_dragon_tiger_prospective_15d5 import run as collect

SHANGHAI = ZoneInfo("Asia/Shanghai")
BATCHES = {
    "cn_dragon_tiger_after_close": "after_close",
    "cn_dragon_tiger_before_open": "before_open",
}


def load_calendar(path: Path) -> dict:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if raw.get("market_code") != "CN_A" or raw.get("timezone") != "Asia/Shanghai":
        raise ValueError("CN calendar identity invalid")
    year = int(raw["year"])
    closed = set()
    for start, end in raw.get("closed_ranges", []):
        start_day = date.fromisoformat(str(start))
        end_day = date.fromisoformat(str(end))
        if end_day < start_day or start_day.year != year or end_day.year != year:
            raise ValueError("CN calendar range invalid")
        cursor = start_day
        while cursor <= end_day:
            closed.add(cursor)
            cursor += timedelta(days=1)
    return {"year": year, "closed": closed, "source": str(path)}


def is_open(day: date, calendar: dict) -> bool:
    if day.year != calendar["year"]:
        raise RuntimeError(f"No verified CN calendar for {day.year}")
    return day.weekday() < 5 and day not in calendar["closed"]


def adjacent_open(day: date, calendar: dict, direction: int) -> date:
    if direction not in (-1, 1):
        raise ValueError("direction must be -1 or 1")
    for offset in range(1, 16):
        candidate = day + timedelta(days=direction * offset)
        if is_open(candidate, calendar):
            return candidate
    raise RuntimeError("No adjacent open CN session within 15 days")


def plan(batch_name: str, cfg: dict, calendar: dict, now: datetime,
         *, force: bool = False) -> dict:
    if batch_name not in BATCHES:
        raise ValueError(f"Unknown CN research batch {batch_name}")
    if not cfg.get("enabled") or cfg.get("status") != "RESEARCH_ONLY":
        return {"status": "SKIP_DISABLED"}
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    local = now.astimezone(SHANGHAI)
    if not force and (local.hour != int(cfg["run_hours"])
                      or not int(cfg["run_minutes"]) <= local.minute <= int(cfg["run_minutes"]) + 15):
        return {"status": "SKIP_WINDOW"}
    if not is_open(local.date(), calendar):
        return {"status": "SKIP_CLOSED"}
    phase = BATCHES[batch_name]
    if phase == "after_close":
        if local.time() < time(15, 0):
            return {"status": "SKIP_BEFORE_MARKET_CLOSE"}
        target, next_session = local.date(), adjacent_open(local.date(), calendar, 1)
    else:
        if local.time() >= time(9, 15):
            return {"status": "SKIP_AFTER_DECISION_CUTOFF"}
        target, next_session = adjacent_open(local.date(), calendar, -1), local.date()
    cutoff = datetime.combine(next_session, time(9, 15), SHANGHAI)
    return {"status": "DUE", "phase": phase, "target_session": target.isoformat(),
            "next_open_session": next_session.isoformat(),
            "decision_cutoff_shanghai": cutoff.isoformat(),
            "scheduled": not force, "calendar_year": calendar["year"]}


def _write_report(output_root: Path, report: dict) -> Path:
    folder = output_root / "runs"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    path = folder / f"run-{stamp}-{uuid.uuid4().hex[:8]}.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    return path


def execute(batch_name: str, batch_config: Path, calendar_path: Path,
            *, now: datetime | None = None, force: bool = False,
            probe: bool = False) -> dict:
    raw = yaml.safe_load(batch_config.read_text(encoding="utf-8")) or {}
    cfg = raw.get(batch_name)
    if not isinstance(cfg, dict):
        raise KeyError(f"Missing batch.yaml section {batch_name}")
    catalog_identity = validate_cn_catalog(batch_config, raw, batch_name)
    calendar = load_calendar(calendar_path)
    now = now or datetime.now(UTC)
    decision = plan(batch_name, cfg, calendar, now, force=force)
    if decision["status"] != "DUE":
        return {"status": decision["status"], "batch": batch_name}
    root = Path(cfg["output_root"])
    if not root.is_absolute():
        root = batch_config.resolve().parent / root
    target = date.fromisoformat(decision["target_session"])
    previous = prior_observations(root / target.isoformat())
    same_phase = [
        item for item in previous
        if (item.get("collection_context") or {}).get("phase") == decision["phase"]
        and int((item.get("counts") or {}).get("events") or 0) > 0
    ]
    if same_phase and not force:
        return {"status": "SKIP_ALREADY_CAPTURED", "batch": batch_name,
                "target_session": target.isoformat()}
    if probe:
        return {"status": "DUE", "batch": batch_name,
                "target_session": target.isoformat()}
    started = datetime.now(UTC)
    report = {"batch": batch_name, "phase": decision["phase"],
              **catalog_identity,
              "target_session": target.isoformat(),
              "next_open_session": decision["next_open_session"],
              "decision_cutoff_shanghai": decision["decision_cutoff_shanghai"],
              "started_at_utc": started.isoformat(), "status": "RUNNING",
              "rights_status": "RESEARCH_REVIEW_PENDING",
              "historical_pit_certified": False, "ml_serving_changed": False}
    try:
        snapshot_path = collect(target, root, collection_context=decision)
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        observed = datetime.fromisoformat(snapshot["observed_at_utc"])
        cutoff = datetime.fromisoformat(decision["decision_cutoff_shanghai"])
        timely = observed < cutoff
        count = int(snapshot["counts"]["events"])
        report.update({"snapshot": str(snapshot_path),
                       "requested_count": 2, "received_count": count,
                       "persisted_count": count, "failed_count": 0,
                       "warning_count": int(not timely or count == 0),
                       "observed_before_decision_cutoff": timely,
                       "corrections": snapshot["counts"]})
        report["status"] = ("COMPLETED_RESEARCH_ONLY" if timely and count > 0
                            else "FAILED_EMPTY_OR_LATE")
    except Exception as exc:
        report.update({"status": "FAILED", "requested_count": 2,
                       "received_count": 0, "persisted_count": 0,
                       "failed_count": 1, "warning_count": 0,
                       "error_message": f"{type(exc).__name__}: {exc}"})
    report["finished_at_utc"] = datetime.now(UTC).isoformat()
    report["report_path"] = str(_write_report(root, report))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-name", choices=tuple(BATCHES), required=True)
    parser.add_argument("--batch-config", type=Path, default=Path("batch.yaml"))
    parser.add_argument("--calendar", type=Path,
                        default=Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml"))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    result = execute(args.batch_name, args.batch_config, args.calendar,
                     force=args.force or os.environ.get("CN_DRAGON_TIGER_FORCE") == "1",
                     probe=args.probe)
    if args.probe:
        raise SystemExit(0 if result["status"] == "DUE" else 10)
    print(json.dumps(result, ensure_ascii=False, default=str))
    if result["status"] not in {"SKIP_WINDOW", "SKIP_CLOSED", "SKIP_DISABLED",
                                "SKIP_BEFORE_MARKET_CLOSE", "SKIP_AFTER_DECISION_CUTOFF",
                                "SKIP_ALREADY_CAPTURED"}:
        summary = {
            "batch": args.batch_name,
            "status": "FAILED" if result["status"].startswith("FAILED") else "SUCCESS",
            "requested": result.get("requested_count", 0),
            "received": result.get("received_count", 0),
            "persisted": result.get("persisted_count", 0),
            "failed": result.get("failed_count", 0),
            "warning_count": result.get("warning_count", 0),
            "error_message": result.get("error_message", ""),
            "phase": result.get("phase", ""),
        }
        print("::alpha_trade_run_summary::" + json.dumps(summary, ensure_ascii=False))
    if result["status"] in {"FAILED", "FAILED_EMPTY_OR_LATE"}:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
