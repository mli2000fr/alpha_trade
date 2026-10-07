"""Pre-registered, outcome-blind CN Dragon/Tiger matching audit.

The journal is research-only. This module never loads future labels, trains a
model, writes to a database, or marks historical data as PIT-certified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import yaml

from service.market.cn_dragon_tiger_schedule_15d6 import adjacent_open, load_calendar

SHANGHAI = ZoneInfo("Asia/Shanghai")
REQUIRED_CANDIDATE_COLUMNS = {
    "decision_date", "exchange", "code", "board_code", "oracle_score",
    "prior_return_5d", "oracle_top20", "oracle_oos",
    "score_available_at_utc", "prior_return_available_at_utc",
    "model_trained_through",
}


def _digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_protocol(path: Path) -> dict:
    protocol = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if protocol.get("protocol_id") != "CN_DRAGON_TIGER_15D7_V1":
        raise ValueError("Unknown D7 protocol")
    if protocol.get("status") != "PREREGISTERED_RESEARCH_ONLY":
        raise ValueError("D7 protocol must remain research-only")
    matching = protocol["matching"]
    if not (0 < float(matching["score_rank_caliper"]) <= 1
            and 0 < float(matching["prior_return_5d_caliper"]) <= 1
            and int(matching["max_controls_per_exposed"]) >= 1
            and matching["control_reuse"] is False):
        raise ValueError("Invalid fixed D7 matching contract")
    return protocol


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Timestamp without timezone")
    return parsed.astimezone(timezone.utc)


def _boolean(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if str(value).strip().lower() in {"true", "1"}:
        return True
    if str(value).strip().lower() in {"false", "0"}:
        return False
    raise ValueError("Invalid candidate boolean value")


def load_timely_snapshots(root: Path, calendar: dict, *, now: datetime | None = None,
                          include_future_cutoffs: bool = False) -> tuple[dict, dict]:
    """Select the latest complete official snapshot actually seen before 09:15.

    An absent session is unknown, never silently interpreted as no event.
    The optional future-cutoff view is for read-only contract preview only;
    the matching audit uses the fail-closed default.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware")
    selected: dict[str, dict] = {}
    stats = {"snapshot_files": 0, "timely_files": 0, "late_files": 0,
             "future_cutoffs": 0, "sessions": 0, "reason_rows": 0,
             "unique_event_symbols": 0, "revisions": 0, "source_paths": []}
    for path in sorted(root.glob("*/snapshot-*.json")):
        item = json.loads(path.read_text(encoding="utf-8"))
        stats["snapshot_files"] += 1
        if item.get("schema") != "cn_dragon_tiger_observation_v1":
            raise ValueError(f"Unrecognized snapshot schema: {path}")
        if item.get("source") != "SSE_SSE_STAR_SZSE_OFFICIAL":
            raise ValueError(f"Non-official source: {path}")
        if set((item.get("provenance") or {})) != {"sse", "szse"}:
            raise ValueError(f"Incomplete exchange provenance: {path}")
        events = item.get("events")
        if not isinstance(events, list) or len(events) != int((item.get("counts") or {}).get("events", -1)):
            raise ValueError(f"Corrupt snapshot event count: {path}")
        context = item.get("collection_context") or {}
        event_day = date.fromisoformat(item["trade_date"])
        if context.get("target_session") != event_day.isoformat() or context.get("phase") not in {"after_close", "before_open"}:
            raise ValueError(f"Invalid collection context: {path}")
        decision_day = date.fromisoformat(context["next_open_session"])
        if adjacent_open(event_day, calendar, 1) != decision_day:
            raise ValueError(f"Non-adjacent decision session: {path}")
        cutoff = datetime.combine(decision_day, time(9, 15), SHANGHAI)
        if _timestamp(context["decision_cutoff_shanghai"]) != cutoff.astimezone(timezone.utc):
            raise ValueError(f"Decision cutoff mismatch: {path}")
        observed = _timestamp(item["observed_at_utc"])
        if observed > now.astimezone(timezone.utc):
            raise ValueError(f"Future observation timestamp: {path}")
        if cutoff > now.astimezone(SHANGHAI):
            stats["future_cutoffs"] += 1
            if not include_future_cutoffs:
                continue
        if observed >= cutoff.astimezone(timezone.utc):
            stats["late_files"] += 1
            continue
        keys = set()
        for event in events:
            if event.get("date") != event_day.isoformat() or event.get("exchange") not in {"SSE", "SZSE"}:
                raise ValueError(f"Invalid event identity: {path}")
            code = str(event.get("code") or "")
            if len(code) != 6 or not code.isdigit():
                raise ValueError(f"Invalid event code: {path}")
            if _timestamp(event["first_seen_at_utc"]) > observed:
                raise ValueError(f"Event first-seen after snapshot: {path}")
            keys.add((event["exchange"], code))
        stats["timely_files"] += 1
        stats["source_paths"].append({"path": str(path), "sha256": _digest(path)})
        key = decision_day.isoformat()
        previous = selected.get(key)
        if previous is None or observed > previous["observed_at_utc"]:
            if previous is not None:
                stats["revisions"] += 1
            selected[key] = {"event_day": event_day.isoformat(),
                             "observed_at_utc": observed,
                             "cutoff_utc": cutoff.astimezone(timezone.utc),
                             "event_symbols": keys, "reason_rows": len(events),
                             "snapshot": str(path)}
        elif observed == previous["observed_at_utc"]:
            raise ValueError(f"Ambiguous simultaneous snapshots: {path}")
    stats["sessions"] = len(selected)
    stats["reason_rows"] = sum(item["reason_rows"] for item in selected.values())
    stats["unique_event_symbols"] = sum(len(item["event_symbols"]) for item in selected.values())
    return selected, stats


