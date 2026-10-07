"""Read-only gate before a prospective CN Oracle export for Dragon/Tiger D7."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from database.router import get_market_engine
from service.market.cn_dragon_tiger_matched_15d7 import (
    _timestamp, load_candidates, load_protocol, load_timely_snapshots,
)
from service.market.cn_dragon_tiger_schedule_15d6 import load_calendar


def inspect(*, snapshot_root: Path, calendar_path: Path,
            oracle_root: Path, candidate_export: Path | None = None,
            protocol_path: Path = Path("config/research_cn/sprint15d7_dragon_tiger_protocol.yaml"),
            engine=None, now: datetime | None = None) -> dict:
    calendar = load_calendar(calendar_path)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    snapshots, observations = load_timely_snapshots(
        snapshot_root, calendar, now=now, include_future_cutoffs=True,
    )
    owned_engine = engine is None
    engine = engine or get_market_engine("CN_A", database_alias="cn_primary")
    if engine.url.database != "alpha_trade_cn":
        raise RuntimeError("Oracle CN readiness refused outside alpha_trade_cn")
    try:
        with engine.connect() as connection:
            last_bar, bars_2026 = connection.execute(text(
                "SELECT MAX(date),COUNT(*) FROM stock_bars_daily "
                "WHERE market_code='CN_A' AND date >= '2026-01-01'"
            )).one()
            last_session, sessions_2026 = connection.execute(text(
                "SELECT MAX(session_date),COUNT(*) FROM market_sessions "
                "WHERE market_code='CN_A' AND session_status='open' "
                "AND session_date >= '2026-01-01'"
            )).one()
            overall_last_bar = connection.execute(text(
                "SELECT MAX(date) FROM stock_bars_daily WHERE market_code='CN_A'"
            )).scalar_one()
            overall_last_session = connection.execute(text(
                "SELECT MAX(session_date) FROM market_sessions "
                "WHERE market_code='CN_A' AND session_status='open'"
            )).scalar_one()
    finally:
        if owned_engine:
            engine.dispose()
    historical_h20 = sorted(oracle_root.glob("*/h20/*/lightgbm/predictions.parquet"))
    oof_2026 = [path for path in historical_h20 if path.parent.parent.name.startswith("2026")]
    decisions = sorted(snapshots)
    reasons = []
    if not decisions:
        reasons.append("NO_TIMELY_PROSPECTIVE_DRAGON_TIGER_SESSION")
    # A pre-open decision on J only needs the last completed event session J-1.
    # Requiring a canonical bar/session for J would look ahead to its close.
    last_event_day = max((item["event_day"] for item in snapshots.values()),
                         default="2026-01-01")
    if not sessions_2026 or not last_session or str(last_session) < last_event_day:
        reasons.append("CN_2026_DECISION_CALENDAR_MISSING")
    if not bars_2026 or not last_bar or str(last_bar) < min(
            (item["event_day"] for item in snapshots.values()), default="2026-01-01"):
        reasons.append("CN_2026_PREDECISION_BARS_MISSING")
    candidate_rows = 0
    candidate_error = None
    future_decisions = []
    if candidate_export is not None:
        try:
            candidates = load_candidates(candidate_export, load_protocol(protocol_path), snapshots)
            if any(_timestamp(value) > now for column in
                   ("score_available_at_utc", "prior_return_available_at_utc")
                   for value in candidates[column]):
                raise ValueError("Candidate availability timestamp is in the future")
            candidate_rows = len(candidates)
            future_decisions = sorted(
                day for day in candidates["decision_date"].unique()
                if snapshots[day]["cutoff_utc"] > now
            )
        except (ValueError, KeyError, OSError) as exc:
            candidate_error = f"{type(exc).__name__}: {exc}"
    if candidate_rows == 0:
        reasons.append("NO_VALID_2026_PROSPECTIVE_ORACLE_CANDIDATE_EXPORT")
    return {
        "status": ("BLOCKED_EXPORT" if reasons else
                   "WAITING_FOR_DECISION_CUTOFF" if future_decisions else
                   "INPUTS_PRESENT_REQUIRES_ARTIFACT_AND_PIT_AUDIT"),
        "reasons": reasons,
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": "alpha_trade_cn", "market_code": "CN_A",
        "observations": {key: value for key, value in observations.items() if key != "source_paths"},
        "decision_sessions": decisions,
        "future_candidate_decisions": future_decisions,
        "last_bar_2026": str(last_bar) if last_bar else None,
        "bar_rows_2026": int(bars_2026),
        "last_open_session_2026": str(last_session) if last_session else None,
        "open_sessions_2026": int(sessions_2026),
        "last_bar_overall": str(overall_last_bar) if overall_last_bar else None,
        "last_open_session_overall": str(overall_last_session) if overall_last_session else None,
        "historical_h20_oof_files": len(historical_h20),
        "h20_oof_2026_files": len(oof_2026),
        "candidate_export": str(candidate_export) if candidate_export else None,
        "candidate_rows_validated": candidate_rows,
        "candidate_validation_error": candidate_error,
        "forecast_export_created": False,
        "training_performed": False,
        "database_modified": False,
        "serving_changed": False,
        "warning": "Historical backfill cannot retroactively prove a pre-09:15 prediction. Even when inputs exist, verify model provenance and score timestamps separately.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", type=Path,
                        default=Path("artifacts/research/cn_dragon_tiger_15d6/observations"))
    parser.add_argument("--calendar", type=Path,
                        default=Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml"))
    parser.add_argument("--oracle-root", type=Path,
                        default=Path("artifacts/cn/oracle/sprint10b"))
    parser.add_argument("--candidates", type=Path,
                        help="Export prospectif 2026 conforme au contrat D7, si disponible")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        raise FileExistsError(f"Refusing to overwrite: {args.report}")
    report = inspect(snapshot_root=args.snapshot_root, calendar_path=args.calendar,
                     oracle_root=args.oracle_root, candidate_export=args.candidates)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "reasons": report["reasons"],
                      "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
