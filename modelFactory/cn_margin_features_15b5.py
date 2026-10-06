"""15-B5: frozen SZSE archives to rolling features and strict-asof OOF joins.

Research proxy only, no training, network access or database writes.
"""
from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
from collections import Counter, deque
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from modelFactory.cn_oracle_aggregate import _find_run
from modelFactory.cn_oracle_walk_forward import (
    AUDIT_PATH,
    DEFAULT_CONFIG,
    DEFAULT_OUTPUT,
    Protocol,
    _sha,
    _sources,
    _top_rows,
)
from service.market.cn_szse_margin_dataset import CONFIG, OUTPUT, checkpoint

LOG = logging.getLogger(__name__)
FEATURES = ["financing_buy_to_amount", "financing_buy_to_amount_mean5",
            "financing_balance_change5", "financing_balance_change20"]
DEST = Path("artifacts/research/cn_margin_lending/sprint15b5_features")
KEYS = ["session_date", "instrument_id"]


def rolling_row(row: dict, index: int, history: deque) -> dict:
    """A missing calendar session or invalid row breaks all intersecting windows."""
    ratio = row["financing_buy_to_amount"]
    reasons = list(row["quality_reasons"])
    if ratio is not None and (not np.isfinite(ratio) or ratio < 0 or ratio > 1):
        reasons.append("FINANCING_BUY_EXCEEDS_AMOUNT")
    valid = not reasons and row["measures"] is not None and ratio is not None
    history.append((index, row, valid))
    values = dict.fromkeys(FEATURES)
    if valid:
        values[FEATURES[0]] = ratio
    for length, name in [(5, FEATURES[1]), (6, FEATURES[2]), (21, FEATURES[3])]:
        window = list(history)[-length:]
        contiguous = len(window) == length and all(
            entry[0] == index - length + 1 + i and entry[2]
            for i, entry in enumerate(window))
        if not contiguous:
            continue
        if length == 5:
            values[name] = sum(x[1]["financing_buy_to_amount"] for x in window) / 5
        else:
            initial = window[0][1]["measures"]["融资余额"]
            if initial > 0:
                values[name] = row["measures"]["融资余额"] / initial - 1
    return {"instrument_id": row["instrument_id"], "source_session": row["source_session"],
            "quality_reasons": "|".join(reasons), **values}


def strict_join(events: pd.DataFrame, margins: pd.DataFrame,
                calendar: pd.DataFrame) -> pd.DataFrame:
    """Latest calendar source before decision; never fall back to stale valid rows."""
    events = events.copy()
    events["decision_at"] = pd.to_datetime(events["decision_at"], utc=True)
    calendar = calendar.copy()
    calendar["margin_available_at"] = pd.to_datetime(calendar["margin_available_at"], utc=True)
    expected = pd.merge_asof(
        events.sort_values("decision_at"), calendar.sort_values("margin_available_at"),
        left_on="decision_at", right_on="margin_available_at",
        direction="backward", allow_exact_matches=False)
    joined = expected.merge(margins, on=["source_session", "instrument_id"],
                            how="left", validate="many_to_one")
    if (joined["margin_available_at"].dropna()
            >= joined.loc[joined["margin_available_at"].notna(), "decision_at"]).any():
        raise ValueError("Margin data available at or after decision")
    joined["margin_common_valid"] = joined[FEATURES].notna().all(axis=1)
    return joined


