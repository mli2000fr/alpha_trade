"""Read-only final integrity and coverage audit of 15-B5 artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from modelFactory import cn_margin_features_15b5 as builder
from modelFactory.cn_oracle_walk_forward import _sha
from service.market.cn_szse_margin_dataset import OUTPUT, checkpoint


def run(root: Path, dataset_root: Path = OUTPUT) -> dict:
    report = json.loads((root / "report.json").read_text(encoding="utf-8"))
    if (report["status"] != "PASS_FEATURE_JOIN_PROXY_ONLY_PROTOCOL_HISTORY_BLOCKED"
            or report["implementation_sha256"] != _sha(Path(builder.__file__))
            or report["training_ready"] or report["strict_ml_allowed"]
            or report["training_executed"]):
        raise ValueError("Invalid frozen B5 preparation")
    labels = set(report["label_metadata_never_inputs"])
    if any(labels.intersection(columns) for columns in report["model_feature_columns"].values()):
        raise ValueError("Label metadata in model inputs")
    expected_keys = {f"{year}H{half}-lag{lag}" for year in range(2022, 2026)
                     for half in (1, 2) for lag in (2, 3, 5)}
    if set(report["folds"]) != expected_keys or len(report["features"]["years"]) != 8:
        raise ValueError("Incomplete B5 outputs")
    state_path = dataset_root / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    snapshot_path = dataset_root / "reference_snapshot.json"
    if (report["b4_state_sha256"] != _sha(state_path)
            or state["reference_sha256"] != _sha(snapshot_path)):
        raise ValueError("B4 reference changed")
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    sessions = snapshot["sessions"]
    for lag in (2, 3, 5):
        expected_calendar = pd.DataFrame([
            {"source_session": day, "margin_available_at": sessions[i + lag][1]}
            for i, (day, _) in enumerate(sessions)
            if day in state["sessions"] and i + lag < len(sessions) and sessions[i + lag][1]])
        if not pd.read_parquet(root / f"calendar-lag{lag}.parquet").equals(expected_calendar):
            raise ValueError(f"Altered availability calendar lag{lag}")
    result = {"status": "PASS_ASOF_AND_COVERAGE_PROXY_ONLY", "folds": {},
              "report_sha256": _sha(root / "report.json"), "training_ready": False,
              "strict_ml_allowed": False}
    for year, entry in report["features"]["years"].items():
        if _sha(root / f"margin-{year}.parquet") != entry["sha256"]:
            raise ValueError("Changed derived margin partition")
    for key, entry in report["folds"].items():
        path = root / f"{key}.parquet"
        if _sha(path) != entry["joined_sha256"]:
            raise ValueError(f"Changed join {key}")
        frame = pd.read_parquet(path)
        if len(frame) != entry["xshe_pool_rows"] or frame.duplicated(builder.KEYS).any():
            raise ValueError(f"Wrong event count or duplicate {key}")
        decision = pd.to_datetime(frame["decision_at"], utc=True)
        available = pd.to_datetime(frame["margin_available_at"], utc=True)
        if (available.notna() & (available >= decision)).any():
            raise ValueError(f"Late margin {key}")
        if frame["strict_ml_allowed"].any() or frame["historical_vintage_proven"].any():
            raise ValueError(f"Wrong research status {key}")
        paired = frame["evaluation_common_valid"].fillna(False)
        if (int(paired.sum()) != entry["paired_valid_rows"]
                or not frame.loc[paired, builder.FEATURES].notna().all().all()
                or frame.loc[paired, "target_d10"].isna().any()):
            raise ValueError(f"Wrong common population {key}")
        if frame.loc[frame["oracle_decile"].isna(), "target_d10"].notna().any():
            raise ValueError(f"Unknown targets imputed {key}")
        lag = int(key.rsplit("lag", 1)[1])
        calendar = pd.read_parquet(root / f"calendar-lag{lag}.parquet")
        expected = builder.strict_join(
            frame[["instrument_id", "decision_at"]].assign(event_index=frame.index),
            pd.DataFrame(columns=["source_session", "instrument_id", *builder.FEATURES]),
            calendar).sort_values("event_index")
        if not frame["source_session"].fillna("").reset_index(drop=True).equals(
                expected["source_session"].fillna("").reset_index(drop=True)):
            raise ValueError(f"Stale or wrong calendar source {key}")
        known = frame["quality_reasons"].notna()
        result["folds"][key] = {
            "events": len(frame), "latest_source_row_present": int(known.sum()),
            "latest_source_row_absent": int((~known).sum()),
            "margin_four_features_valid": int(frame["margin_common_valid"].sum()),
            "paired_rows": int(paired.sum()),
            "paired_pct_of_xshe_pool": round(100 * paired.mean(), 4),
            "price_missing_counts_among_margin_valid": {
                name: int(value) for name, value in frame.loc[
                    frame["margin_common_valid"], report["model_feature_columns"]["PRICE_BASELINE"]
                ].isna().sum().items() if value},
            "d1_vs_d10_rows": entry["d1_vs_d10_rows"],
            "history_gate_before_purge": entry["history_gate_passed_before_label_purge"]}
    checkpoint(root / "join_audit.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--dataset-root", type=Path, default=OUTPUT)
    args = parser.parse_args()
    result = run(args.root, args.dataset_root)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
