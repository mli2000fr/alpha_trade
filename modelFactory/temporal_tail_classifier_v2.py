"""Temporal D1/D10 V2, research-only Dataset A.

The module tests whether strictly past trajectories [J-N, ..., J] separate the
realized H20 cross-sectional D1 and D10 tails.  It writes only research
artifacts and never changes serving, prediction or application tables.
"""
from __future__ import annotations

import argparse
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import GUARD_COL, build_feature_matrix, load_oracle_targets
from modelFactory.oracle.leakage import assert_no_forbidden_features, assert_no_future_features

LOGGER = logging.getLogger(__name__)
TARGET = "tail_target"


@dataclass(frozen=True, slots=True)
class Fold:
    index: int
    test_start: pd.Timestamp
    test_end: pd.Timestamp


def load_config(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    required = {"base_features", "windows", "models", "walk_forward", "gates"}
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"Configuration Temporal V2 incomplète: {missing}")
    windows = [int(value) for value in payload["windows"]]
    if windows != [3, 5, 10]:
        raise ValueError("La campagne principale Temporal V2 exige N=3,5,10 exactement.")
    features = [str(value) for value in payload["base_features"]]
    if not 20 <= len(features) <= 30 or len(features) != len(set(features)):
        raise ValueError("Le budget principal exige 20 à 30 features de base uniques.")
    assert_no_forbidden_features(features)
    assert_no_future_features(features)
    return payload


def _rolling_slope(values: np.ndarray) -> float:
    if len(values) < 2 or not np.isfinite(values).all():
        return np.nan
    x = np.arange(len(values), dtype=float)
    return float(np.polyfit(x, values.astype(float), 1)[0])


