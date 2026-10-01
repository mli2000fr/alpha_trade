"""Sprint 15-B8: frozen, research-only directional margin ablation for CN_A.

Consumes B5/B7 immutable joins; never writes to databases or model serving paths.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from modelFactory.cn_margin_preflight_15b7 import (
    B5_ROOT,
    B6_ROOT,
    TASKS,
    decision_calendar,
    task_gate,
    validated_sources,
)
from modelFactory.cn_oracle_walk_forward import _sha
from service.market.cn_szse_margin_dataset import checkpoint

LOG = logging.getLogger(__name__)
B7_ROOT = Path("artifacts/research/cn_margin_lending/sprint15b7_preflight_v2")
OUTPUT = Path("artifacts/research/cn_margin_lending/sprint15b8_directional")
B4_CONFIG = Path("config/research_cn/sprint15b4_szse_margin.yaml")
META = ["session_date", "instrument_id", "decision_at", "available_at_utc",
        "evaluation_common_valid", *TASKS.values()]
MODELS = ("logistic", "lightgbm")


def locked_inputs(b5_root: Path, b6_root: Path, b7_root: Path) -> tuple[dict, dict, dict]:
    upstream, sources, _ = validated_sources(b5_root, b6_root)
    b7 = json.loads((b7_root / "report.json").read_text(encoding="utf-8"))
    if (b7["status"] != "PASS_ACTUAL_FOLD_GATES_PROXY_ONLY" or b7["blockers"]
            or b7["strict_ml_allowed"] or b7["training_executed"]
            or b7["config_sha256"] != _sha(Path("config/research_cn/sprint15b6_margin_calendar.yaml"))
            or b7["b5_report_sha256"] != _sha(b5_root / "report.json")
            or b7["b6_audit_sha256"] != _sha(b6_root / "audit.json")):
        raise ValueError("B7 actual gates or source contract invalid")
    cfg = upstream["cfg"]
    b4 = yaml.safe_load(B4_CONFIG.read_text(encoding="utf-8"))
    if (cfg["directional"]["variants_from"] != str(B4_CONFIG).replace("\\", "/")
            or tuple(cfg["directional"]["models"]) != MODELS
            or list(b4["variants"]) != list(upstream["b5"]["model_feature_columns"])):
        raise ValueError("Unregistered model or feature variant")
    calendar = decision_calendar(sources)
    for semester in cfg["directional"]["development_semesters"] + cfg["directional"]["historical_confirmation_semesters"]:
        for task in TASKS:
            if not b7["folds"][f"{semester}:{task}"]["all_gates_pass"]:
                raise ValueError(f"B7 fold gate not passed: {semester}/{task}")
    return {"cfg": cfg, "b4": b4, "b5": upstream["b5"], "b7": b7,
            "b7_report_sha256": _sha(b7_root / "report.json")}, calendar, sources


def load_history(*, semester: str, lag: int, columns: list[str], roots: dict,
                 inputs: dict) -> pd.DataFrame:
    pieces = []
    for year in range(2021, int(semester[:4]) + 1):
        for half in (1, 2):
            name = f"{year}H{half}"
            if name > semester:
                break
            if year == 2021:
                path = roots["b7"] / f"{name}-lag{lag}.parquet"
                expected = inputs["b7"]["joins_2021"][name]["joins"][str(lag)]["sha256"]
            else:
                path = roots["b5"] / f"{name}-lag{lag}.parquet"
                expected = inputs["b5"]["folds"][f"{name}-lag{lag}"]["joined_sha256"]
            if _sha(path) != expected:
                raise ValueError(f"Changed joined input {path}")
            pieces.append(pd.read_parquet(path, columns=columns))
    frame = pd.concat(pieces, ignore_index=True)
    if frame.duplicated(["session_date", "instrument_id"]).any():
        raise ValueError("Duplicate oracle-margin event")
    frame["session_date"] = pd.to_datetime(frame["session_date"])
    frame["decision_at"] = pd.to_datetime(frame["decision_at"], utc=True)
    frame["available_at_utc"] = pd.to_datetime(frame["available_at_utc"], utc=True)
    return frame


def split_fold(frame: pd.DataFrame, *, task: str, semester: str, inputs: dict,
               calendar: dict) -> dict[str, pd.DataFrame]:
    gate = task_gate(frame, task=task, semester=semester, full_calendar=calendar,
                     cfg=inputs["cfg"])
    expected = inputs["b7"]["folds"][f"{semester}:{task}"]
    if (not gate["all_gates_pass"] or gate["partitions"] != expected["partitions"]
            or gate["checks"] != expected["checks"]):
        raise ValueError(f"B7 population changed: {semester}/{task}")
    target = TASKS[task]
    valid = frame["evaluation_common_valid"].fillna(False) & frame[target].notna()
    frame = frame.loc[valid].copy()
    planned = gate["calendar"]
    train_end = pd.Timestamp(planned["train_end"])
    val_start, val_end = map(pd.Timestamp, (planned["validation_start"], planned["validation_end"]))
    test_start = pd.Timestamp(semester[:4] + ("-01-01" if semester.endswith("H1") else "-07-01"))
    test_end = (pd.Timestamp(int(semester[:4]), 6, 30) if semester.endswith("H1")
                else pd.Timestamp(int(semester[:4]), 12, 31))
    parts = {
        "train": frame.loc[(frame["session_date"] <= train_end)
                           & (frame["available_at_utc"] < pd.Timestamp(gate["train_boundary_decision"]))],
        "validation": frame.loc[frame["session_date"].between(val_start, val_end)
                                & (frame["available_at_utc"] < pd.Timestamp(gate["test_boundary_decision"]))],
        "test": frame.loc[frame["session_date"].between(test_start, test_end)],
    }
    for name, part in parts.items():
        if len(part) != expected["partitions"][name]["rows"]:
            raise ValueError(f"Changed {name} rows")
    return parts


def sample_train(train: pd.DataFrame, limit: int) -> pd.DataFrame:
    if len(train) <= limit:
        return train
    key = pd.util.hash_pandas_object(train[["session_date", "instrument_id"]], index=False).to_numpy(dtype="uint64")
    return train.iloc[np.sort(np.argpartition(key, limit - 1)[:limit])].copy()


def make_model(name: str, inputs: dict):
    cfg = inputs["cfg"]["directional"]
    if name == "logistic":
        params = cfg["logistic"]
        if params["class_weight"] is not None:
            raise ValueError("Class weights not preregistered")
        return make_pipeline(StandardScaler(), LogisticRegression(
            C=params["C"], penalty=params["penalty"], solver=params["solver"],
            max_iter=params["max_iter"], class_weight=None))
    if name == "lightgbm":
        params = inputs["b4"]["lightgbm"]
        return lgb.LGBMClassifier(**params, random_state=cfg["seed"],
                                  n_jobs=4, verbosity=-1)
    raise ValueError(f"Unknown model {name}")


def finite_features(parts: dict[str, pd.DataFrame], columns: list[str]) -> None:
    forbidden = {"oracle_decile", "future_return", "available_at_utc", "oracle_score",
                 "target_d10", "target_d1_vs_d10", "target_quality_valid"}
    if forbidden.intersection(columns) or len(columns) != len(set(columns)):
        raise ValueError("Label, future or duplicate feature in model input")
    for name, part in parts.items():
        if not np.isfinite(part[columns].to_numpy(dtype=float)).all():
            raise ValueError(f"Missing or infinite feature in {name}")


def train_fold(*, task: str, semester: str, model_name: str, inputs: dict,
               calendar: dict, roots: dict, output: Path) -> dict:
    variants = inputs["b5"]["model_feature_columns"]
    columns = list(dict.fromkeys([*META, *[c for features in variants.values() for c in features]]))
    history = load_history(semester=semester, lag=2, columns=columns, roots=roots, inputs=inputs)
    parts = split_fold(history, task=task, semester=semester, inputs=inputs, calendar=calendar)
    target = TASKS[task]
    train = sample_train(parts["train"], inputs["cfg"]["directional"]["maximum_train_rows"])
    if train["session_date"].nunique() < inputs["cfg"]["directional"]["minimum_train_sessions_after_purge"]:
        raise ValueError("Train sampling lost required sessions")
    parts["train"] = train
    outcome = {"status": "RUNNING", "task": task, "semester": semester,
               "model": model_name, "variants": {}, "training_executed": False}
    output.mkdir(parents=True, exist_ok=False)
    checkpoint(output / "report.json", outcome)
    try:
        predictions = parts["test"][["session_date", "instrument_id", target]].copy()
        predictions = predictions.rename(columns={target: "target"})
        predictions["target"] = predictions["target"].astype(int)
        for variant, features in variants.items():
            finite_features(parts, features)
            estimator = make_model(model_name, inputs)
            estimator.fit(parts["train"][features].to_numpy(dtype=float),
                          parts["train"][target].to_numpy(dtype=int))
            predictions[variant] = estimator.predict_proba(
                parts["test"][features].to_numpy(dtype=float))[:, 1]
            outcome["variants"][variant] = {"features": features, "train_rows": len(train),
                                             "validation_rows": len(parts["validation"]),
                                             "test_rows": len(parts["test"])}
            LOG.info("B8 %s %s %s %s trained", task, semester, model_name, variant)
            checkpoint(output / "report.json", outcome)
        if predictions.duplicated(["session_date", "instrument_id"]).any():
            raise ValueError("Duplicate OOF prediction")
        path = output / "predictions.parquet"
        predictions.to_parquet(path, index=False)
        outcome.update(status="OOS_RESEARCH_PROXY_ONLY", predictions_sha256=_sha(path),
                       predictions_rows=len(predictions), training_executed=True,
                       serving_enabled=False, strict_ml_allowed=False)
        checkpoint(output / "report.json", outcome)
    except Exception as exc:
        outcome.update(status="FAILED", error=str(exc))
        checkpoint(output / "report.json", outcome)
        raise
    return outcome


def date_weights(frame: pd.DataFrame) -> np.ndarray:
    group = (["bootstrap_draw", "session_date"] if "bootstrap_draw" in frame
             else ["session_date"])
    return (1.0 / frame.groupby(group)["instrument_id"].transform("size")).to_numpy(dtype=float)


def weighted_auc(frame: pd.DataFrame, score: str) -> float:
    if frame["target"].nunique() != 2:
        raise ValueError("AUC needs both classes")
    return float(roc_auc_score(frame["target"].to_numpy(dtype=int),
                               frame[score].to_numpy(dtype=float), sample_weight=date_weights(frame)))


def daily_top(frame: pd.DataFrame, score: str, pct: float) -> pd.DataFrame:
    if frame.duplicated(["session_date", "instrument_id"]).any():
        raise ValueError("Duplicate test event")
    ordered = frame.sort_values(["session_date", score, "instrument_id"],
                                ascending=[True, False, True], kind="mergesort")
    rank = ordered.groupby("session_date").cumcount()
    size = ordered.groupby("session_date")["session_date"].transform("size")
    return ordered.loc[rank < np.ceil(size * pct)].copy()


def score_metrics(frame: pd.DataFrame, variant: str, pct: float) -> dict:
    top = daily_top(frame, variant, pct)
    return {"auc_equal_date": weighted_auc(frame, variant),
            "precision_top20_equal_date": float(top.groupby("session_date")["target"].mean().mean()),
            "rows": len(frame), "dates": int(frame["session_date"].nunique())}


def bootstrap_delta_auc(frame: pd.DataFrame, *, variant: str, reps: int,
                        alpha_each: float, seed: int) -> dict:
    months = frame["session_date"].dt.to_period("M")
    blocks = [frame.loc[months == month] for month in sorted(months.unique())]
    rng = np.random.default_rng(seed)
    values = np.empty(reps, dtype=float)
    for i in range(reps):
        draw = pd.concat([blocks[j].assign(bootstrap_draw=k)
                          for k, j in enumerate(rng.integers(0, len(blocks), len(blocks)))],
                         ignore_index=True)
        values[i] = weighted_auc(draw, variant) - weighted_auc(draw, "PRICE_BASELINE")
    return {"months": len(blocks), "repetitions": reps,
            "alpha_each_two_sided": alpha_each,
            "lower_fwer_bound": float(np.quantile(values, alpha_each / 2)),
            "upper_fwer_bound": float(np.quantile(values, 1 - alpha_each / 2))}


def aggregate(*, output: Path, inputs: dict) -> dict:
    cfg = inputs["cfg"]
    ev = cfg["evaluation"]
    semesters = cfg["directional"]["development_semesters"] + cfg["directional"]["historical_confirmation_semesters"]
    comparisons = {}
    for task in TASKS:
        for model in MODELS:
            fold_frames = []
            per_fold = {}
            for semester in semesters:
                folder = output / task / model / semester
                report = json.loads((folder / "report.json").read_text(encoding="utf-8"))
                path = folder / "predictions.parquet"
                if (report["status"] != "OOS_RESEARCH_PROXY_ONLY"
                        or report["predictions_sha256"] != _sha(path)):
                    raise ValueError(f"Incomplete B8 fold {folder}")
                frame = pd.read_parquet(path)
                frame["session_date"] = pd.to_datetime(frame["session_date"])
                if len(frame) != report["predictions_rows"]:
                    raise ValueError("OOF row count changed")
                fold_frames.append(frame)
                per_fold[semester] = {variant: score_metrics(frame, variant, ev["directional_top_pct"])
                                      for variant in inputs["b5"]["model_feature_columns"]}
            pooled = pd.concat(fold_frames, ignore_index=True)
            base_top = daily_top(pooled, "PRICE_BASELINE", ev["directional_top_pct"])
            base_positive = base_top.loc[base_top["target"].eq(1), ["session_date", "instrument_id"]]
            base_keys = pd.MultiIndex.from_frame(base_positive)
            for index, variant in enumerate(list(inputs["b5"]["model_feature_columns"])[1:]):
                actual_top = daily_top(pooled, variant, ev["directional_top_pct"])
                actual_keys = pd.MultiIndex.from_frame(actual_top[["session_date", "instrument_id"]])
                removed = 1 - float(base_keys.isin(actual_keys).mean()) if len(base_keys) else math.nan
                pooled_base = score_metrics(pooled, "PRICE_BASELINE", ev["directional_top_pct"])
                pooled_variant = score_metrics(pooled, variant, ev["directional_top_pct"])
                fold_deltas = {semester: per_fold[semester][variant]["auc_equal_date"]
                               - per_fold[semester]["PRICE_BASELINE"]["auc_equal_date"]
                               for semester in semesters}
                boot = bootstrap_delta_auc(pooled, variant=variant,
                                           reps=ev["bootstrap_repetitions"],
                                           alpha_each=ev["familywise_alpha"] / ev["primary_hypotheses"],
                                           seed=cfg["directional"]["seed"] + index
                                           + (0 if task == "D1_VS_D10" else 10)
                                           + (0 if model == "logistic" else 20))
                delta = pooled_variant["auc_equal_date"] - pooled_base["auc_equal_date"]
                precision_uplift = (pooled_variant["precision_top20_equal_date"]
                                    - pooled_base["precision_top20_equal_date"])
                positive = sum(x > 0 for x in fold_deltas.values())
                go = (delta >= ev["min_delta_auc"] and positive >= ev["min_positive_folds"]
                      and all(fold_deltas[x] > 0 for x in cfg["directional"]["historical_confirmation_semesters"])
                      and precision_uplift >= ev["min_precision_uplift"]
                      and removed <= ev["max_removed_baseline_top20_true_positives_fraction"]
                      and boot["lower_fwer_bound"] > 0)
                comparisons[f"{task}:{model}:{variant}"] = {
                    "status": "RESEARCH_SIGNAL_PASS_PROXY_ONLY" if go else "NO_GO_INCREMENTAL_MARGIN",
                    "baseline": pooled_base, "extension": pooled_variant,
                    "delta_auc_equal_date": delta, "precision_top20_uplift": precision_uplift,
                    "baseline_top20_true_positive_removed_fraction": removed,
                    "fold_delta_auc": fold_deltas, "positive_folds": positive,
                    "monthly_bootstrap": boot, "strict_ml_allowed": False,
                    "production_decision": "NEVER_FROM_PROXY_ALONE"}
    return {"status": "COMPLETED_RESEARCH_PROXY_ONLY", "comparisons": comparisons,
            "b7_report_sha256": inputs["b7_report_sha256"],
            "b6_config_sha256": _sha(Path("config/research_cn/sprint15b6_margin_calendar.yaml")),
            "training_executed": True, "serving_enabled": False, "strict_ml_allowed": False}


def run(*, output: Path = OUTPUT, b5_root: Path = B5_ROOT,
        b6_root: Path = B6_ROOT, b7_root: Path = B7_ROOT) -> dict:
    if output.exists():
        raise FileExistsError(f"Use a new B8 output directory: {output}")
    roots = {"b5": b5_root, "b7": b7_root}
    inputs, calendar, _ = locked_inputs(b5_root, b6_root, b7_root)
    output.mkdir(parents=True)
    state = {"status": "RUNNING", "completed_folds": [], "comparisons": {},
             "b7_report_sha256": inputs["b7_report_sha256"], "strict_ml_allowed": False,
             "serving_enabled": False}
    checkpoint(output / "report.json", state)
    try:
        for task in TASKS:
            for model in MODELS:
                for semester in (inputs["cfg"]["directional"]["development_semesters"]
                                 + inputs["cfg"]["directional"]["historical_confirmation_semesters"]):
                    train_fold(task=task, semester=semester, model_name=model,
                               inputs=inputs, calendar=calendar, roots=roots,
                               output=output / task / model / semester)
                    state["completed_folds"].append(f"{task}:{model}:{semester}")
                    checkpoint(output / "report.json", state)
        state.update(aggregate(output=output, inputs=inputs))
        checkpoint(output / "report.json", state)
    except Exception as exc:
        state.update(status="FAILED", error=str(exc))
        checkpoint(output / "report.json", state)
        raise
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    report = run(output=args.output)
    print(json.dumps({"status": report["status"], "results": {
        key: value["status"] for key, value in report["comparisons"].items()}},
        ensure_ascii=True))


if __name__ == "__main__":
    main()
