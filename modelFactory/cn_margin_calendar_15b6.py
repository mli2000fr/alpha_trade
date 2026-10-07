"""15-B6 feasibility audit and isolated Oracle H20 OOF extension for 2021.

No modification of original 10-B runs or market database. Training only
when --mode train is explicitly provided.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from modelFactory.cn_oracle_walk_forward import (
    AUDIT_PATH,
    DEFAULT_CONFIG,
    LABEL,
    META,
    Protocol,
    _fit,
    _sha,
    _sources,
    _training_sample,
)
from service.market.cn_szse_margin_dataset import checkpoint

LOG = logging.getLogger(__name__)
CONFIG = Path("config/research_cn/sprint15b6_margin_calendar.yaml")
OUTPUT = Path("artifacts/research/cn_margin_lending/sprint15b6_calendar")


def load_protocol(path: Path = CONFIG) -> dict:
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    if (cfg.get("experiment") != "cn_margin_directional_15b6_v1"
            or cfg.get("market_code") != "CN_A" or cfg.get("strict_ml_allowed") is not False
            or cfg["oracle_extension"]["test_semesters"] != ["2021H1", "2021H2"]
            or cfg["directional"]["development_semesters"] != ["2024H1", "2024H2"]
            or cfg["directional"]["historical_confirmation_semesters"] != ["2025H1", "2025H2"]):
        raise ValueError("Wrong locked B6 research protocol")
    for name, expected in cfg["upstream_hashes"].items():
        if _sha(Path(name)) != expected:
            raise ValueError(f"Changed upstream artifact: {name}")
    extension = cfg["oracle_extension"]
    expected_extension = {"horizon": 20, "model": "lightgbm", "minimum_train_sessions": 504,
                          "validation_window_sessions": 126, "maximum_train_rows": 600000}
    if any(extension.get(k) != v for k, v in expected_extension.items()):
        raise ValueError("Changed locked Oracle extension parameters")
    direction = cfg["directional"]
    expected_direction = {"minimum_train_sessions_after_purge": 504,
                          "validation_window_sessions": 126, "purge_sessions": 20,
                          "embargo_sessions": 20, "primary_lag_sessions": 2,
                          "diagnostic_only_lag_sessions": [3, 5]}
    if any(direction.get(k) != v for k, v in expected_direction.items()):
        raise ValueError("Changed locked directional windows")
    return cfg


def bounds(semester: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    if semester not in ["2020H1", "2020H2", "2021H1", "2021H2"]:
        raise ValueError("Extension audit limited to 2020/2021")
    year, half = int(semester[:4]), semester[-1]
    return ((pd.Timestamp(year, 1, 1), pd.Timestamp(year, 6, 30)) if half == "1"
            else (pd.Timestamp(year, 7, 1), pd.Timestamp(year, 12, 31)))


def split_extension(frame: pd.DataFrame, semester: str, cap: int = 600000):
    start, end = bounds(semester)
    if frame.duplicated(["session_date", "instrument_id"]).any():
        raise ValueError("Duplicate feature/label key")
    dates = pd.DatetimeIndex(sorted(frame["session_date"].unique()))
    prior = dates[dates < start]
    if len(prior) < 630:
        raise ValueError(f"Only {len(prior)} prior sessions; need 504+126")
    validation_start = prior[-126]
    test = frame.loc[frame["session_date"].between(start, end)].copy()
    val = frame.loc[(frame["session_date"] >= validation_start) & (frame["session_date"] < start)].copy()
    train = frame.loc[frame["session_date"] < validation_start].copy()
    # Preserve 10-B's preliminary year-stratified cap before the label purge.
    per_year_cap = max(1000, math.ceil(cap / (int(semester[:4]) - 2018 + 1)))
    train = pd.concat([_training_sample(part, per_year_cap)
                       for _, part in train.groupby(train["session_date"].dt.year)], ignore_index=True)
    if test.empty or val["session_date"].nunique() != 126:
        raise ValueError("Incomplete validation/test calendar")
    train_boundary, val_boundary = val["decision_at"].min(), test["decision_at"].min()
    train = train.loc[train["target_quality_valid"] & (train["available_at_utc"] < train_boundary)]
    val = val.loc[val["target_quality_valid"] & (val["available_at_utc"] < val_boundary)]
    if train["session_date"].nunique() < 504 or val.empty:
        raise ValueError("Insufficient history after label-availability purge")
    # Same deterministic cap as existing Oracle, never sample validation/test.
    train = _training_sample(train, cap)
    if train["session_date"].nunique() < 504:
        raise ValueError("Training cap lost required sessions")
    split = {
        "test_semester": semester, "test_start": str(start.date()), "test_end": str(end.date()),
        "validation_start": str(validation_start.date()), "prior_calendar_sessions": len(prior),
        "train_rows": len(train), "validation_rows": len(val), "test_rows": len(test),
        "train_sessions_after_purge_and_sampling": int(train["session_date"].nunique()),
        "validation_sessions_after_label_purge": int(val["session_date"].nunique()),
        "test_sessions": int(test["session_date"].nunique()),
        "train_label_max_available_at": str(train["available_at_utc"].max()),
        "validation_label_max_available_at": str(val["available_at_utc"].max()),
        "train_boundary_decision": str(train_boundary), "validation_boundary_decision": str(val_boundary),
    }
    return train, val, test, split


def load_frame(sources: dict, label_audit: dict, end_year: int, features: list[str]) -> pd.DataFrame:
    pieces = []
    for year in range(2018, end_year + 1):
        feature_path, label_folder = sources[year]
        label_path = label_folder / "h20.parquet"
        expected = next(item for item in label_audit["yearly"] if item["year"] == year)["horizons"]["20"]["sha256"]
        if _sha(label_path) != expected:
            raise ValueError(f"Changed H20 labels {year}")
        feature = pd.read_parquet(feature_path, columns=[*META, *features])
        label = pd.read_parquet(label_path, columns=LABEL)
        part = feature.merge(label, on=["session_date", "instrument_id"], validate="one_to_one")
        if len(part) != len(feature) or len(label) != len(feature) or set(part["market_code"]) != {"CN_A"}:
            raise ValueError("Different candidate population")
        pieces.append(part)
    frame = pd.concat(pieces, ignore_index=True)
    for name in ("session_date", "decision_at", "available_at_utc"):
        frame[name] = pd.to_datetime(frame[name])
    if (frame["available_at_utc"].notna() & (frame["available_at_utc"] <= frame["decision_at"])).any():
        raise ValueError("Future label already available at event decision")
    return frame


def source_fingerprints(sources: dict) -> dict:
    return {str(year): {"feature_path": str(feature), "feature_sha256": _sha(feature),
                        "label_path": str(labels / "h20.parquet"),
                        "label_sha256": _sha(labels / "h20.parquet")}
            for year, (feature, labels) in sources.items() if year <= 2021}


def directional_calendar(dates: list, semester: str) -> dict:
    """Conservative 20-session gaps on the full event calendar, before row purge."""
    start = pd.Timestamp(semester[:4] + ("-01-01" if semester[-1] == "1" else "-07-01"))
    ordered = pd.DatetimeIndex(sorted(pd.to_datetime(dates).unique()))
    prior = ordered[ordered < start]
    # Twenty full embargo sessions before test, and twenty purge sessions before validation.
    val = prior[-146:-20]
    train = prior[:-166]
    return {"test_semester": semester, "prior_sessions_upper_bound": len(prior),
            "train_sessions_upper_bound_after_calendar_gaps": len(train),
            "validation_window_sessions": len(val),
            "validation_start": str(val[0].date()) if len(val) else None,
            "validation_end": str(val[-1].date()) if len(val) else None,
            "train_end": str(train[-1].date()) if len(train) else None,
            "calendar_gate_only": len(train) >= 504 and len(val) == 126,
            "row_and_label_purge_gate_proven": False}


def audit(config: Path = CONFIG, output: Path = OUTPUT) -> dict:
    cfg = load_protocol(config)
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    upstream = Protocol.load(DEFAULT_CONFIG)
    sources, labels = _sources(upstream)
    frame = load_frame(sources, labels, 2021, [])
    result = {"status": "RUNNING", "protocol_sha256": _sha(config),
              "implementation_sha256": _sha(Path(__file__)), "oracle_feasibility": {},
              "directional_calendar": {}, "training_executed": False,
              "training_ready": False, "strict_ml_allowed": False,
              "extension_predictions_ready": False}
    result["oracle_source_artifacts"] = source_fingerprints(sources)
    output.mkdir(parents=True)
    for semester in ("2020H1", "2020H2", "2021H1", "2021H2"):
        try:
            train, val, _, split = split_extension(frame, semester)
            for part in (train, val):
                if part["oracle_extreme20"].dropna().nunique() != 2:
                    raise ValueError("Both Oracle classes required")
            result["oracle_feasibility"][semester] = {"feasible": True, **split}
        except ValueError as exc:
            result["oracle_feasibility"][semester] = {"feasible": False, "reason": str(exc)}
    # Calendar upper bound, NOT a replacement for the missing 2021 scored pool.
    dates = []
    for year in range(2021, 2026):
        dates.extend(pd.read_parquet(sources[year][0], columns=["session_date"])["session_date"].unique())
    for semester in (cfg["directional"]["development_semesters"]
                     + cfg["directional"]["historical_confirmation_semesters"]):
        result["directional_calendar"][semester] = directional_calendar(dates, semester)
    required = cfg["oracle_extension"]["test_semesters"]
    feasible = all(result["oracle_feasibility"][s]["feasible"] for s in required)
    result["status"] = "PASS_EXTENSION_FEASIBILITY_PENDING_2021_OOF" if feasible else "BLOCKED_EXTENSION"
    result["blockers"] = [
        "Oracle OOF 2021H1/H2 scores not yet trained; actual TOP20 margin coverage unknown",
        "Directional row/class gates, 504 train sessions after purge and 100 usable validation sessions unproven",
        "Archive availability is proxy only, not certified historical PIT",
        "Complete-case baseline restricts scope; no full-TOP20 production inference"]
    checkpoint(output / "audit.json", result)
    return result


def train_extension(semester: str, config: Path = CONFIG, output: Path = OUTPUT) -> dict:
    cfg = load_protocol(config)
    if semester not in cfg["oracle_extension"]["test_semesters"]:
        raise ValueError("Only the two preregistered 2021 folds may be trained")
    upstream = Protocol.load(DEFAULT_CONFIG)
    sources, labels = _sources(upstream)
    folder = output / "oracle_extension" / semester
    if folder.exists():
        raise FileExistsError(f"Refusing overwrite: {folder}")
    preflight = json.loads((output / "audit.json").read_text(encoding="utf-8"))
    if (preflight["status"] != "PASS_EXTENSION_FEASIBILITY_PENDING_2021_OOF"
            or preflight["protocol_sha256"] != _sha(config)
            or preflight["implementation_sha256"] != _sha(Path(__file__))
            or not preflight["oracle_feasibility"][semester]["feasible"]):
        raise ValueError("Matching successful B6 feasibility audit required")
    frame = load_frame(sources, labels, 2021, upstream.raw["features"])
    train, val, test, split = split_extension(frame, semester)
    folder.mkdir(parents=True)
    report = {"status": "RUNNING", "market_code": "CN_A", "horizon": 20,
              "model_name": "lightgbm", "test_semester": semester, "split": split,
              "protocol_sha256": _sha(config), "upstream_protocol_sha256": _sha(DEFAULT_CONFIG),
              "code_sha256": _sha(Path(__file__)), "label_audit_sha256": _sha(AUDIT_PATH),
              "historical_vintage_proven": False, "strict_ml_allowed": False,
              "serving_enabled": False, "directional_model_trained": False}
    report["source_artifacts"] = source_fingerprints(sources)
    if report["source_artifacts"] != preflight["oracle_source_artifacts"]:
        raise ValueError("Training input differs from audited sources")
    checkpoint(folder / "report.json", report)
    try:
        scores = _fit("lightgbm", train, val, test, upstream, folder / "model")
        if len(scores) != len(test) or not np.isfinite(scores).all():
            raise ValueError("Missing/nonfinite Oracle extension predictions")
        columns = ["market_code", "session_date", "instrument_id", "board_code", "cn_breadth_1",
                   "target_quality_valid", "target_quality_reason", "oracle_extreme20", "oracle_decile",
                   "future_return", "execution_data_eligible"]
        predictions = test[columns].copy()
        predictions["oracle_score"] = scores
        predictions["baseline_score"] = test[upstream.raw["baseline_score"]].to_numpy()
        predictions["horizon"], predictions["test_semester"], predictions["model_name"] = 20, semester, "lightgbm"
        path = folder / "predictions.parquet"
        predictions.to_parquet(path, index=False)
        report.update(status="OOS_RESEARCH_ONLY", predictions_sha256=_sha(path))
        checkpoint(folder / "report.json", report)
    except Exception as exc:
        report.update(status="FAILED", error=str(exc))
        checkpoint(folder / "report.json", report)
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["audit", "train"], default="audit")
    parser.add_argument("--config", type=Path, default=CONFIG)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--test-semester", choices=["2021H1", "2021H2"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    if args.mode == "train" and not args.test_semester:
        parser.error("--mode train requires --test-semester")
    result = (audit(args.config, args.output) if args.mode == "audit"
              else train_extension(args.test_semester, args.config, args.output))
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
