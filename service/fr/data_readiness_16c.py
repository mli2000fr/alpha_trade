"""Isolated 31-day FR warmup collection and ESMA reserve audit; no SQL/serving."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from common.market_calendar import get_market_calendar
from service.fr.eodhd_daily_15b import atomic, collect
from service.fr.operational_collectors_15c import corporate
from service.fr.operational_batch_15a import load_section
from service.fr.prediction_contract_16a import ROOT, scoped_path


def reserve_audit(root: Path = ROOT) -> dict:
    cfg = load_section("fr_security_master_sync", root / "batch_fr.yaml")
    path = scoped_path(cfg["baseline_history"], root)
    raw = path.read_bytes()
    history = json.loads(raw)
    gaps = history.get("missing_delta_days", [])
    return {"market_code": "FR_EQ", "base_path": str(path),
            "base_sha256": hashlib.sha256(raw).hexdigest(),
            "base_end": history["end"], "files_missing": history.get("missing_files", []),
            "publication_continuity_confirmed": history.get("publication_continuity_confirmed"),
            "missing_publication_days": gaps,
            "gaps_by_year": dict(sorted(Counter(day[:4] for day in gaps).items())),
            "recent_gaps_2026": [day for day in gaps if day.startswith("2026")],
            "conclusion": "UNRESOLVED_NO_AUTOMATIC_CONTINUITY_PROMOTION",
            "note": "Archive absent from index is not proof of no change; a later Full cannot certify every past day."}


def run(output: Path, end: date, *, resume=False, max_symbols=None) -> dict:
    output = output.resolve()
    allowed = (ROOT / "artifacts/fr/research/data_readiness_16c").resolve()
    if not output.is_relative_to(allowed) or output == allowed:
        raise ValueError("Isolated FR 16-C run directory required")
    calendar = get_market_calendar("FR_EQ", allow_us_weekday_fallback=False)
    now = datetime.now(UTC)
    # Do not use collect(today=...) to bypass the normal 22h safety boundary.
    safe_end = datetime.now(ZoneInfo("Europe/Paris")).date()
    if datetime.now(ZoneInfo("Europe/Paris")).hour < 22:
        from datetime import timedelta
        safe_end -= timedelta(days=1)
    if end > safe_end or calendar.session(end).close_at_utc > now:
        raise ValueError("End must be an already closed session within the normal 22h safety policy")
    if output.exists() and not resume:
        raise ValueError("Existing run: use --resume explicitly")
    output.mkdir(parents=True, exist_ok=True)
    lock = output / ".lock"
    with lock.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps({"pid": __import__("os").getpid(), "started_at": now.isoformat()}))
    report = {"market_code": "FR_EQ", "status": "RUNNING", "end_date": str(end),
              "started_at": now.isoformat(), "lookback_days": 31, "stages": {},
              "sql_writes": False, "serving_enabled": False, "orders_allowed": False}
    try:
        if resume and (output / "progress.json").exists():
            previous = json.loads((output / "progress.json").read_text(encoding="utf-8"))
            if previous.get("end_date") != str(end):
                raise ValueError("Resume end date changed")
        report["esma_reserves"] = reserve_audit()
        atomic(output / "progress.json", report)
        for stage, name, handler in (
            ("bars", "fr_daily_bars_sync", collect),
            ("actions", "fr_corporate_actions_sync", corporate),
        ):
            cfg = load_section(name, ROOT / "batch_fr.yaml")
            if not cfg.get("enabled") or cfg.get("status") not in {"ACTIVE", "ACTIVE_RESEARCH"}:
                raise ValueError("Collector disabled or blocked: " + name)
            cfg = {**cfg, "lookback_days": 31}
            stats = {"requested_count": 0, "received_count": 0, "persisted_count": 0,
                     "failed_count": 0, "warning_count": 0, "status": "RUNNING"}
            report["current_stage"] = stage
            report["stages"][stage] = stats
            atomic(output / "progress.json", report)
            print("16-C START " + stage, flush=True)
            try:
                handler(cfg, stats, root=output / ("eodhd_daily" if stage == "bars" else "corporate_actions"),
                        identities=scoped_path(cfg["identities_file"], ROOT), today=end,
                        resume=resume, max_symbols=max_symbols)
                stats["status"] = "COLLECTED_NOT_QUALIFIED"
            except Exception as exc:
                stats.update(status="FAILED", error_message=str(exc)[:500],
                             failed_count=max(1, stats["failed_count"]))
            atomic(output / "progress.json", report)
            print("16-C END " + stage + " " + stats["status"], flush=True)
        report.update(status="PARTIAL_COLLECTION" if any(s["status"] == "FAILED" for s in report["stages"].values())
                      else "COLLECTED_PENDING_QUALIFICATION",
                      finished_at=datetime.now(UTC).isoformat(), current_stage=None,
                      availability_rule="Actual observations only; historical decision dates remain unavailable",
                      next_step="Assemble a future XPAR opening after all observations; retain ESMA/identity/action reserves")
        atomic(output / "report.json", report)
        atomic(output / "progress.json", report)
        return report
    except Exception as exc:
        report.update(status="FAILED", error_message=str(exc)[:500], finished_at=datetime.now(UTC).isoformat())
        atomic(output / "report.json", report)
        atomic(output / "progress.json", report)
        raise
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--end-date", type=date.fromisoformat, required=True)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-symbols", type=int)
    args = parser.parse_args()
    report = run(args.output_dir, args.end_date, resume=args.resume, max_symbols=args.max_symbols)
    print(json.dumps({key: value for key, value in report.items() if key != "esma_reserves"}, ensure_ascii=False))
    if report["status"] != "COLLECTED_PENDING_QUALIFICATION":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