def add_temporal_features(
    frame: pd.DataFrame,
    base_features: list[str],
    window: int,
    *,
    positive_fraction_features: set[str],
    acceleration_features: set[str],
) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    """Build causal features on N+1 observed sessions inside each symbol."""
    if window not in {3, 5, 10}:
        raise ValueError("Fenêtre Temporal V2 non pré-enregistrée.")
    result = frame.sort_values(["symbol", "date"]).copy()
    state, delta, shape = [], [], []
    for feature in base_features:
        if feature not in result:
            continue
        values = pd.to_numeric(result[feature], errors="coerce")
        result[feature] = values
        state.append(feature)
        grouped = result.groupby("symbol", sort=False)[feature]
        delta_name = f"{feature}__delta_{window}"
        result[delta_name] = values - grouped.shift(window)
        delta.append(delta_name)

        slope_name = f"{feature}__slope_{window}"
        std_name = f"{feature}__std_{window}"
        result[slope_name] = grouped.transform(
            lambda series: series.rolling(window + 1, min_periods=window + 1).apply(
                _rolling_slope, raw=True
            )
        )
        result[std_name] = grouped.transform(
            lambda series: series.rolling(window + 1, min_periods=window + 1).std()
        )
        shape.extend([slope_name, std_name])

        daily_change = grouped.diff()
        if feature in positive_fraction_features:
            name = f"{feature}__positive_fraction_{window}"
            valid = daily_change.notna().astype(float)
            positive = daily_change.gt(0).astype(float).where(daily_change.notna())
            numerator = positive.groupby(result["symbol"], sort=False).transform(
                lambda series: series.rolling(window, min_periods=window).sum()
            )
            denominator = valid.groupby(result["symbol"], sort=False).transform(
                lambda series: series.rolling(window, min_periods=window).sum()
            )
            result[name] = numerator / denominator.where(denominator.eq(window))
            shape.append(name)

        if feature in acceleration_features:
            name = f"{feature}__acceleration_{window}"
            recent = max(1, window // 2)
            older = window - recent
            recent_slope = grouped.transform(
                lambda series, size=recent: series.rolling(
                    size + 1, min_periods=size + 1
                ).apply(
                    _rolling_slope, raw=True
                )
            )
            shifted = result.groupby("symbol", sort=False)[feature].shift(recent)
            older_slope = shifted.groupby(result["symbol"], sort=False).transform(
                lambda series, size=older: series.rolling(
                    size + 1, min_periods=size + 1
                ).apply(
                    _rolling_slope, raw=True
                )
            )
            result[name] = recent_slope - older_slope
            shape.append(name)
    return result, {"state": state, "delta": delta, "shape": shape}


def make_folds(dates: pd.Series, config: dict[str, Any]) -> list[Fold]:
    unique = pd.DatetimeIndex(pd.to_datetime(dates).dropna().unique()).sort_values()
    minimum = int(config["min_train_sessions"])
    test_size = int(config["test_sessions"])
    step = int(config["step_sessions"])
    candidates: list[Fold] = []
    index = minimum
    while index + test_size <= len(unique):
        test_dates = unique[index:index + test_size]
        candidates.append(Fold(len(candidates), test_dates[0], test_dates[-1]))
        index += step
    maximum = int(config["max_splits"])
    return candidates[-maximum:]


def _date_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.groupby("date")["date"].transform("size").astype(float)
    weights = 1.0 / counts
    return (weights / weights.mean()).to_numpy(float)


def fit_predict(
    model_name: str,
    train: pd.DataFrame,
    test: pd.DataFrame,
    features: list[str],
    model_config: dict[str, Any],
    seed: int,
    threads: int,
) -> np.ndarray:
    x_train = train[features].replace([np.inf, -np.inf], np.nan)
    x_test = test[features].replace([np.inf, -np.inf], np.nan)
    y_train = train[TARGET].astype(int).to_numpy()
    if model_name == "logistic":
        imputer = SimpleImputer(strategy="median", add_indicator=True)
        scaler = StandardScaler()
        train_values = scaler.fit_transform(imputer.fit_transform(x_train))
        test_values = scaler.transform(imputer.transform(x_test))
        model = LogisticRegression(
            C=float(model_config.get("C", 1.0)),
            max_iter=int(model_config.get("max_iter", 1000)),
            random_state=seed,
        )
        model.fit(train_values, y_train, sample_weight=_date_weights(train))
        return model.predict_proba(test_values)[:, 1]

    from catboost import CatBoostClassifier, CatBoostRanker

    common = {
        "iterations": int(model_config.get("iterations", 300)),
        "depth": int(model_config.get("depth", 5)),
        "learning_rate": float(model_config.get("learning_rate", 0.03)),
        "random_seed": seed,
        "verbose": False,
        "allow_writing_files": False,
        "thread_count": threads,
    }
    if model_name == "catboost":
        model = CatBoostClassifier(loss_function="Logloss", eval_metric="AUC", **common)
        model.fit(x_train, y_train, sample_weight=_date_weights(train))
        return model.predict_proba(x_test)[:, 1]
    if model_name == "pairlogit":
        ordered = train.assign(_row=np.arange(len(train))).sort_values(["date", "_row"])
        model = CatBoostRanker(loss_function="PairLogit", **common)
        model.fit(
            ordered[features].replace([np.inf, -np.inf], np.nan),
            ordered[TARGET].astype(int),
            group_id=ordered["date"].dt.strftime("%Y-%m-%d"),
        )
        return np.asarray(model.predict(x_test), dtype=float)
    raise ValueError(f"Modèle Temporal V2 inconnu: {model_name}")


def _safe_auc(y: pd.Series | np.ndarray, score: pd.Series | np.ndarray) -> float | None:
    y_values = np.asarray(y)
    score_values = np.asarray(score, dtype=float)
    valid = np.isfinite(score_values) & pd.notna(y_values)
    if valid.sum() < 2 or len(np.unique(y_values[valid])) < 2:
        return None
    return float(roc_auc_score(y_values[valid].astype(int), score_values[valid]))


def _same_date_auc(frame: pd.DataFrame) -> pd.Series:
    values: dict[pd.Timestamp, float] = {}
    for date, group in frame.groupby("date", sort=True):
        auc = _safe_auc(group[TARGET], group["tail_polarity_score"])
        if auc is not None:
            values[pd.Timestamp(date)] = auc
    return pd.Series(values, dtype=float)


def evaluate_oof(frame: pd.DataFrame) -> dict[str, Any]:
    tails = frame[frame[TARGET].notna()].copy()
    same_date = _same_date_auc(tails)
    score_rank = tails.groupby("date")["tail_polarity_score"].rank(pct=True, method="average")
    top = tails[score_rank.gt(0.9)]
    bottom = tails[score_rank.le(0.1)]
    fold_auc = {
        str(int(fold)): auc
        for fold, group in tails.groupby("fold")
        if (auc := _safe_auc(group[TARGET], group["tail_polarity_score"])) is not None
    }
    year_auc = {
        str(int(year)): auc
        for year, group in tails.groupby(tails["date"].dt.year)
        if (auc := _safe_auc(group[TARGET], group["tail_polarity_score"])) is not None
    }
    buckets = tails.copy()
    buckets["score_bucket"] = np.ceil(
        buckets.groupby("date")["tail_polarity_score"].rank(
            method="first", pct=True
        ) * 10
    ).clip(1, 10).astype(int)
    bucket_table = buckets.groupby("score_bucket").agg(
        n=(TARGET, "size"), d10_rate=(TARGET, "mean"),
        mean_return=("future_return", "mean"), median_return=("future_return", "median"),
    ).reset_index()
    monotonic = bucket_table["score_bucket"].corr(bucket_table["d10_rate"], method="spearman")
    y = tails[TARGET].astype(int)
    raw_score = tails["tail_polarity_score"].astype(float)
    probability = raw_score.clip(1e-6, 1 - 1e-6) if raw_score.between(0, 1).all() else None
    predicted = raw_score.ge(float(raw_score.median())).astype(int)
    return {
        "rows": int(len(tails)),
        "dates": int(tails["date"].nunique()),
        "global_oof_auc": _safe_auc(y, raw_score),
        "mean_same_date_auc": float(same_date.mean()),
        "median_same_date_auc": float(same_date.median()),
        "std_same_date_auc": float(same_date.std()),
        "date_auc_gt_0_50_rate": float(same_date.gt(0.50).mean()),
        "date_auc_gt_0_55_rate": float(same_date.gt(0.55).mean()),
        "date_auc_gt_0_60_rate": float(same_date.gt(0.60).mean()),
        "top10_d10_rate": float(top[TARGET].mean()),
        "bottom10_d1_rate": float(1.0 - bottom[TARGET].mean()),
        "pairwise_accuracy": float(same_date.mean()),
        "fold_auc": fold_auc,
        "year_auc": year_auc,
        "positive_fold_rate": float(sum(v > 0.5 for v in fold_auc.values()) / len(fold_auc)),
        "positive_years": int(sum(v > 0.5 for v in year_auc.values())),
        "bucket_monotonic_spearman": float(monotonic),
        "buckets": bucket_table.to_dict(orient="records"),
        "secondary": {
            "average_precision": float(average_precision_score(y, raw_score)),
            "accuracy": float(accuracy_score(y, predicted)),
            "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
            "precision_d10": float(precision_score(y, predicted, zero_division=0)),
            "recall_d10": float(recall_score(y, predicted, zero_division=0)),
            "precision_d1": float(precision_score(1-y, 1-predicted, zero_division=0)),
            "recall_d1": float(recall_score(1-y, 1-predicted, zero_division=0)),
            "f1": float(f1_score(y, predicted, zero_division=0)),
            "log_loss": float(log_loss(y, probability)) if probability is not None else None,
            "brier": float(brier_score_loss(y, probability)) if probability is not None else None,
        },
    }


def audit_labels(labels: pd.DataFrame) -> dict[str, Any]:
    frame = labels[labels["oracle_decile"].isin([1, 10])].copy()
    frame["date"] = pd.to_datetime(frame["prediction_date"]).dt.normalize()
    frame["semester"] = frame["date"].dt.year.astype(str) + "H" + ((frame["date"].dt.month-1)//6+1).astype(str)

    def summarize(group: pd.DataFrame) -> dict[str, Any]:
        d1 = group[group["oracle_decile"].eq(1)]["future_return"]
        d10 = group[group["oracle_decile"].eq(10)]["future_return"]
        return {
            "rows": int(len(group)),
            "p_negative_given_d1": float(d1.lt(0).mean()),
            "p_positive_given_d10": float(d10.gt(0).mean()),
            "p_le_minus_3pct_given_d1": float(d1.le(-0.03).mean()),
            "p_ge_plus_3pct_given_d10": float(d10.ge(0.03).mean()),
            "d1_mean_return": float(d1.mean()), "d1_median_return": float(d1.median()),
            "d10_mean_return": float(d10.mean()), "d10_median_return": float(d10.median()),
        }

    daily = frame.groupby(["date", "oracle_decile"])["future_return"].mean().unstack()
    same_sign = np.sign(daily.get(1, pd.Series(dtype=float))) == np.sign(
        daily.get(10, pd.Series(dtype=float))
    )
    return {
        "global": summarize(frame),
        "by_year": {str(key): summarize(group) for key, group in frame.groupby(frame["date"].dt.year)},
        "by_semester": {str(key): summarize(group) for key, group in frame.groupby("semester")},
        "same_absolute_sign_date_rate": float(same_sign.mean()),
    }


def build_dataset(
    engine: Any,
    batch_id: str,
    gate_path: Path,
    profile_path: Path,
    config: dict[str, Any],
    cache_path: Path,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    gate = pd.read_parquet(gate_path)
    symbols = sorted(gate["symbol"].astype(str).str.upper().unique())
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    if cache_path.exists():
        features = pd.read_parquet(cache_path)
    else:
        features = build_feature_matrix(
            engine, symbols, start_date=config["start_date"], end_date=config["end_date"],
            feature_set="expert", generator_options=dict(profile.get("generator_options") or {}),
        )
        features.to_parquet(cache_path, index=False)
    features["date"] = pd.to_datetime(features["date"]).dt.normalize()
    available = [name for name in config["base_features"] if name in features]
    missing = sorted(set(config["base_features"]).difference(available))
    if len(available) < 20:
        raise ValueError(f"Budget temporel insuffisant: {len(available)} features disponibles.")
    labels = load_oracle_targets(engine, batch_id, int(config["target_horizon"]))
    labels = labels.rename(columns={"prediction_date": "date"})
    labels["date"] = pd.to_datetime(labels["date"]).dt.normalize()
    keep = ["date", "symbol", "oracle_decile", "oracle_pct_rank", "future_return", GUARD_COL]
    dataset = features[["date", "symbol", *available]].merge(
        labels[keep], on=["date", "symbol"], how="inner", validate="one_to_one"
    )
    dataset = dataset[
        dataset["date"].between(
            pd.Timestamp(config["start_date"]), pd.Timestamp(config["end_date"])
        )
    ].copy()
    dataset[TARGET] = np.where(
        dataset["oracle_decile"].eq(10), 1.0,
        np.where(dataset["oracle_decile"].eq(1), 0.0, np.nan),
    )
    return dataset, {
        "symbols": len(symbols), "rows": len(dataset), "dates": dataset["date"].nunique(),
        "base_features_available": available, "base_features_missing": missing,
        "survivorship_bias_risk": True,
    }


def run_variant(
    frame: pd.DataFrame,
    features: list[str],
    representation: str,
    window: int | None,
    model_name: str,
    config: dict[str, Any],
    threads: int,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    folds = make_folds(frame["date"], config["walk_forward"])
    outputs: list[pd.DataFrame] = []
    for fold in folds:
        train = frame[
            frame[TARGET].notna()
            & (pd.to_datetime(frame[GUARD_COL]) < fold.test_start)
            & (frame["date"] < fold.test_start)
        ].copy()
        test = frame[frame["date"].between(fold.test_start, fold.test_end)].copy()
        if train[TARGET].nunique() < 2 or test.empty:
            continue
        score = fit_predict(
            model_name, train, test, features,
            config["models"][model_name], int(config["seed"]), threads,
        )
        test = test[["date", "symbol", "oracle_decile", "future_return", TARGET]].copy()
        test["tail_polarity_score"] = score
        test["fold"] = fold.index
        test["representation"] = representation
        test["window"] = window
        test["model"] = model_name
        outputs.append(test)
    if not outputs:
        raise ValueError(f"Aucune prédiction OOF pour {representation}/{model_name}.")
    oof = pd.concat(outputs, ignore_index=True)
    metrics = evaluate_oof(oof)
    middle = oof[oof[TARGET].isna()].copy()
    tails = oof[oof[TARGET].notna()].copy()
    amplitude = pd.concat([
        tails.assign(amplitude_target=1), middle.assign(amplitude_target=0)
    ], ignore_index=True)
    daily_rank = amplitude.groupby("date")["tail_polarity_score"].rank(pct=True)
    amplitude["amplitude_score"] = (daily_rank - 0.5).abs()
    metrics["amplitude_auc_from_direction_confidence"] = _safe_auc(
        amplitude["amplitude_target"], amplitude["amplitude_score"]
    )
    return oof, metrics


def _markdown_report(report: dict[str, Any], comparison: pd.DataFrame) -> str:
    lines = [
        "# TEMPORAL D1/D10 CLASSIFIER REPORT — Dataset A", "",
        f"Verdict intermédiaire : **{report['verdict']}**", "",
        "## Label contract", "",
        "- Target : H20 `future_return`, déciles cross-sectionnels autoritatifs.",
        "- D1 = 0, D10 = 1 ; D2-D9 exclus du fit mais scorés en test.",
        "- Signal J, disponibilité du target contrôlée par `oracle_available_date`.",
        "- Fenêtre N = `[J-N,...,J]`, soit N+1 observations.", "",
        "## Comparaison OOF", "",
        comparison.to_markdown(index=False), "",
        "## Décision", "",
        "Dataset B n'est autorisé que si une représentation temporelle franchit le gate T2.",
        "Le statut de confirmation finale reste `UNAVAILABLE_ALREADY_OBSERVED`.", "",
    ]
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict[str, Any]:
    config = load_config(args.config)
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    dataset, population = build_dataset(
        get_sqlalchemy_engine(), args.batch_id, args.gate_path, args.profile_path,
        config, output / "base_feature_panel.parquet",
    )
    dataset.to_parquet(output / "dataset_a.parquet", index=False)
    labels = load_oracle_targets(get_sqlalchemy_engine(), args.batch_id, int(config["target_horizon"]))
    labels = labels[
        pd.to_datetime(labels["prediction_date"]).between(
            pd.Timestamp(config["start_date"]), pd.Timestamp(config["end_date"])
        )
    ].copy()
    label_audit = audit_labels(labels)
    base = population["base_features_available"]
    all_oof: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    temporal_frames: dict[int, tuple[pd.DataFrame, dict[str, list[str]]]] = {}
    for window in config["windows"]:
        temporal_frames[int(window)] = add_temporal_features(
            dataset, base, int(window),
            positive_fraction_features=set(config["positive_fraction_features"]),
            acceleration_features=set(config["acceleration_features"]),
        )
    variants: list[tuple[str, int | None, pd.DataFrame, list[str]]] = [
        ("T0_STATE", None, dataset, base)
    ]
    for window, (temporal, groups) in temporal_frames.items():
        variants.append((f"T1_STATE_DELTA_N{window}", window, temporal, groups["state"] + groups["delta"]))
        variants.append((f"T2_STATE_TRAJECTORY_N{window}", window, temporal,
                         groups["state"] + groups["delta"] + groups["shape"]))
    jobs = [
        (representation, window, frame, features, model_name)
        for representation, window, frame, features in variants
        for model_name in ("logistic", "catboost", "pairlogit")
    ]
    variant_dir = output / "variants"
    variant_dir.mkdir(exist_ok=True)

    def execute_variant(
        job: tuple[str, int | None, pd.DataFrame, list[str], str]
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        representation, window, frame, features, model_name = job
        LOGGER.info("Temporal V2 %s / %s (%d features)", representation, model_name, len(features))
        variant_stem = f"{representation.lower()}__{model_name}"
        variant_oof = variant_dir / f"{variant_stem}.parquet"
        variant_metrics = variant_dir / f"{variant_stem}.json"
        if variant_oof.exists():
            LOGGER.info("Reprise Temporal V2: %s déjà terminé", variant_stem)
            oof = pd.read_parquet(variant_oof)
            metrics = evaluate_oof(oof)
            middle = oof[oof[TARGET].isna()].copy()
            tails = oof[oof[TARGET].notna()].copy()
            amplitude = pd.concat([
                tails.assign(amplitude_target=1),
                middle.assign(amplitude_target=0),
            ], ignore_index=True)
            daily_rank = amplitude.groupby("date")["tail_polarity_score"].rank(pct=True)
            metrics["amplitude_auc_from_direction_confidence"] = _safe_auc(
                amplitude["amplitude_target"], (daily_rank - 0.5).abs()
            )
        else:
            oof, metrics = run_variant(
                frame, features, representation, window, model_name, config, args.threads
            )
            oof.to_parquet(variant_oof, index=False)
        variant_metrics.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        row = {
            "representation": representation, "window": window, "model": model_name,
            "features": len(features), "global_oof_auc": metrics["global_oof_auc"],
            "mean_same_date_auc": metrics["mean_same_date_auc"],
            "median_same_date_auc": metrics["median_same_date_auc"],
            "date_auc_gt_0_50_rate": metrics["date_auc_gt_0_50_rate"],
            "date_auc_gt_0_55_rate": metrics["date_auc_gt_0_55_rate"],
            "top10_d10_rate": metrics["top10_d10_rate"],
            "bottom10_d1_rate": metrics["bottom10_d1_rate"],
            "positive_fold_rate": metrics["positive_fold_rate"],
            "positive_years": metrics["positive_years"],
            "bucket_monotonic_spearman": metrics["bucket_monotonic_spearman"],
            "amplitude_auc": metrics["amplitude_auc_from_direction_confidence"],
            "metrics": metrics,
        }
        return oof, row

    with ThreadPoolExecutor(max_workers=args.parallel_variants) as executor:
        futures = {executor.submit(execute_variant, job): job for job in jobs}
        for completed, future in enumerate(as_completed(futures), start=1):
            oof, row = future.result()
            all_oof.append(oof)
            rows.append(row)
            LOGGER.info("Temporal V2 variantes terminées: %d/%d", completed, len(jobs))
    comparison = pd.DataFrame(rows)
    t0 = comparison[comparison["representation"].eq("T0_STATE")].set_index("model")
    comparison["delta_vs_t0"] = comparison.apply(
        lambda row: row["mean_same_date_auc"] - t0.loc[row["model"], "mean_same_date_auc"], axis=1
    )
    gates = config["gates"]
    comparison["passes_temporal_gate"] = (
        comparison["representation"].str.startswith("T2_")
        & comparison["delta_vs_t0"].ge(float(gates["min_delta_mean_same_date_auc_vs_t0"]))
        & comparison["positive_fold_rate"].ge(float(gates["min_positive_fold_rate"]))
        & comparison["positive_years"].ge(int(gates["min_positive_years"]))
        & comparison["bucket_monotonic_spearman"].ge(float(gates["min_bucket_monotonic_spearman"]))
    )
    verdict = "GO_NEXT_B" if bool(comparison["passes_temporal_gate"].any()) else "NO_GO_DATASET_A"
    serializable = comparison.drop(columns=["metrics"])
    serializable.to_csv(output / "comparison.csv", index=False)
    pd.concat(all_oof, ignore_index=True).to_parquet(output / "oof_predictions.parquet", index=False)
    report = {
        "schema_version": 1, "experiment": config["experiment"],
        "generated_at": datetime.now(UTC).isoformat(), "research_only": True,
        "batch_id": args.batch_id, "population": population,
        "label_contract": {
            "target_horizon": 20,
            "forward_return_definition": "global_oracle_labels.future_return H20",
            "d1_definition": "bottom 10% cross-sectionnel de prediction_date",
            "d10_definition": "top 10% cross-sectionnel de prediction_date",
            "universe_definition": "399 symboles du gate Oracle OOF du batch",
            "signal_date_definition": "prediction_date J",
            "target_available_at_rule": "oracle_available_date < test_start",
        },
        "label_audit": label_audit,
        "config": config,
        "results": rows,
        "comparison": serializable.to_dict(orient="records"),
        "verdict": verdict,
        "final_confirmation_status": config["confirmation_status"],
        "serving_ready": False,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    (output / "TEMPORAL_D1D10_CLASSIFIER_REPORT.md").write_text(
        _markdown_report(report, serializable.round(4)), encoding="utf-8"
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--gate-path", type=Path, required=True)
    parser.add_argument("--profile-path", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("config/research/temporal_d1d10_v2.json"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--parallel-variants", type=int, default=1)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    if args.parallel_variants < 1:
        parser.error("--parallel-variants doit être supérieur ou égal à 1")
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    report = run(args)
    print(json.dumps({"output": str(args.output), "verdict": report["verdict"]}))


if __name__ == "__main__":
    main()