def load_candidates(path: Path, protocol: dict, snapshots: dict) -> pd.DataFrame:
    frame = pd.read_parquet(path) if path.suffix.lower() == ".parquet" else pd.read_csv(path)
    missing = REQUIRED_CANDIDATE_COLUMNS - set(frame.columns)
    if missing:
        raise ValueError(f"Candidate columns missing: {sorted(missing)}")
    forbidden = {str(value).lower() for value in protocol["candidate_contract"]["forbidden_columns"]}
    leaked = [column for column in frame.columns if str(column).lower() in forbidden
              or str(column).lower().startswith(("future_", "realized_", "target_", "label_"))]
    if leaked:
        raise ValueError(f"Outcome-bearing candidate columns forbidden: {leaked}")
    if frame.empty:
        raise ValueError("No Oracle TOP20 candidates")
    out = frame[list(REQUIRED_CANDIDATE_COLUMNS)].copy()
    out["decision_date"] = pd.to_datetime(out["decision_date"]).dt.date.astype(str)
    out["code"] = out["code"].astype(str).str.zfill(6)
    if out.duplicated(["decision_date", "exchange", "code"]).any():
        raise ValueError("Duplicate Oracle candidate identity")
    if not out["exchange"].isin(["SSE", "SZSE"]).all() or not out["code"].str.fullmatch(r"\d{6}").all():
        raise ValueError("Invalid CN candidate identity")
    if not out["oracle_top20"].map(_boolean).all() or not out["oracle_oos"].map(_boolean).all():
        raise ValueError("Candidates must be Oracle TOP20 and genuinely OOS")
    for column in ("oracle_score", "prior_return_5d"):
        out[column] = pd.to_numeric(out[column], errors="raise")
        if not out[column].map(math.isfinite).all():
            raise ValueError(f"Non-finite {column}")
    if out["board_code"].isna().any() or out["board_code"].astype(str).eq("").any():
        raise ValueError("Missing board_code")
    if set(out["decision_date"]) - set(snapshots):
        raise ValueError("Missing complete timely snapshots for candidate decisions")
    for row in out.itertuples(index=False):
        cutoff = snapshots[row.decision_date]["cutoff_utc"]
        if _timestamp(row.score_available_at_utc) >= cutoff or _timestamp(row.prior_return_available_at_utc) >= cutoff:
            raise ValueError("Oracle score or prior return unavailable before decision")
        if date.fromisoformat(str(row.model_trained_through)[:10]) >= date.fromisoformat(row.decision_date):
            raise ValueError("Model trained on or after decision date")
    out["exposed"] = [
        (row.exchange, row.code) in snapshots[row.decision_date]["event_symbols"]
        for row in out.itertuples(index=False)
    ]
    out["score_rank"] = out.groupby("decision_date")["oracle_score"].rank(method="average", pct=True)
    return out.sort_values(["decision_date", "board_code", "exchange", "code"], kind="stable")