def oracle_pool(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.duplicated(KEYS).any() or not frame["oracle_score"].notna().all():
        raise ValueError("Duplicated or missing Oracle scores")
    # Do not filter by future target quality, future return or margin coverage first.
    return _top_rows(frame, "oracle_score", 0.20)


def join_price(events: pd.DataFrame, price: pd.DataFrame) -> pd.DataFrame:
    overlap = sorted((set(events) & set(price)) - set(KEYS))
    joined = events.merge(price, on=KEYS, validate="one_to_one", suffixes=("_oracle", ""))
    for name in overlap:
        left, right = joined[name + "_oracle"], joined[name]
        if not ((left == right) | (left.isna() & right.isna())).all():
            raise ValueError(f"Price/Oracle shared feature differs: {name}")
        joined = joined.drop(columns=name + "_oracle")
    return joined


def attach_targets(frame: pd.DataFrame) -> None:
    # Unknown/invalid deciles stay unknown, never become a negative class.
    valid = frame["target_quality_valid"].fillna(False) & frame["oracle_decile"].between(1, 10).fillna(False)
    frame["target_d10"] = frame["oracle_decile"].eq(10).astype("Int8").where(valid)
    frame["target_d1_vs_d10"] = frame["target_d10"].where(frame["oracle_decile"].isin([1, 10]))


def build_features(root: Path, output: Path, snapshot: dict, state: dict) -> dict:
    histories = {}
    rows = []
    years = {}
    reasons = Counter()
    sessions = snapshot["sessions"]
    position = {day: i for i, (day, _) in enumerate(sessions)}
    calendar = {lag: [] for lag in (2, 3, 5)}
    current_year = None

    def flush(year):
        if not rows:
            return
        frame = pd.DataFrame(rows)
        if frame.duplicated(["source_session", "instrument_id"]).any():
            raise ValueError("Duplicate rolling key")
        path = output / f"margin-{year}.parquet"
        frame.to_parquet(path, index=False)
        years[year] = {"rows": len(frame), "common_valid": int(frame[FEATURES].notna().all(axis=1).sum()),
                       "sha256": _sha(path)}
        rows.clear()

    for index, day in enumerate(state["contract"]["session_dates"]):
        if current_year and day[:4] != current_year:
            flush(current_year)
        current_year = day[:4]
        for lag in calendar:
            future = position[day] + lag
            if future < len(sessions) and sessions[future][1]:
                calendar[lag].append({"source_session": day,
                                      "margin_available_at": sessions[future][1]})
        path = root / f"{day}.jsonl.gz"
        if _sha(path) != state["sessions"][day]["partition_sha256"]:
            raise ValueError(f"Changed margin partition {day}")
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            for line in stream:
                row = json.loads(line)
                history = histories.setdefault(row["instrument_id"], deque(maxlen=21))
                derived = rolling_row(row, index, history)
                reasons.update(derived["quality_reasons"].split("|") if derived["quality_reasons"] else [])
                rows.append(derived)
        if index % 100 == 0:
            LOG.info("rolling sessions=%s/%s", index + 1, len(state["sessions"]))
    flush(current_year)
    for lag, values in calendar.items():
        pd.DataFrame(values).to_parquet(output / f"calendar-lag{lag}.parquet", index=False)
    return {"years": years, "quality_reasons": dict(reasons)}


def run(root: Path = OUTPUT, output: Path = DEST) -> dict:
    if output.exists():
        raise FileExistsError(f"New output directory required: {output}")
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    audit = json.loads((root / "audit_report.json").read_text(encoding="utf-8"))
    if (state["status"] != "COMPLETED_COLLECTION_PROXY_ONLY"
            or audit["status"] != "PASS_COLLECTION_AUDIT_PROXY_ONLY"
            or audit["errors"] or (root / ".lock").exists()):
        raise ValueError("B4 audit missing, failed or collector active")
    from service.market import cn_szse_margin_dataset as collector
    if (state["contract"]["config_sha256"] != _sha(CONFIG)
            or state["contract"]["implementation_sha256"] != _sha(Path(collector.__file__))
            or state["reference_sha256"] != _sha(root / "reference_snapshot.json")):
        raise ValueError("B4 frozen contract differs")
    snapshot = json.loads((root / "reference_snapshot.json").read_text(encoding="utf-8"))
    protocol = Protocol.load(DEFAULT_CONFIG)
    sources, label_audit = _sources(protocol)
    from modelFactory import cn_oracle_walk_forward as runner
    reports = {}
    # Fix LightGBM amplitude, not a model chosen after directional results.
    for semester in protocol.raw["test_semesters"]:
        found = _find_run(DEFAULT_OUTPUT, horizon=20, semester=semester, model="lightgbm",
                          config_sha=_sha(DEFAULT_CONFIG), code_sha=_sha(Path(runner.__file__)),
                          audit_sha=_sha(AUDIT_PATH))
        if found is None:
            raise ValueError(f"OOF Oracle absent {semester}")
        path, report = found
        split = report["split"]
        if (report["status"] != "OOS_RESEARCH_ONLY" or report["market_code"] != "CN_A"
                or pd.Timestamp(split["train_label_max_available_at"])
                >= pd.Timestamp(split["validation_start"])
                or pd.Timestamp(split["validation_label_max_available_at"])
                >= pd.Timestamp(split["test_start"])):
            raise ValueError(f"Invalid Oracle split {semester}")
        reports[semester] = (path, report)
    output.mkdir(parents=True)
    result = {"status": "RUNNING", "strict_ml_allowed": False, "training_ready": False,
              "process_id": os.getpid(),
              "serving_enabled": False, "training_executed": False,
              "implementation_sha256": _sha(Path(__file__)), "protocol_sha256": _sha(CONFIG),
              "b4_state_sha256": _sha(root / "state.json"),
              "b4_audit_sha256": _sha(root / "audit_report.json"),
              "oracle_model_fixed": "lightgbm", "top20_scope": "whole_CN_before_margin_or_labels",
              "folds": {}, "blockers": []}
    result["model_feature_columns"] = {
        key: [*protocol.raw["features"], "log_amount_mean20_cny", *extension]
        for key, extension in cfg["variants"].items()}
    result["label_metadata_never_inputs"] = [
        "oracle_decile", "oracle_extreme20", "future_return", "available_at_utc",
        "target_quality_valid", "target_quality_reason", "execution_data_eligible",
        "target_d10", "target_d1_vs_d10"]
    checkpoint(output / "report.json", result)
    result["features"] = build_features(root, output, snapshot, state)
    ids = {r["instrument_id"] for r in snapshot["instruments"]}
    history_dates = {lag: set() for lag in (2, 3, 5)}
    for year in range(2022, 2026):
        feature_path, label_folder = sources[year]
        columns = ["session_date", "instrument_id", "decision_at", *protocol.raw["features"]]
        price = pd.read_parquet(feature_path, columns=columns)
        price = price.loc[price["instrument_id"].isin(ids)]
        price["log_amount_mean20_cny"] = np.log(
            price["amount_mean20_cny"].where(price["amount_mean20_cny"] > 0))
        label_path = label_folder / "h20.parquet"
        expected_hash = next(y for y in label_audit["yearly"] if y["year"] == year)["horizons"]["20"]["sha256"]
        if _sha(label_path) != expected_hash:
            raise ValueError(f"Changed labels {year}")
        labels = pd.read_parquet(label_path, columns=[*KEYS, "available_at_utc"])
        price = price.merge(labels, on=KEYS, validate="one_to_one")
        margin = pd.concat([pd.read_parquet(output / f"margin-{y}.parquet")
                            for y in (year - 1, year)], ignore_index=True)
        for semester in (f"{year}H1", f"{year}H2"):
            path, source_report = reports[semester]
            predictions = pd.read_parquet(path)
            if (set(predictions["market_code"]) != {"CN_A"}
                    or set(predictions["horizon"]) != {20}
                    or set(predictions["test_semester"]) != {semester}):
                raise ValueError("Wrong prediction scope")
            pool = oracle_pool(predictions)
            events = join_price(pool.loc[pool["instrument_id"].isin(ids)], price)
            if len(events) != int(pool["instrument_id"].isin(ids).sum()):
                raise ValueError("Price/label join lost events")
            for lag in (2, 3, 5):
                calendar = pd.read_parquet(output / f"calendar-lag{lag}.parquet")
                joined = strict_join(events, margin, calendar)
                joined["price_valid"] = np.isfinite(joined[protocol.raw["features"]]).all(axis=1)
                joined["price_valid"] &= np.isfinite(joined["log_amount_mean20_cny"])
                joined["evaluation_common_valid"] = (
                    joined["margin_common_valid"] & joined["price_valid"]
                    & joined["target_quality_valid"].fillna(False)
                    & joined["oracle_decile"].between(1, 10).fillna(False)
                    & joined["available_at_utc"].notna())
                # Labels and label availability remain metadata, never model inputs.
                attach_targets(joined)
                joined["strict_ml_allowed"] = False
                joined["historical_vintage_proven"] = False
                key = f"{semester}-lag{lag}"
                destination = output / f"{key}.parquet"
                joined.to_parquet(destination, index=False)
                common = joined.loc[joined["evaluation_common_valid"]]
                before = len(history_dates[lag])
                minimum = cfg["minimum_train_sessions"] + cfg["validation_sessions"]
                result["folds"][key] = {
                    "oracle_all_rows": len(predictions), "oracle_top20_rows": len(pool),
                    "xshe_pool_rows": len(events), "paired_valid_rows": len(common),
                    "paired_dates": int(common["session_date"].nunique()),
                    "paired_symbols": int(common["instrument_id"].nunique()),
                    "d1_vs_d10_rows": int(common["oracle_decile"].isin([1, 10]).sum()),
                    "prior_oof_sessions": before, "minimum_prior_sessions": minimum,
                    "history_gate_passed_before_label_purge": before >= minimum,
                    "predictions_sha256": source_report["predictions_sha256"],
                    "joined_sha256": _sha(destination)}
                if before < minimum:
                    result["blockers"].append(f"{key}: OOF history {before} < {minimum}; no training allowed")
                history_dates[lag].update(common["session_date"].astype(str))
                LOG.info("%s joined=%s paired=%s history=%s", key, len(joined), len(common), before)
                checkpoint(output / "report.json", result)
    result["status"] = "PASS_FEATURE_JOIN_PROXY_ONLY_PROTOCOL_HISTORY_BLOCKED"
    result["completed_at"] = datetime.now(UTC).isoformat()
    checkpoint(output / "report.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=OUTPUT)
    parser.add_argument("--output", type=Path, default=DEST)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        result = run(args.dataset_root, args.output)
    except Exception as exc:
        report_path = args.output / "report.json"
        if report_path.exists():
            report = json.loads(report_path.read_text(encoding="utf-8"))
            if report.get("status") == "RUNNING" and report.get("process_id") == os.getpid():
                report.update(status="FAILED", error=str(exc))
                checkpoint(report_path, report)
        LOG.exception("B5 failed; retain artifacts and use a new output directory after diagnosis")
        raise
    print(result["status"])


if __name__ == "__main__":
    main()
