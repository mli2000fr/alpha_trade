"""E7-B: modèles KEEP/EXIT et replay économique Walk-Forward purgé.

Les modèles restent des artefacts de recherche. Le critère primaire n'est pas
le F1 état par état, mais le rendement net apparié obtenu en exécutant la
première décision EXIT de chaque trade contre le lifecycle H20 témoin.
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from modelFactory.multi_horizon_oracle_rolling import RollingConfig, block_bootstrap_mean
from modelFactory.position_keep_exit_dataset import FEATURE_COLUMNS

LOGGER = logging.getLogger(__name__)
MODEL_FEATURES = [column for column in FEATURE_COLUMNS if column not in {
    "remaining_sessions_h20", "current_pnl_gross", "distance_to_tp",
}]
CLASSIFICATION_MODELS = ("logistic_keep", "lightgbm_keep")
MODELS = (*CLASSIFICATION_MODELS, "lightgbm_advantage")


@dataclass(frozen=True, slots=True)
class WalkForwardConfig:
    min_train_dates: int = 504
    val_dates: int = 126
    test_dates: int = 126
    step_dates: int = 126
    max_splits: int = 8
    bootstrap_samples: int = 2_000
    random_seed: int = 42

    def __post_init__(self) -> None:
        if min(
            self.min_train_dates, self.val_dates, self.test_dates,
            self.step_dates, self.max_splits,
        ) <= 0:
            raise ValueError("Les paramètres Walk-Forward doivent être positifs.")


def build_purged_folds(states: pd.DataFrame, config: WalkForwardConfig) -> list[dict[str, Any]]:
    """Construit train/validation/test et purge par vraie fin de label."""
    required = {"state_date", "entry_date", "label_end_date", "trade_id"}
    missing = required - set(states.columns)
    if missing:
        raise ValueError(f"Colonnes de purge absentes: {sorted(missing)}")
    frame = states.copy()
    for column in ("state_date", "entry_date", "label_end_date"):
        frame[column] = pd.to_datetime(frame[column], errors="coerce").dt.normalize()
    dates = pd.Index(sorted(frame["state_date"].dropna().unique()))
    folds: list[dict[str, Any]] = []
    train_end = config.min_train_dates
    while len(folds) < config.max_splits:
        val_end = train_end + config.val_dates
        test_end = val_end + config.test_dates
        if test_end > len(dates):
            break
        val_start = pd.Timestamp(dates[train_end])
        test_start = pd.Timestamp(dates[val_end])
        test_last = pd.Timestamp(dates[test_end - 1])
        train = frame[
            (frame["state_date"] < val_start)
            & (frame["label_end_date"] < val_start)
        ].copy()
        validation = frame[
            frame["state_date"].isin(dates[train_end:val_end])
            & (frame["entry_date"] >= val_start)
            & (frame["label_end_date"] < test_start)
        ].copy()
        test = frame[
            frame["state_date"].isin(dates[val_end:test_end])
            & (frame["entry_date"] >= test_start)
        ].copy()
        if not train.empty and not validation.empty and not test.empty:
            train_ids = set(train["trade_id"])
            val_ids = set(validation["trade_id"])
            test_ids = set(test["trade_id"])
            if train_ids & val_ids or train_ids & test_ids or val_ids & test_ids:
                raise AssertionError("Un trade traverse plusieurs partitions Walk-Forward.")
            folds.append({
                "fold": len(folds), "val_start": val_start,
                "test_start": test_start, "test_end": test_last,
                "train": train, "validation": validation, "test": test,
            })
        train_end += config.step_dates
    return folds


def equal_trade_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.groupby("trade_id")["trade_id"].transform("size").to_numpy(dtype=float)
    weights = 1.0 / counts
    return weights / weights.mean()


def _finite_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[MODEL_FEATURES].replace([np.inf, -np.inf], np.nan)


def fit_platt(y: np.ndarray, raw_probability: np.ndarray, weights: np.ndarray) -> LogisticRegression | None:
    if np.unique(y).size < 2:
        return None
    clipped = np.clip(raw_probability, 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1.0, max_iter=500, random_state=42)
    calibrator.fit(logit, y, sample_weight=weights)
    return calibrator


def apply_platt(calibrator: LogisticRegression | None, raw_probability: np.ndarray) -> np.ndarray:
    if calibrator is None:
        return np.asarray(raw_probability, dtype=float)
    clipped = np.clip(raw_probability, 1e-6, 1 - 1e-6)
    logit = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
    return calibrator.predict_proba(logit)[:, 1]


def fit_predict_models(
    train: pd.DataFrame, validation: pd.DataFrame, test: pd.DataFrame,
    *, seed: int,
) -> dict[str, dict[str, np.ndarray]]:
    x_train, x_val, x_test = map(_finite_matrix, (train, validation, test))
    y_train = train["label_keep"].astype(int).to_numpy()
    y_val = validation["label_keep"].astype(int).to_numpy()
    weights_train = equal_trade_weights(train)
    weights_val = equal_trade_weights(validation)
    predictions: dict[str, dict[str, np.ndarray]] = {}

    logistic = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
        ("scaler", StandardScaler()),
        ("model", LogisticRegression(C=0.2, max_iter=1_000, random_state=seed)),
    ])
    logistic.fit(x_train, y_train, model__sample_weight=weights_train)
    raw_val = logistic.predict_proba(x_val)[:, 1]
    raw_test = logistic.predict_proba(x_test)[:, 1]
    calibrator = fit_platt(y_val, raw_val, weights_val)
    predictions["logistic_keep"] = {
        "validation": apply_platt(calibrator, raw_val),
        "test": apply_platt(calibrator, raw_test),
    }

    classifier = lgb.LGBMClassifier(
        objective="binary", n_estimators=500, learning_rate=0.03,
        max_depth=4, num_leaves=15, min_child_samples=200,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1,
        reg_lambda=1.0, random_state=seed, n_jobs=4, verbosity=-1,
    )
    classifier.fit(
        x_train, y_train, sample_weight=weights_train,
        eval_set=[(x_val, y_val)], eval_metric="binary_logloss",
        callbacks=[lgb.early_stopping(40, verbose=False)],
    )
    raw_val = classifier.predict_proba(x_val)[:, 1]
    raw_test = classifier.predict_proba(x_test)[:, 1]
    calibrator = fit_platt(y_val, raw_val, weights_val)
    predictions["lightgbm_keep"] = {
        "validation": apply_platt(calibrator, raw_val),
        "test": apply_platt(calibrator, raw_test),
    }

    regressor = lgb.LGBMRegressor(
        objective="huber", n_estimators=500, learning_rate=0.03,
        max_depth=4, num_leaves=15, min_child_samples=200,
        subsample=0.8, colsample_bytree=0.8, reg_alpha=0.1,
        reg_lambda=1.0, random_state=seed, n_jobs=4, verbosity=-1,
    )
    regressor.fit(
        x_train, train["target_keep_advantage"].to_numpy(),
        sample_weight=weights_train,
        eval_set=[(x_val, validation["target_keep_advantage"].to_numpy())],
        eval_metric="l1", callbacks=[lgb.early_stopping(40, verbose=False)],
    )
    predictions["lightgbm_advantage"] = {
        "validation": regressor.predict(x_val), "test": regressor.predict(x_test),
    }
    return predictions


def replay_first_exit(
    states: pd.DataFrame, scores: np.ndarray, *, threshold: float,
) -> pd.DataFrame:
    """Exécute la première décision EXIT; sinon conserve le résultat H20."""
    frame = states.copy()
    frame["decision_score"] = np.asarray(scores, dtype=float)
    frame = frame.sort_values(["trade_id", "state_date"])
    rows: list[dict[str, Any]] = []
    for trade_id, group in frame.groupby("trade_id", sort=False):
        exits = group[group["decision_score"] < threshold]
        baseline = float(group.iloc[0]["keep_terminal_net"])
        if exits.empty:
            policy_return = baseline
            exit_state_date = pd.NaT
            exited = False
        else:
            chosen = exits.iloc[0]
            policy_return = float(chosen["immediate_exit_net"])
            exit_state_date = chosen["state_date"]
            exited = True
        rows.append({
            "trade_id": trade_id, "signal_date": group.iloc[0]["signal_date"],
            "symbol": group.iloc[0]["symbol"], "baseline_return": baseline,
            "policy_return": policy_return, "delta": policy_return - baseline,
            "model_exit": exited, "model_exit_state_date": exit_state_date,
        })
    return pd.DataFrame(rows)


def select_threshold(validation: pd.DataFrame, scores: np.ndarray, *, classifier: bool) -> dict[str, float]:
    grid = (
        np.linspace(0.20, 0.80, 13).tolist() if classifier
        else [-np.inf, -0.02, -0.01, -0.005, -0.0025, 0.0, 0.0025, 0.005, 0.01, 0.02]
    )
    # Le seuil sentinelle signifie « ne jamais sortir » et empêche de forcer
    # une politique lorsque la validation ne bat pas le témoin.
    if classifier:
        grid = [-np.inf, *grid]
    best: dict[str, float] | None = None
    for threshold in grid:
        replay = replay_first_exit(validation, scores, threshold=float(threshold))
        candidate = {
            "threshold": float(threshold), "mean_return": float(replay["policy_return"].mean()),
            "mean_delta": float(replay["delta"].mean()),
            "exit_rate": float(replay["model_exit"].mean()),
        }
        if best is None or (candidate["mean_return"], -candidate["exit_rate"]) > (
            best["mean_return"], -best["exit_rate"]
        ):
            best = candidate
    assert best is not None
    return best


def _safe_auc(y: pd.Series, scores: np.ndarray) -> float:
    return float(roc_auc_score(y, scores)) if y.nunique() > 1 else np.nan


def run_walk_forward(states: pd.DataFrame, config: WalkForwardConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    folds = build_purged_folds(states, config)
    if len(folds) < 3:
        raise ValueError(f"Nombre de folds E7-B insuffisant: {len(folds)}")
    prediction_rows: list[pd.DataFrame] = []
    metrics: list[dict[str, Any]] = []
    for fold in folds:
        predictions = fit_predict_models(
            fold["train"], fold["validation"], fold["test"],
            seed=config.random_seed + fold["fold"],
        )
        for model_name, model_predictions in predictions.items():
            classifier = model_name in CLASSIFICATION_MODELS
            selected = select_threshold(
                fold["validation"], model_predictions["validation"], classifier=classifier,
            )
            replay = replay_first_exit(
                fold["test"], model_predictions["test"], threshold=selected["threshold"],
            )
            replay["fold"] = fold["fold"]
            replay["model"] = model_name
            replay["threshold"] = selected["threshold"]
            prediction_rows.append(replay)
            if classifier:
                state_metric = {
                    "state_auc": _safe_auc(fold["test"]["label_keep"], model_predictions["test"]),
                    "state_brier": float(brier_score_loss(
                        fold["test"]["label_keep"], model_predictions["test"]
                    )),
                    "state_spearman_advantage": float(spearmanr(
                        model_predictions["test"], fold["test"]["target_keep_advantage"],
                        nan_policy="omit",
                    ).statistic),
                }
            else:
                state_metric = {
                    "state_auc": np.nan, "state_brier": np.nan,
                    "state_spearman_advantage": float(spearmanr(
                        model_predictions["test"], fold["test"]["target_keep_advantage"],
                        nan_policy="omit",
                    ).statistic),
                }
            metrics.append({
                "fold": fold["fold"], "model": model_name,
                "val_start": fold["val_start"], "test_start": fold["test_start"],
                "test_end": fold["test_end"], "train_states": len(fold["train"]),
                "validation_states": len(fold["validation"]), "test_states": len(fold["test"]),
                "test_trades": len(replay), "selected_threshold": selected["threshold"],
                "validation_delta": selected["mean_delta"],
                "baseline_return": replay["baseline_return"].mean(),
                "policy_return": replay["policy_return"].mean(),
                "mean_delta": replay["delta"].mean(),
                "exit_rate": replay["model_exit"].mean(),
                "win_rate": replay["policy_return"].gt(0).mean(), **state_metric,
            })
    return pd.concat(prediction_rows, ignore_index=True), pd.DataFrame(metrics)


def summarize(policy_trades: pd.DataFrame, folds: pd.DataFrame, config: WalkForwardConfig) -> dict[str, Any]:
    def finite_mean(values: pd.Series) -> float | None:
        value = float(values.mean())
        return value if np.isfinite(value) else None

    models: dict[str, Any] = {}
    for model, trades in policy_trades.groupby("model", sort=False):
        daily = trades.groupby("signal_date")["delta"].mean().sort_index()
        low, high = block_bootstrap_mean(
            daily, RollingConfig(bootstrap_samples=config.bootstrap_samples)
        )
        fold_group = folds[folds["model"].eq(model)]
        models[model] = {
            "test_trades": int(len(trades)), "folds": int(fold_group["fold"].nunique()),
            "baseline_mean_return": float(trades["baseline_return"].mean()),
            "policy_mean_return": float(trades["policy_return"].mean()),
            "mean_delta": float(trades["delta"].mean()),
            "paired_daily_delta": float(daily.mean()),
            "paired_daily_ci95": [low, high],
            "positive_fold_rate": float(fold_group["mean_delta"].gt(0).mean()),
            "mean_exit_rate": float(trades["model_exit"].mean()),
            "mean_state_auc": finite_mean(fold_group["state_auc"]),
            "mean_state_brier": finite_mean(fold_group["state_brier"]),
            "mean_state_spearman_advantage": finite_mean(fold_group["state_spearman_advantage"]),
        }
    champion = max(models, key=lambda name: models[name]["mean_delta"])
    result = models[champion]
    low = result["paired_daily_ci95"][0]
    verdict = (
        "GO_RESEARCH" if result["folds"] >= 5 and result["mean_delta"] > 0
        and np.isfinite(low) and low > 0 and result["positive_fold_rate"] >= 0.60
        else "WEAK_SIGNAL" if result["mean_delta"] > 0 and result["positive_fold_rate"] >= 0.50
        else "NO_GO"
    )
    return {"models": models, "champion": champion, "verdict": verdict,
            "promotion_authorized": False}


def run(dataset_artifact: Path, *, output_root: Path, config: WalkForwardConfig) -> Path:
    states_path = dataset_artifact / "position_states.parquet"
    source_report_path = dataset_artifact / "report.json"
    if not states_path.is_file() or not source_report_path.is_file():
        raise ValueError("Artefact E7-A incomplet.")
    source_report = json.loads(source_report_path.read_text(encoding="utf-8"))
    if source_report.get("stage") != "E7-A_DATASET_AUDIT":
        raise ValueError("Le dossier source n'est pas un artefact E7-A.")
    states = pd.read_parquet(states_path)
    policy_trades, fold_metrics = run_walk_forward(states, config)
    summary = summarize(policy_trades, fold_metrics, config)
    run_id = f"position-keep-exit-wf-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    policy_trades.to_parquet(output / "oos_policy_trades.parquet", index=False)
    fold_metrics.to_csv(output / "fold_metrics.csv", index=False)
    report = {
        "schema_version": 1, "run_id": run_id,
        "experiment": "e7_daily_position_keep_exit_walk_forward",
        "stage": "E7-B_WALK_FORWARD", "status": "complete",
        "research_only": True, "source_dataset_artifact": str(dataset_artifact),
        "generated_at": datetime.now(UTC).isoformat(), "config": asdict(config),
        "model_features": MODEL_FEATURES,
        "target_contract": {
            "classifier": "label_keep",
            "regressor": "target_keep_advantage",
            "primary_metric": "paired net return of first EXIT versus fixed_h20",
            "threshold_selection": "validation only, no-exit sentinel included",
        },
        "split_contract": {
            "chronological": True, "grouped_by_trade_id": True,
            "train_purge": "label_end_date < val_start",
            "validation_purge": "label_end_date < test_start",
            "test_cohort": "entry_date >= test_start",
            "equal_trade_training_weights": True,
        },
        **summary,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E7-B terminé: %s verdict=%s", output, summary["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-artifact", type=Path, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/position_keep_exit"))
    parser.add_argument("--wf-min-train-size", type=int, default=504)
    parser.add_argument("--wf-val-size", type=int, default=126)
    parser.add_argument("--wf-test-size", type=int, default=126)
    parser.add_argument("--wf-step-size", type=int, default=126)
    parser.add_argument("--wf-max-splits", type=int, default=8)
    parser.add_argument("--bootstrap-samples", type=int, default=2_000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    print(run(
        args.dataset_artifact, output_root=args.output_root,
        config=WalkForwardConfig(
            min_train_dates=args.wf_min_train_size, val_dates=args.wf_val_size,
            test_dates=args.wf_test_size, step_dates=args.wf_step_size,
            max_splits=args.wf_max_splits, bootstrap_samples=args.bootstrap_samples,
        ),
    ))


if __name__ == "__main__":
    main()