def match_candidates(frame: pd.DataFrame, protocol: dict) -> tuple[pd.DataFrame, dict]:
    """Deterministic nearest matching, with no outcomes and no control reuse."""
    params = protocol["matching"]
    score_limit = float(params["score_rank_caliper"])
    return_limit = float(params["prior_return_5d_caliper"])
    max_controls = int(params["max_controls_per_exposed"])
    rows = []
    for (day, board), group in frame.groupby(["decision_date", "board_code"], sort=True):
        exposed = group.loc[group["exposed"]]
        controls = group.loc[~group["exposed"]]
        used = set()
        for treated in exposed.itertuples(index=False):
            choices = []
            for control in controls.itertuples(index=False):
                key = (control.exchange, control.code)
                score_gap = abs(float(treated.score_rank) - float(control.score_rank))
                return_gap = abs(float(treated.prior_return_5d) - float(control.prior_return_5d))
                if key not in used and score_gap <= score_limit and return_gap <= return_limit:
                    choices.append((score_gap / score_limit + return_gap / return_limit,
                                    score_gap, return_gap, control.exchange, control.code, control))
            for _, score_gap, return_gap, _, _, control in sorted(choices)[:max_controls]:
                used.add((control.exchange, control.code))
                rows.append({"decision_date": day, "board_code": board,
                             "exposed_exchange": treated.exchange, "exposed_code": treated.code,
                             "control_exchange": control.exchange, "control_code": control.code,
                             "exposed_score_rank": float(treated.score_rank),
                             "control_score_rank": float(control.score_rank),
                             "exposed_prior_return_5d": float(treated.prior_return_5d),
                             "control_prior_return_5d": float(control.prior_return_5d),
                             "score_rank_gap": score_gap, "prior_return_gap": return_gap})
    matches = pd.DataFrame(rows)
    exposed_count = int(frame["exposed"].sum())
    matched = (int(matches[["decision_date", "exposed_exchange", "exposed_code"]]
                   .drop_duplicates().shape[0]) if not matches.empty else 0)
    return matches, {"candidate_rows": int(len(frame)), "open_sessions": int(frame["decision_date"].nunique()),
                     "exposed_candidates": exposed_count, "matched_exposed": matched,
                     "matched_fraction": matched / exposed_count if exposed_count else None,
                     "matched_pairs": int(len(matches))}


def audit(*, snapshot_root: Path, calendar_path: Path, protocol_path: Path,
          output: Path, candidates_path: Path | None = None,
          now: datetime | None = None) -> dict:
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Refusing to overwrite existing D7 output: {output}")
    protocol = load_protocol(protocol_path)
    snapshots, observations = load_timely_snapshots(snapshot_root, load_calendar(calendar_path), now=now)
    report = {"protocol_id": protocol["protocol_id"], "protocol_sha256": _digest(protocol_path),
              "generated_at_utc": datetime.now(timezone.utc).isoformat(),
              "observations": observations, "outcomes_loaded": False,
              "training_performed": False, "database_modified": False,
              "serving_changed": False, "historical_pit_certified": False,
              "rights_status": "RESEARCH_REVIEW_PENDING"}
    matches = None
    if candidates_path is None:
        report["status"] = "WAITING_FOR_PROSPECTIVE_ORACLE_OOS_CANDIDATES"
    else:
        report["candidate_path"] = str(candidates_path)
        report["candidate_sha256"] = _digest(candidates_path)
        frame = load_candidates(candidates_path, protocol, snapshots)
        matches, metrics = match_candidates(frame, protocol)
        report["matching"] = metrics
        gate = protocol["readiness_gates"]
        matched_days = (set(matches["decision_date"]) if not matches.empty else set())
        quarters = {f"{day[:4]}Q{(int(day[5:7]) - 1) // 3 + 1}" for day in matched_days}
        report["calendar_quarters"] = sorted(quarters)
        report["status"] = ("MATCHING_READY_FOR_SEPARATE_OUTCOME_AUDIT"
                            if metrics["open_sessions"] >= int(gate["minimum_open_sessions"])
                            and metrics["exposed_candidates"] >= int(gate["minimum_exposed_candidates"])
                            and (metrics["matched_fraction"] or 0) >= float(gate["minimum_matched_fraction"])
                            and len(quarters) >= int(gate["minimum_calendar_quarters"])
                            else "INSUFFICIENT_PROSPECTIVE_MATCHED_SAMPLE")
        # Balance is computed without future labels; it may only demote readiness.
        balance = {}
        for column in ("score_rank", "prior_return_5d"):
            if matches.empty:
                balance[column] = None
                continue
            left = matches[f"exposed_{column}"].astype(float)
            right = matches[f"control_{column}"].astype(float)
            scale = math.sqrt((left.var(ddof=0) + right.var(ddof=0)) / 2)
            balance[column] = (abs(float(left.mean() - right.mean())) / scale if scale > 0
                               else (0.0 if float(left.mean()) == float(right.mean()) else None))
        report["absolute_standardized_differences"] = balance
        if any(value is None or value > float(gate["maximum_absolute_standardized_difference"])
               for value in balance.values()):
            report["status"] = "INSUFFICIENT_MATCH_BALANCE"
    output.mkdir(parents=True, exist_ok=True)
    if matches is not None:
        matches.to_parquet(output / "outcome_blind_matches.parquet", index=False)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                                  default=str), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-root", type=Path,
                        default=Path("artifacts/research/cn_dragon_tiger_15d6/observations"))
    parser.add_argument("--calendar", type=Path,
                        default=Path("config/research_cn/sprint15d6_cn_calendar_2026.yaml"))
    parser.add_argument("--protocol", type=Path,
                        default=Path("config/research_cn/sprint15d7_dragon_tiger_protocol.yaml"))
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = audit(snapshot_root=args.snapshot_root, calendar_path=args.calendar,
                   protocol_path=args.protocol, candidates_path=args.candidates,
                   output=args.output)
    print(json.dumps({"status": report["status"], "observations": report["observations"]["sessions"],
                      "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
