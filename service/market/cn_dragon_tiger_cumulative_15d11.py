"""Outcome-blind cumulative readiness audit of prospective CN D7 daily matches.

No future labels, returns, database writes, model fitting or serving changes.
Only immutable D8 exports and D10 daily matching artifacts are admitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from service.market.cn_dragon_tiger_matched_15d7 import load_protocol
from service.market.cn_oracle_daily_15d9 import verify_published

ROOT = Path(__file__).resolve().parents[2]
SHANGHAI = ZoneInfo("Asia/Shanghai")
FORBIDDEN = {"oracle_decile", "realized_decile", "future_return", "target", "label", "d1", "d10"}
PAIR_COLUMNS = {
    "decision_date", "exposed_exchange", "exposed_code", "control_exchange", "control_code",
    "exposed_score_rank", "control_score_rank", "exposed_prior_return_5d", "control_prior_return_5d",
}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _standardized_difference(pairs: pd.DataFrame, column: str) -> float | None:
    if pairs.empty:
        return None
    left = pairs[f"exposed_{column}"].astype(float)
    right = pairs[f"control_{column}"].astype(float)
    scale = math.sqrt((left.var(ddof=0) + right.var(ddof=0)) / 2)
    if scale == 0:
        return 0.0 if float(left.mean()) == float(right.mean()) else None
    return abs(float(left.mean() - right.mean())) / scale


def inspect(*, daily_root: Path, oracle_root: Path, protocol_path: Path,
            now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    protocol = load_protocol(protocol_path)
    protocol_sha = _digest(protocol_path)
    available: dict[str, dict] = {}
    for folder in sorted(oracle_root.iterdir()) if oracle_root.exists() else []:
        if not folder.is_dir() or not (folder / "report.json").exists():
            continue
        try:
            day = datetime.strptime(folder.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day > now.astimezone(SHANGHAI).date():
            continue
        published = verify_published(folder, decision=day)
        cutoff = datetime.fromisoformat(published["decision_cutoff_utc"])
        if cutoff <= now:
            available[day.isoformat()] = published

    daily: list[dict] = []
    frames: list[pd.DataFrame] = []
    completed_ledgers: dict[str, dict] = {}
    for ledger_path in sorted((daily_root / "runs").glob("run-*.json")):
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger.get("status") != "COMPLETED_RESEARCH_ONLY":
            continue
        day = str(ledger.get("session"))
        if day in completed_ledgers:
            raise RuntimeError(f"Duplicate completed D10 ledger: {day}")
        completed_ledgers[day] = ledger
    for folder in sorted(daily_root.iterdir()) if daily_root.exists() else []:
        if not folder.is_dir() or not (folder / "report.json").exists():
            continue
        day = folder.name
        if day not in available:
            raise RuntimeError(f"D10 day has no eligible, cutoff-passed D8 export: {day}")
        report_path = folder / "report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        candidate = oracle_root / day / "oracle_top20.parquet"
        if (report.get("protocol_sha256") != protocol_sha
                or report.get("candidate_sha256") != available[day]["candidate_export_sha256"]
                or Path(report.get("candidate_path", "")).resolve() != candidate.resolve()
                or report.get("outcomes_loaded") is not False
                or report.get("training_performed") is not False
                or report.get("database_modified") is not False
                or report.get("serving_changed") is not False):
            raise RuntimeError(f"D10 provenance or outcome-blind contract invalid: {day}")
        metrics = report.get("matching") or {}
        if (int(metrics.get("open_sessions", -1)) != 1
                or int(metrics.get("candidate_rows", -1)) != int(available[day]["quality"]["top20"])):
            raise RuntimeError(f"D10 candidate population invalid: {day}")
        pairs_path = folder / "outcome_blind_matches.parquet"
        ledger = completed_ledgers.get(day)
        if (ledger is None or ledger.get("d7_report_sha256") != _digest(report_path)
                or ledger.get("d7_pairs_sha256") != _digest(pairs_path)
                or ledger.get("candidate_sha256") != available[day]["candidate_export_sha256"]):
            raise RuntimeError(f"D10 immutable file ledger mismatch: {day}")
        pairs = pd.read_parquet(pairs_path)
        leaked = [column for column in pairs.columns
                  if str(column).lower() in FORBIDDEN
                  or str(column).lower().startswith(("future_", "realized_", "target_", "label_"))]
        if leaked:
            raise RuntimeError(f"Future outcome column in D10 pairs: {day}")
        if len(pairs):
            if not PAIR_COLUMNS <= set(pairs.columns) or set(pairs["decision_date"].astype(str)) != {day}:
                raise RuntimeError(f"D10 pair schema or date invalid: {day}")
            for column in ("exposed_score_rank", "control_score_rank",
                           "exposed_prior_return_5d", "control_prior_return_5d"):
                if not pairs[column].map(lambda value: math.isfinite(float(value))).all():
                    raise RuntimeError(f"Non-finite D10 matching covariate: {day}/{column}")
            key = ["decision_date", "exposed_exchange", "exposed_code", "control_exchange", "control_code"]
            if pairs.duplicated(key).any():
                raise RuntimeError(f"Duplicate D10 matched pair: {day}")
            frames.append(pairs)
        matched_exposed = (len(pairs[["exposed_exchange", "exposed_code"]].drop_duplicates())
                           if len(pairs) else 0)
        if (len(pairs) != int(metrics.get("matched_pairs", -1))
                or matched_exposed != int(metrics.get("matched_exposed", -1))):
            raise RuntimeError(f"D10 report/pair count mismatch: {day}")
        daily.append({"decision_date": day, "candidate_rows": int(metrics["candidate_rows"]),
                      "exposed_candidates": int(metrics["exposed_candidates"]),
                      "matched_exposed": matched_exposed, "matched_pairs": len(pairs),
                      "d7_report_sha256": _digest(report_path),
                      "d7_pairs_sha256": _digest(pairs_path),
                      "oracle_export_sha256": available[day]["candidate_export_sha256"]})

    missing = sorted(set(available) - {item["decision_date"] for item in daily})
    pooled = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    exposed = sum(item["exposed_candidates"] for item in daily)
    matched = sum(item["matched_exposed"] for item in daily)
    quarters = sorted({f"{item['decision_date'][:4]}Q{(int(item['decision_date'][5:7]) - 1) // 3 + 1}"
                       for item in daily if item["matched_exposed"]})
    balance = {column: _standardized_difference(pooled, column)
               for column in ("score_rank", "prior_return_5d")}
    gates = protocol["readiness_gates"]
    checks = {
        "open_sessions": len(daily) >= int(gates["minimum_open_sessions"]),
        "exposed_candidates": exposed >= int(gates["minimum_exposed_candidates"]),
        "matched_fraction": exposed > 0 and matched / exposed >= float(gates["minimum_matched_fraction"]),
        "calendar_quarters": len(quarters) >= int(gates["minimum_calendar_quarters"]),
        "match_balance": all(value is not None and value <= float(gates["maximum_absolute_standardized_difference"])
                             for value in balance.values()),
        "journal_complete": not missing,
    }
    status = ("INCOMPLETE_PROSPECTIVE_JOURNAL" if missing else
              "WAITING_FOR_FIRST_PROSPECTIVE_MATCH" if not daily else
              "MATCHING_READY_FOR_SEPARATE_OUTCOME_AUDIT" if all(checks.values()) else
              "INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE")
    return {"status": status, "checked_at_utc": now.astimezone(UTC).isoformat(),
            "protocol_id": protocol["protocol_id"], "protocol_sha256": protocol_sha,
            "decision_sessions": len(daily), "candidate_rows": sum(item["candidate_rows"] for item in daily),
            "exposed_candidates": exposed, "matched_exposed": matched,
            "matched_pairs": sum(item["matched_pairs"] for item in daily),
            "matched_fraction": matched / exposed if exposed else None,
            "calendar_quarters": quarters, "absolute_standardized_differences": balance,
            "eligible_oracle_decisions": sorted(available), "missing_daily_matches": missing,
            "gate_thresholds": gates, "gate_checks": checks, "daily": daily,
            "outcomes_loaded": False, "training_performed": False,
            "database_modified": False, "serving_changed": False,
            "trading_enabled": False, "historical_pit_certified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--daily-root", type=Path,
                        default=ROOT / "artifacts/research/cn_dragon_tiger_15d10")
    parser.add_argument("--oracle-root", type=Path,
                        default=ROOT / "artifacts/research/cn_oracle_prospective_15d8")
    parser.add_argument("--protocol", type=Path,
                        default=ROOT / "config/research_cn/sprint15d7_dragon_tiger_protocol.yaml")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite cumulative D7 report: {args.output}")
    result = inspect(daily_root=args.daily_root, oracle_root=args.oracle_root,
                     protocol_path=args.protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({"status": result["status"], "decision_sessions": result["decision_sessions"],
                      "missing_daily_matches": len(result["missing_daily_matches"]),
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
