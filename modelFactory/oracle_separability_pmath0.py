"""P-MATH-0 — audit non paramétrique de séparabilité dans le pool Oracle.

Recherche uniquement : aucune écriture SQL, aucun artefact de serving.
Les permutations sont intra-date et les transformations sont apprises sur le
train de chaque fold chronologique.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.sparse.csgraph import minimum_spanning_tree
from scipy.spatial.distance import pdist, squareform
from scipy.stats import chi2, energy_distance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import GUARD_COL, build_dataset as build_oracle_dataset
from modelFactory.oracle.train import get_universe_symbols
from modelFactory.oracle.walk_forward import build_folds_adaptive
from modelFactory.shared_directional import (
    ORACLE_GATE_SCORE_COL,
    _load_gate,
    load_profile,
)

LOGGER = logging.getLogger(__name__)
DEFAULT_CONFIG = Path("config/research/pmath0_separability.json")
DECILE = "oracle_decile"
TARGET = "_pmath0_target"
TASKS = ("D1_VS_D10", "D10_VS_REST", "D1_VS_REST")


@dataclass(frozen=True)
class Preprocessor:
    features: tuple[str, ...]
    median: np.ndarray
    lower: np.ndarray
    upper: np.ndarray
    mean: np.ndarray
    scale: np.ndarray


def attach_task(frame: pd.DataFrame, task: str) -> pd.DataFrame:
    """Attach the frozen binary target and retain the task population."""
    if task not in TASKS:
        raise ValueError(f"Unknown P-MATH-0 task: {task}")
    result = frame.copy()
    decile = pd.to_numeric(result[DECILE], errors="coerce")
    if task == "D1_VS_D10":
        result = result[decile.isin([1, 10])].copy()
        decile = pd.to_numeric(result[DECILE], errors="coerce")
        result[TARGET] = decile.eq(10).astype(int)
    elif task == "D10_VS_REST":
        result = result[decile.between(1, 10)].copy()
        result[TARGET] = decile[result.index].eq(10).astype(int)
    else:
        result = result[decile.between(1, 10)].copy()
        result[TARGET] = decile[result.index].eq(1).astype(int)
    return result


def balanced_by_date(
    frame: pd.DataFrame,
    *,
    max_per_class: int,
    seed: int,
) -> pd.DataFrame:
    """Balance classes inside every date while preserving broad date coverage."""
    if frame.empty:
        return frame.copy()
    work = frame.dropna(subset=["date", TARGET]).copy()
    normalized = pd.to_datetime(work["date"]).dt.normalize()
    dates = pd.Index(normalized.unique()).sort_values()
    per_date_cap = max(1, int(math.ceil(max_per_class / max(len(dates), 1))))
    rng = np.random.default_rng(seed)
    pieces: list[pd.DataFrame] = []
    for date in dates:
        group = work[normalized.eq(date)]
        negative = group[group[TARGET].eq(0)]
        positive = group[group[TARGET].eq(1)]
        count = min(len(negative), len(positive), per_date_cap)
        if count <= 0:
            continue
        neg_idx = rng.choice(negative.index.to_numpy(), size=count, replace=False)
        pos_idx = rng.choice(positive.index.to_numpy(), size=count, replace=False)
        pieces.extend([work.loc[neg_idx], work.loc[pos_idx]])
    if not pieces:
        return work.iloc[0:0].copy()
    result = pd.concat(pieces, ignore_index=True)
    if int((result[TARGET] == 0).sum()) > max_per_class:
        kept: list[pd.DataFrame] = []
        used = 0
        for _, group in result.groupby("date", sort=True):
            per_class = int((group[TARGET] == 0).sum())
            if used + per_class > max_per_class:
                break
            kept.append(group)
            used += per_class
        result = pd.concat(kept, ignore_index=True) if kept else result.iloc[0:0]
    return result.sort_values(["date", "symbol"]).reset_index(drop=True)


def permute_within_date(
    labels: np.ndarray,
    dates: Iterable[Any],
    rng: np.random.Generator,
) -> np.ndarray:
    result = np.asarray(labels, dtype=int).copy()
    date_values = pd.to_datetime(pd.Series(list(dates))).dt.normalize().to_numpy()
    for date in pd.unique(date_values):
        indices = np.flatnonzero(date_values == date)
        result[indices] = rng.permutation(result[indices])
    return result


def fit_preprocessor(
    train: pd.DataFrame,
    features: list[str],
    *,
    lower_q: float,
    upper_q: float,
    max_missing_rate: float,
) -> Preprocessor:
    raw = train.reindex(columns=features).apply(pd.to_numeric, errors="coerce")
    keep = raw.columns[raw.isna().mean().le(max_missing_rate)].tolist()
    if not keep:
        raise ValueError("No usable P-MATH-0 features")
    raw = raw[keep]
    median = raw.median(axis=0).fillna(0.0).to_numpy(float)
    values = raw.to_numpy(float)
    values = np.where(np.isfinite(values), values, median)
    lower = np.nanquantile(values, lower_q, axis=0)
    upper = np.nanquantile(values, upper_q, axis=0)
    values = np.clip(values, lower, upper)
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    valid = np.isfinite(scale) & (scale > 1e-10)
    if not valid.any():
        raise ValueError("All P-MATH-0 features are constant")
    return Preprocessor(
        tuple(np.asarray(keep)[valid].tolist()),
        median[valid], lower[valid], upper[valid], mean[valid], scale[valid],
    )


def transform(frame: pd.DataFrame, preprocessor: Preprocessor) -> np.ndarray:
    raw = frame.reindex(columns=list(preprocessor.features)).apply(
        pd.to_numeric, errors="coerce").to_numpy(float)
    raw = np.where(np.isfinite(raw), raw, preprocessor.median)
    raw = np.clip(raw, preprocessor.lower, preprocessor.upper)
    return (raw - preprocessor.mean) / preprocessor.scale


def median_bandwidth(values: np.ndarray, *, max_rows: int, seed: int) -> float:
    rng = np.random.default_rng(seed)
    if len(values) > max_rows:
        values = values[rng.choice(len(values), max_rows, replace=False)]
    distances = pdist(values, metric="euclidean")
    positive = distances[np.isfinite(distances) & (distances > 0)]
    if not len(positive):
        return 1.0
    return max(float(np.median(positive)), 1e-6)


def rff_embedding(
    values: np.ndarray,
    *,
    bandwidth: float,
    components: int,
    seed: int,
) -> np.ndarray:
    rng = np.random.default_rng(seed)
    weights = rng.normal(
        0.0, 1.0 / max(bandwidth, 1e-9),
        size=(values.shape[1], components),
    )
    phase = rng.uniform(0.0, 2.0 * np.pi, size=components)
    return np.sqrt(2.0 / components) * np.cos(values @ weights + phase)


def mmd2_from_embedding(embedding: np.ndarray, labels: np.ndarray) -> float:
    first = embedding[labels == 0]
    second = embedding[labels == 1]
    if not len(first) or not len(second):
        return float("nan")
    delta = first.mean(axis=0) - second.mean(axis=0)
    return float(delta @ delta)


def make_projections(dimension: int, count: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    directions = rng.normal(size=(dimension, count))
    norms = np.linalg.norm(directions, axis=0)
    norms[norms == 0] = 1.0
    return directions / norms


def sliced_energy(projected: np.ndarray, labels: np.ndarray) -> float:
    values = []
    for column in range(projected.shape[1]):
        distance = energy_distance(
            projected[labels == 0, column],
            projected[labels == 1, column],
        )
        values.append(float(distance * distance))
    return float(np.mean(values))


def mst_edges(values: np.ndarray) -> np.ndarray:
    distances = squareform(pdist(values, metric="euclidean"))
    tree = minimum_spanning_tree(distances).tocoo()
    return np.column_stack([tree.row, tree.col]).astype(int)


def hp_divergence(labels: np.ndarray, edges: np.ndarray) -> float:
    """Balanced-prior Friedman-Rafsky estimate of HP divergence."""
    labels = np.asarray(labels, dtype=int)
    if not len(labels):
        return float("nan")
    cross = int(np.sum(labels[edges[:, 0]] != labels[edges[:, 1]]))
    estimate = 1.0 - (2.0 * cross / len(labels))
    return float(np.clip(estimate, 0.0, 1.0))


def hp_bayes_error_bounds(divergence: float) -> tuple[float, float]:
    """Equal-prior HP bounds, clipped to the admissible [0, 0.5] range."""
    value = float(np.clip(divergence, 0.0, 1.0))
    lower = max(0.0, 0.5 - math.sqrt(value))
    upper = min(0.5, 0.5 * (1.0 - value))
    return lower, upper


def empirical_test(observed: float, null: list[float]) -> dict[str, float]:
    array = np.asarray(null, dtype=float)
    finite = array[np.isfinite(array)]
    if not len(finite):
        return {"observed": observed, "null_mean": float("nan"),
                "null_std": float("nan"), "null_z": float("nan"),
                "p_value": float("nan")}
    mean = float(finite.mean())
    std = float(finite.std(ddof=1)) if len(finite) > 1 else 0.0
    z_score = (observed - mean) / std if std > 0 else 0.0
    p_value = (1.0 + float(np.sum(finite >= observed))) / (len(finite) + 1.0)
    return {"observed": float(observed), "null_mean": mean, "null_std": std,
            "null_z": float(z_score), "p_value": float(p_value)}


def fisher_pvalue(values: Iterable[float]) -> float:
    array = np.asarray([value for value in values if np.isfinite(value)], dtype=float)
    if not len(array):
        return float("nan")
    statistic = -2.0 * np.log(np.clip(array, 1e-300, 1.0)).sum()
    return float(chi2.sf(statistic, 2 * len(array)))


def holm_adjust(values: dict[str, float]) -> dict[str, float]:
    finite = sorted(
        ((key, value) for key, value in values.items() if np.isfinite(value)),
        key=lambda item: item[1],
    )
    result = {key: float("nan") for key in values}
    running = 0.0
    total = len(finite)
    for rank, (key, value) in enumerate(finite):
        adjusted = min(1.0, (total - rank) * value)
        running = max(running, adjusted)
        result[key] = running
    return result


def _fold_specs(dataset: pd.DataFrame, config: dict[str, Any], horizon: int) -> list[dict[str, Any]]:
    wf = config["walk_forward"]
    folds = build_folds_adaptive(
        dataset,
        min_train_dates=int(wf["min_train_dates"]),
        val_dates=int(wf["val_dates"]),
        test_dates=int(wf["test_dates"]),
        step_dates=int(wf["step_dates"]),
        max_splits=10_000,
        forecast_horizon=horizon,
        materialize=False,
    )
    if wf.get("fold_selection") != "latest":
        raise ValueError("P-MATH-0 requires latest folds")
    return folds[-int(wf["max_splits"]):]


def _split(frame: pd.DataFrame, spec: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(frame["date"])
    guards = pd.to_datetime(frame[GUARD_COL])
    train = frame[
        dates.isin(spec["train_dates"])
        & guards.lt(pd.Timestamp(spec["val_start"]))
    ]
    test = frame[dates.isin(spec["test_dates"])]
    return train, test


def audit_fold(
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    *,
    config: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    sampling = config["sampling"]
    stats = config["statistics"]
    train_sample = balanced_by_date(
        train, max_per_class=int(sampling["classifier_train_max_per_class"]), seed=seed)
    test_sample = balanced_by_date(
        test, max_per_class=int(sampling["test_max_per_class"]), seed=seed + 1)
    if train_sample[TARGET].nunique() < 2 or test_sample[TARGET].nunique() < 2:
        raise ValueError("P-MATH-0 fold lacks both classes")

    preprocessor = fit_preprocessor(
        train_sample, features,
        lower_q=float(stats["winsor_lower"]),
        upper_q=float(stats["winsor_upper"]),
        max_missing_rate=float(stats["max_missing_rate"]),
    )
    train_x = transform(train_sample, preprocessor)
    test_x = transform(test_sample, preprocessor)
    train_y = train_sample[TARGET].to_numpy(int)
    test_y = test_sample[TARGET].to_numpy(int)
    bandwidth = median_bandwidth(
        train_x, max_rows=int(sampling["bandwidth_max_rows"]), seed=seed + 2)
    embedding = rff_embedding(
        test_x, bandwidth=bandwidth, components=int(stats["rff_components"]),
        seed=seed + 3)
    projections = make_projections(
        test_x.shape[1], int(stats["sliced_energy_projections"]), seed + 4)
    projected = test_x @ projections
    edges = mst_edges(test_x)
    classifier = LogisticRegression(
        C=1.0, max_iter=500, solver="lbfgs", random_state=seed)
    classifier.fit(train_x, train_y)
    classifier_score = classifier.predict_proba(test_x)[:, 1]

    observed = {
        "rff_mmd2": mmd2_from_embedding(embedding, test_y),
        "sliced_energy": sliced_energy(projected, test_y),
        "hp_divergence": hp_divergence(test_y, edges),
        "c2st_auc": float(roc_auc_score(test_y, classifier_score)),
    }
    null = {key: [] for key in observed}
    rng = np.random.default_rng(seed + 5)
    for _ in range(int(stats["permutations"])):
        labels = permute_within_date(test_y, test_sample["date"], rng)
        null["rff_mmd2"].append(mmd2_from_embedding(embedding, labels))
        null["sliced_energy"].append(sliced_energy(projected, labels))
        null["hp_divergence"].append(hp_divergence(labels, edges))
        null["c2st_auc"].append(float(roc_auc_score(labels, classifier_score)))
    metrics = {
        key: empirical_test(value, null[key]) for key, value in observed.items()
    }
    lower, upper = hp_bayes_error_bounds(observed["hp_divergence"])
    return {
        "rows_train_balanced": int(len(train_sample)),
        "rows_test_balanced": int(len(test_sample)),
        "dates_test": int(test_sample["date"].nunique()),
        "features_used": len(preprocessor.features),
        "bandwidth": bandwidth,
        "hp_bayes_error_lower": lower,
        "hp_bayes_error_upper": upper,
        "metrics": metrics,
    }


def summarize_task(folds: list[dict[str, Any]], gates: dict[str, Any]) -> dict[str, Any]:
    alpha = float(gates["alpha"])
    methods = ("rff_mmd2", "sliced_energy", "hp_divergence", "c2st_auc")
    summary: dict[str, Any] = {"folds": len(folds), "methods": {}}
    for method in methods:
        p_values = [row["metrics"][method]["p_value"] for row in folds]
        z_scores = [row["metrics"][method]["null_z"] for row in folds]
        observed = [row["metrics"][method]["observed"] for row in folds]
        summary["methods"][method] = {
            "median_observed": float(np.nanmedian(observed)),
            "median_null_z": float(np.nanmedian(z_scores)),
            "fold_reject_rate": float(np.mean(np.asarray(p_values) <= alpha)),
            "fisher_p_value": fisher_pvalue(p_values),
        }
    aucs = [row["metrics"]["c2st_auc"]["observed"] for row in folds]
    summary["classifier_auc_median"] = float(np.nanmedian(aucs))
    summary["classifier_auc_pass_fold_rate"] = float(
        np.mean(np.asarray(aucs) >= float(gates["classifier_auc_median_min"])))
    summary["hp_bayes_error_lower_median"] = float(np.nanmedian(
        [row["hp_bayes_error_lower"] for row in folds]))
    summary["hp_bayes_error_upper_median"] = float(np.nanmedian(
        [row["hp_bayes_error_upper"] for row in folds]))
    return summary


def apply_global_gates(summaries: dict[str, Any], gates: dict[str, Any]) -> None:
    p_values = {
        f"{task}:{method}": details["fisher_p_value"]
        for task, summary in summaries.items()
        for method, details in summary["methods"].items()
    }
    adjusted = holm_adjust(p_values)
    for task, summary in summaries.items():
        passed_nonparametric = []
        for method in ("rff_mmd2", "sliced_energy", "hp_divergence"):
            details = summary["methods"][method]
            details["holm_fisher_p_value"] = adjusted[f"{task}:{method}"]
            passed = (
                details["holm_fisher_p_value"] <= float(gates["alpha"])
                and details["fold_reject_rate"]
                >= float(gates["nonparametric_fold_reject_rate_min"])
                and details["median_null_z"]
                >= float(gates["nonparametric_median_null_z_min"])
            )
            details["passes"] = bool(passed)
            passed_nonparametric.append(passed)
        c2st = summary["methods"]["c2st_auc"]
        c2st["holm_fisher_p_value"] = adjusted[f"{task}:c2st_auc"]
        statistical = sum(passed_nonparametric) >= int(gates["nonparametric_methods_min"])
        operational = (
            summary["classifier_auc_median"] >= float(gates["classifier_auc_median_min"])
            and summary["classifier_auc_pass_fold_rate"]
            >= float(gates["classifier_auc_pass_fold_rate_min"])
            and c2st["holm_fisher_p_value"] <= float(gates["alpha"])
        )
        hp_informative = (
            summary["hp_bayes_error_upper_median"]
            <= float(gates["hp_bayes_error_upper_median_max"]))
        summary["gate_checks"] = {
            "stable_nonparametric_separation": bool(statistical),
            "operational_classifier_separation": bool(operational),
            "hp_bound_informative": bool(hp_informative),
        }
        if statistical and operational:
            summary["verdict"] = "STABLE_OPERATIONAL_SEPARATION"
        elif statistical:
            summary["verdict"] = "WEAK_DISTRIBUTION_SHIFT_ONLY"
        else:
            summary["verdict"] = "NO_STABLE_SEPARATION"


def run(args: argparse.Namespace) -> Path:
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if int(config["horizon"]) != args.horizon:
        raise ValueError("P-MATH-0 config/CLI horizon mismatch")
    if args.permutations is not None:
        config["statistics"]["permutations"] = int(args.permutations)
    if args.max_folds is not None:
        config["walk_forward"]["max_splits"] = int(args.max_folds)
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, args.batch_id, args.horizon)
    if args.max_symbols:
        symbols = symbols[:args.max_symbols]
    profile = load_profile(Path(args.state_profile or config["state_profile"]))
    pool, features = build_oracle_dataset(
        engine, args.batch_id, symbols,
        start_date=args.start_date, end_date=args.end_date,
        horizon=args.horizon, require_global_rank=False, need_targets=False,
        feature_whitelist=profile["feature_columns"],
        generator_options=profile["generator_options"],
    )
    if pool.empty:
        raise ValueError("Empty P-MATH-0 feature panel")
    pool["date"] = pd.to_datetime(pool["date"]).dt.normalize()
    pool["symbol"] = pool["symbol"].astype(str).str.upper()
    gate = _load_gate(
        Path("artifacts/models") / args.batch_id / "_oracle_oof_gate.parquet",
        float(config["pool_pct"]),
    )
    eligible = gate[gate["shared_oracle_eligible"]][
        ["date", "symbol", ORACLE_GATE_SCORE_COL]]
    pool = pool.merge(eligible, on=["date", "symbol"], how="inner", validate="one_to_one")
    pool = pool.dropna(subset=[DECILE, GUARD_COL])
    specs = _fold_specs(pool, config, args.horizon)
    if not specs:
        raise ValueError("No P-MATH-0 walk-forward folds")
    output = args.output or Path("artifacts/research/pmath0_separability") / (
        datetime.now(UTC).strftime("pmath0-%Y%m%d%H%M%S"))
    output.mkdir(parents=True, exist_ok=False)

    fold_rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    seed = int(config["statistics"]["random_seed"])
    for task_index, task in enumerate(config["tasks"]):
        task_pool = attach_task(pool, task)
        task_folds: list[dict[str, Any]] = []
        for fold_index, spec in enumerate(specs):
            train, test = _split(task_pool, spec)
            LOGGER.info(
                "P-MATH-0 task=%s fold=%d train=%d test=%d",
                task, fold_index, len(train), len(test))
            result = audit_fold(
                train, test, features, config=config,
                seed=seed + task_index * 10000 + fold_index * 100,
            )
            result.update({
                "task": task, "fold_index": fold_index,
                "test_start": spec["t_start"], "test_end": spec["t_end"],
            })
            task_folds.append(result)
            for method, metrics in result["metrics"].items():
                fold_rows.append({
                    "task": task, "fold_index": fold_index,
                    "test_start": spec["t_start"], "test_end": spec["t_end"],
                    "method": method, **metrics,
                    "rows_test_balanced": result["rows_test_balanced"],
                    "features_used": result["features_used"],
                    "hp_bayes_error_lower": result["hp_bayes_error_lower"],
                    "hp_bayes_error_upper": result["hp_bayes_error_upper"],
                })
        summaries[task] = summarize_task(task_folds, config["gates"])
        summaries[task]["fold_details"] = task_folds
    apply_global_gates(summaries, config["gates"])
    pd.DataFrame(fold_rows).to_csv(output / "fold_metrics.csv", index=False)
    report = {
        "experiment": config["experiment"],
        "status": "COMPLETED_RESEARCH_ONLY",
        "batch_id": args.batch_id,
        "horizon": args.horizon,
        "period": [args.start_date, args.end_date],
        "pool": {
            "rows": int(len(pool)), "dates": int(pool["date"].nunique()),
            "symbols": int(pool["symbol"].nunique()),
            "first_date": str(pool["date"].min().date()),
            "last_date": str(pool["date"].max().date()),
        },
        "fold_coverage": {
            "folds": len(specs), "first_test_start": specs[0]["t_start"],
            "last_test_end": specs[-1]["t_end"], "selection": "latest",
        },
        "feature_count_requested": len(features),
        "config": config,
        "tasks": summaries,
        "serving_changed": False,
        "database_writes": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"P-MATH-0 terminé: {output}")
    for task, summary in summaries.items():
        print(task, summary["verdict"], f"AUC={summary['classifier_auc_median']:.4f}")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--start-date", default="2016-01-01")
    parser.add_argument("--end-date", default="2025-12-31")
    parser.add_argument("--state-profile")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--max-symbols", type=int)
    parser.add_argument("--max-folds", type=int)
    parser.add_argument("--permutations", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if args.horizon != 20:
        parser.error("P-MATH-0 primary contract is frozen at H20")
    if args.start_date > args.end_date:
        parser.error("invalid date window")
    if args.permutations is not None and args.permutations < 9:
        parser.error("permutations must be >= 9")
    run(args)


if __name__ == "__main__":
    main()
