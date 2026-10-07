"""15-B7: join frozen 2021 Oracle OOF to margin and audit actual directional folds.

Research artifacts only. No model training, provider calls, database writes or
change to the 10-B, 15-B4, 15-B5 and 15-B6 frozen campaigns.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory import cn_margin_features_15b5 as b5_builder
from modelFactory.cn_margin_calendar_15b6 import CONFIG, directional_calendar, load_protocol
from modelFactory.cn_margin_features_15b5 import (
    KEYS,
    attach_targets,
    join_price,
    oracle_pool,
    strict_join,
)
from modelFactory.cn_oracle_walk_forward import DEFAULT_CONFIG, Protocol, _sha, _sources
from service.market.cn_szse_margin_dataset import OUTPUT as B4_ROOT
from service.market.cn_szse_margin_dataset import checkpoint

LOG = logging.getLogger(__name__)
B5_ROOT = Path("artifacts/research/cn_margin_lending/sprint15b5_features_v3")
B6_ROOT = Path("artifacts/research/cn_margin_lending/sprint15b6_calendar_v2")
OUTPUT = Path("artifacts/research/cn_margin_lending/sprint15b7_preflight")
TASKS = {"D1_VS_D10": "target_d1_vs_d10", "D10_VS_REST": "target_d10"}


def historical_xshe_ids(b5_root: Path, b4_root: Path = B4_ROOT) -> set[int]:
    """B4 historical XSHE universe, including names never margin-eligible."""
    b5 = json.loads((b5_root / "report.json").read_text(encoding="utf-8"))
    state_path = b4_root / "state.json"
    reference_path = b4_root / "reference_snapshot.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if (b5["b4_state_sha256"] != _sha(state_path)
            or state["reference_sha256"] != _sha(reference_path)
            or state["contract"]["config_sha256"] != b5["protocol_sha256"]):
        raise ValueError("Changed historical XSHE reference")
    items = json.loads(reference_path.read_text(encoding="utf-8"))["instruments"]
    result = {int(item["instrument_id"]) for item in items}
    if len(result) != len(items) or not result:
        raise ValueError("Duplicate or empty XSHE reference")
    return result


def validated_sources(b5_root: Path, b6_root: Path) -> tuple[dict, dict, dict]:
    cfg = load_protocol(CONFIG)
    b5 = json.loads((b5_root / "report.json").read_text(encoding="utf-8"))
    b5_audit = json.loads((b5_root / "join_audit.json").read_text(encoding="utf-8"))
    b6 = json.loads((b6_root / "audit.json").read_text(encoding="utf-8"))
    pinned = {Path(name).resolve(): digest for name, digest in cfg["upstream_hashes"].items()}
    if (b5["status"] != "PASS_FEATURE_JOIN_PROXY_ONLY_PROTOCOL_HISTORY_BLOCKED"
            or b5_audit["status"] != "PASS_ASOF_AND_COVERAGE_PROXY_ONLY"
            or b6["status"] != "PASS_EXTENSION_FEASIBILITY_PENDING_2021_OOF"
            or b6["protocol_sha256"] != _sha(CONFIG)
            or b5["training_executed"] or b5["strict_ml_allowed"]):
        raise ValueError("Upstream research audits not ready")
    if (b5_audit["report_sha256"] != _sha(b5_root / "report.json")
            or pinned.get((b5_root / "report.json").resolve()) != _sha(b5_root / "report.json")
            or pinned.get((b5_root / "join_audit.json").resolve()) != _sha(b5_root / "join_audit.json")
            or b5["implementation_sha256"] != _sha(Path(b5_builder.__file__))):
        raise ValueError("B5 input fingerprints differ")
    if set(b5["folds"]) != {f"{y}H{h}-lag{lag}" for y in range(2022, 2026)
                             for h in (1, 2) for lag in (2, 3, 5)}:
        raise ValueError("Incomplete B5 joins")
    if set(b5["model_feature_columns"]) != {
            "PRICE_BASELINE", "PRICE_MARGIN_FLOW", "PRICE_MARGIN_BALANCE", "PRICE_MARGIN_COMBINED"}:
        raise ValueError("Unexpected B5 feature variants")
    if set(b6["oracle_feasibility"]) != {"2020H1", "2020H2", "2021H1", "2021H2"}:
        raise ValueError("Unexpected B6 extension audit")
    reports = {}
    for semester in cfg["oracle_extension"]["test_semesters"]:
        folder = b6_root / "oracle_extension" / semester
        report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        path = folder / "predictions.parquet"
        if (report["status"] != "OOS_RESEARCH_ONLY" or report["market_code"] != "CN_A"
                or report["horizon"] != 20 or report["model_name"] != "lightgbm"
                or report["test_semester"] != semester or report["serving_enabled"]
                or report["strict_ml_allowed"] or report["directional_model_trained"]
                or report["protocol_sha256"] != _sha(CONFIG)
                or report["code_sha256"] != b6["implementation_sha256"]
                or report["predictions_sha256"] != _sha(path)
                or report["source_artifacts"] != b6["oracle_source_artifacts"]
                or pd.Timestamp(report["split"]["train_label_max_available_at"])
                >= pd.Timestamp(report["split"]["train_boundary_decision"])
                or pd.Timestamp(report["split"]["validation_label_max_available_at"])
                >= pd.Timestamp(report["split"]["validation_boundary_decision"])):
            raise ValueError(f"Invalid extension Oracle {semester}")
        reports[semester] = (path, report)
    protocol = Protocol.load(DEFAULT_CONFIG)
    sources, label_audit = _sources(protocol)
    return {"cfg": cfg, "b5": b5, "b6": b6, "reports": reports}, sources, label_audit


def decision_calendar(sources: dict) -> dict[pd.Timestamp, pd.Timestamp]:
    result = {}
    for year in range(2021, 2026):
        frame = pd.read_parquet(sources[year][0], columns=["session_date", "decision_at"])
        frame["session_date"] = pd.to_datetime(frame["session_date"])
        frame["decision_at"] = pd.to_datetime(frame["decision_at"], utc=True)
        uniqueness = frame.groupby("session_date")["decision_at"].nunique()
        if uniqueness.gt(1).any():
            raise ValueError(f"Different CN decision timestamps on one session {year}")
        for day, instant in frame.groupby("session_date")["decision_at"].first().items():
            if day in result:
                raise ValueError(f"Repeated year/session {day}")
            result[day] = instant
    return result


def join_2021(semester: str, *, sources: dict, label_audit: dict,
              b5_root: Path, report: dict, output: Path) -> dict:
    feature_path, label_folder = sources[2021]
    from modelFactory.cn_oracle_walk_forward import Protocol as OracleProtocol
    oracle = OracleProtocol.load(DEFAULT_CONFIG)
    price = pd.read_parquet(feature_path, columns=[
        "session_date", "instrument_id", "decision_at", *oracle.raw["features"]])
    b5_report = json.loads((b5_root / "report.json").read_text(encoding="utf-8"))
    ids = historical_xshe_ids(b5_root)
    for year in (2020, 2021):
        expected = b5_report["features"]["years"][str(year)]
        path = b5_root / f"margin-{year}.parquet"
        if _sha(path) != expected["sha256"]:
            raise ValueError(f"Changed frozen margin features {year}")
    price = price.loc[price["instrument_id"].isin(ids)].copy()
    price["log_amount_mean20_cny"] = np.log(
        price["amount_mean20_cny"].where(price["amount_mean20_cny"] > 0))
    labels_path = label_folder / "h20.parquet"
    expected_label_hash = next(item for item in label_audit["yearly"]
                               if item["year"] == 2021)["horizons"]["20"]["sha256"]
    if _sha(labels_path) != expected_label_hash:
        raise ValueError("Changed 2021 H20 labels")
    labels = pd.read_parquet(labels_path, columns=[*KEYS, "available_at_utc"])
    price = price.merge(labels, on=KEYS, validate="one_to_one")
    predictions = pd.read_parquet(report["path"])
    if (set(predictions["market_code"]) != {"CN_A"} or set(predictions["horizon"]) != {20}
            or set(predictions["test_semester"]) != {semester}
            or set(predictions["model_name"]) != {"lightgbm"}
            or len(predictions) != report["source"]["split"]["test_rows"]):
        raise ValueError(f"Wrong 2021 prediction scope {semester}")
    pool = oracle_pool(predictions)
    selected = pool.loc[pool["instrument_id"].isin(ids)]
    events = join_price(selected, price)
    if len(events) != len(selected):
        raise ValueError(f"2021 price/label join lost events {semester}")
    margins = pd.concat([pd.read_parquet(b5_root / f"margin-{year}.parquet")
                         for year in (2020, 2021)], ignore_index=True)
    result = {"oracle_all_rows": len(predictions), "oracle_top20_rows": len(pool),
              "xshe_pool_rows": len(events), "joins": {}}
    for lag in (2, 3, 5):
        calendar_path = b5_root / f"calendar-lag{lag}.parquet"
        joined = strict_join(events, margins, pd.read_parquet(calendar_path))
        joined["price_valid"] = np.isfinite(joined[oracle.raw["features"]]).all(axis=1)
        joined["price_valid"] &= np.isfinite(joined["log_amount_mean20_cny"])
        joined["evaluation_common_valid"] = (
            joined["margin_common_valid"] & joined["price_valid"]
            & joined["target_quality_valid"].fillna(False)
            & joined["oracle_decile"].between(1, 10).fillna(False)
            & joined["available_at_utc"].notna())
        attach_targets(joined)
        joined["strict_ml_allowed"] = False
        joined["historical_vintage_proven"] = False
        path = output / f"{semester}-lag{lag}.parquet"
        joined.to_parquet(path, index=False)
        valid = joined.loc[joined["evaluation_common_valid"]]
        result["joins"][str(lag)] = {
            "rows": len(joined), "margin_four_features_valid": int(joined["margin_common_valid"].sum()),
            "paired_rows": len(valid), "paired_dates": int(valid["session_date"].nunique()),
            "paired_symbols": int(valid["instrument_id"].nunique()),
            "d1_vs_d10_rows": int(valid["oracle_decile"].isin([1, 10]).sum()),
            "sha256": _sha(path)}
        LOG.info("%s lag=%s xshe=%s paired=%s", semester, lag, len(joined), len(valid))
    return result


def task_gate(frame: pd.DataFrame, *, task: str, semester: str,
              full_calendar: dict, cfg: dict) -> dict:
    """Tests actual common rows against frozen calendar and label availability."""
    if task not in TASKS:
        raise ValueError(f"Unknown task {task}")
    columns = ["session_date", "decision_at", "instrument_id", "available_at_utc",
               "evaluation_common_valid", TASKS[task]]
    if any(column not in frame for column in columns):
        raise ValueError("Missing gate columns")
    frame = frame[columns].copy()
    frame["session_date"] = pd.to_datetime(frame["session_date"])
    frame["decision_at"] = pd.to_datetime(frame["decision_at"], utc=True)
    frame["available_at_utc"] = pd.to_datetime(frame["available_at_utc"], utc=True)
    if frame.duplicated(KEYS).any():
        raise ValueError("Repeated event in actual gate")
    valid = frame["evaluation_common_valid"].fillna(False)
    frame = frame.loc[valid & frame[TASKS[task]].notna()].copy()
    planned = directional_calendar(list(full_calendar), semester)
    test_start = pd.Timestamp(semester[:4] + ("-01-01" if semester[-1] == "1" else "-07-01"))
    test_end = (pd.Timestamp(int(semester[:4]), 6, 30) if semester[-1] == "1"
                else pd.Timestamp(int(semester[:4]), 12, 31))
    val_start, val_end = pd.Timestamp(planned["validation_start"]), pd.Timestamp(planned["validation_end"])
    train_end = pd.Timestamp(planned["train_end"])
    first_test = next((day for day in sorted(full_calendar) if day >= test_start), None)
    if first_test is None or val_start not in full_calendar:
        raise ValueError("Incomplete official decision calendar")
    train_boundary = pd.to_datetime(full_calendar[val_start], utc=True)
    test_boundary = pd.to_datetime(full_calendar[first_test], utc=True)
    train = frame.loc[(frame["session_date"] <= train_end)
                      & (frame["available_at_utc"] < train_boundary)]
    val = frame.loc[frame["session_date"].between(val_start, val_end)
                    & (frame["available_at_utc"] < test_boundary)]
    test = frame.loc[frame["session_date"].between(test_start, test_end)]
    counts = {}
    for name, part in (("train", train), ("validation", val), ("test", test)):
        counts[name] = {"rows": len(part), "dates": int(part["session_date"].nunique()),
                        "symbols": int(part["instrument_id"].nunique()),
                        "classes": {str(key): int(value) for key, value in
                                    part[TASKS[task]].value_counts(dropna=False).items()}}
        if part["available_at_utc"].isna().any() or (
                part["available_at_utc"] <= part["decision_at"]).any():
            raise ValueError(f"Future label already available at decision: {name}")
    rule = cfg["directional"]
    test_rule = cfg["evaluation"]
    checks = {
        "calendar_504_126_with_gaps": planned["calendar_gate_only"],
        "train_dates_after_label_purge": counts["train"]["dates"]
        >= rule["minimum_train_sessions_after_purge"],
        "validation_dates_after_label_purge": counts["validation"]["dates"]
        >= rule["minimum_validation_sessions_after_label_purge"],
        "test_dates": counts["test"]["dates"] >= test_rule["min_dates_per_fold"],
        "test_rows": counts["test"]["rows"] >= test_rule["min_rows_per_task_per_fold"],
        "test_symbols": counts["test"]["symbols"] >= test_rule["min_symbols_per_task_per_fold"],
        "both_classes_every_partition": all(
            set(part[TASKS[task]].dropna().astype(int).unique()) == {0, 1}
            for part in (train, val, test)),
    }
    return {"task": task, "test_semester": semester, "calendar": planned,
            "train_boundary_decision": str(train_boundary),
            "test_boundary_decision": str(test_boundary),
            "partitions": counts, "checks": checks, "all_gates_pass": all(checks.values())}


def run(*, b5_root: Path = B5_ROOT, b6_root: Path = B6_ROOT, output: Path = OUTPUT) -> dict:
    if output.exists():
        raise FileExistsError(f"Use a new output directory: {output}")
    inputs, sources, label_audit = validated_sources(b5_root, b6_root)
    calendar = decision_calendar(sources)
    b6_cal = inputs["b6"]["directional_calendar"]
    for semester, expected in b6_cal.items():
        if directional_calendar(list(calendar), semester) != expected:
            raise ValueError(f"Calendar differs from preregistered audit {semester}")
    output.mkdir(parents=True)
    report = {"status": "RUNNING", "config_sha256": _sha(CONFIG),
              "b5_report_sha256": _sha(b5_root / "report.json"),
              "b6_audit_sha256": _sha(b6_root / "audit.json"),
              "strict_ml_allowed": False, "training_executed": False,
              "training_ready": False, "serving_enabled": False,
              "joins_2021": {}, "folds": {}, "blockers": []}
    checkpoint(output / "report.json", report)
    try:
        for semester, (path, source_report) in inputs["reports"].items():
            report["joins_2021"][semester] = join_2021(
                semester, sources=sources, label_audit=label_audit, b5_root=b5_root,
                report={"path": path, "source": source_report}, output=output)
            checkpoint(output / "report.json", report)
        for semester in (inputs["cfg"]["directional"]["development_semesters"]
                         + inputs["cfg"]["directional"]["historical_confirmation_semesters"]):
            parts = []
            for year in range(2021, int(semester[:4]) + 1):
                for half in (1, 2):
                    name = f"{year}H{half}"
                    if name > semester:
                        continue
                    if year == 2021:
                        path = output / f"{name}-lag2.parquet"
                        expected = report["joins_2021"][name]["joins"]["2"]["sha256"]
                    else:
                        path = b5_root / f"{name}-lag2.parquet"
                        expected = inputs["b5"]["folds"][f"{name}-lag2"]["joined_sha256"]
                    if _sha(path) != expected:
                        raise ValueError(f"Changed joined source: {path}")
                    parts.append(pd.read_parquet(path, columns=[
                        "session_date", "decision_at", "instrument_id", "available_at_utc",
                        "evaluation_common_valid", *TASKS.values()]))
            history = pd.concat(parts, ignore_index=True)
            for task in TASKS:
                key = f"{semester}:{task}"
                report["folds"][key] = task_gate(
                    history, task=task, semester=semester, full_calendar=calendar, cfg=inputs["cfg"])
                if not report["folds"][key]["all_gates_pass"]:
                    failed = [name for name, passed in report["folds"][key]["checks"].items() if not passed]
                    report["blockers"].append(f"{key}: {','.join(failed)}")
                LOG.info("%s gates=%s", key, report["folds"][key]["checks"])
            checkpoint(output / "report.json", report)
        report["status"] = ("PASS_ACTUAL_FOLD_GATES_PROXY_ONLY" if not report["blockers"]
                            else "BLOCKED_ACTUAL_FOLD_GATES_PROXY_ONLY")
        checkpoint(output / "report.json", report)
    except Exception as exc:
        report.update(status="FAILED", error=str(exc))
        checkpoint(output / "report.json", report)
        raise
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--b5-root", type=Path, default=B5_ROOT)
    parser.add_argument("--b6-root", type=Path, default=B6_ROOT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    result = run(b5_root=args.b5_root, b6_root=args.b6_root, output=args.output)
    print(json.dumps({"status": result["status"], "blockers": result["blockers"],
                      "joins_2021": report_summary(result)}, ensure_ascii=True))


def report_summary(report: dict) -> dict:
    return {semester: data["joins"]["2"] for semester, data in report["joins_2021"].items()}


if __name__ == "__main__":
    main()
