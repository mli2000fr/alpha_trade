"""Read-only Dragon/Tiger preflight from 15-D4 aggregates; no model training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def summarize_deciles(source: dict, window: int) -> dict:
    if window not in (5, 20):
        raise ValueError("Only preregistered windows 5/20")
    deciles = source["realized_deciles"]
    key = f"event_within_{window}_sessions"
    d1_total = int(deciles["1"]["oracle_top20_rows"])
    d10_total = int(deciles["10"]["oracle_top20_rows"])
    d1_event = int(deciles["1"][key])
    d10_event = int(deciles["10"][key])
    if not (0 <= d1_event <= d1_total and 0 <= d10_event <= d10_total):
        raise ValueError("Inconsistent 15-D4 decile counts")
    covered_extremes = d1_event + d10_event
    uncovered_extremes = d1_total + d10_total - covered_extremes
    return {
        "window_sessions": window,
        "d1_event": d1_event, "d10_event": d10_event,
        "d1_no_event": d1_total - d1_event,
        "d10_no_event": d10_total - d10_event,
        "d1_share_among_covered_extremes": round(d1_event / covered_extremes, 6),
        "d1_share_among_uncovered_extremes": round(
            (d1_total - d1_event) / uncovered_extremes, 6),
        "d10_share_among_covered_extremes": round(d10_event / covered_extremes, 6),
        "d10_share_among_uncovered_extremes": round(
            (d10_total - d10_event) / uncovered_extremes, 6),
        "not_matched_on_prior_return": True,
        "not_stratified_by_semester_and_decile": True,
    }


def preflight(report: dict) -> dict:
    if report.get("status") != "COVERAGE_PROXY_ONLY_NO_ML_GO":
        raise ValueError("Expected completed 15-D4 proxy report")
    if report.get("same_day_event_used") is not False:
        raise ValueError("Same-day event leakage")
    if report.get("mapping", {}).get("unmapped_events") != 0:
        raise ValueError("Historical mappings incomplete")
    result = {
        "status": "NO_GO_ML_PENDING_RIGHTS_PIT_MATCHING",
        "primary": "JPLUS2_WITHIN_5",
        "d4_source_status": report["status"],
        "analyses": {},
        "rights_clearance": "UNCONFIRMED",
        "historical_publication_time": "UNPROVEN",
        "historical_corrections": "UNPROVEN",
        "matched_prior_movement_analysis": "NOT_AVAILABLE_FROM_D4_AGGREGATES",
        "model_training_performed": False,
        "production_changed": False,
    }
    for lag in ("JPLUS2", "JPLUS1"):
        if lag not in report["coverage"]:
            raise ValueError(f"Missing coverage {lag}")
        for window in (5, 20):
            result["analyses"][f"{lag}_WITHIN_{window}"] = summarize_deciles(
                report["coverage"][lag], window)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--d4-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    source = json.loads(args.d4_report.read_text(encoding="utf-8"))
    result = preflight(source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": result["status"], "primary": result["analyses"][result["primary"]]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
