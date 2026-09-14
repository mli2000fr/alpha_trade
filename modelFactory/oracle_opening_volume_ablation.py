"""E20-C — ablation OOF appariée prix seul contre prix + volume.

Recherche uniquement. Les deux modèles mutualisés utilisent exactement les mêmes
événements, folds temporels et hyperparamètres. La seule différence autorisée est
l'ajout des variables de volume, transactions et VWAP observées avant 10:00 NY.
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
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle_opening_price_confirmation import _load_labeled_events
from modelFactory.oracle_opening_window_availability_audit import attach_next_oracle_session

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class E20CConfig:
    checkpoint_minutes: int = 30
    minimum_train_sessions: int = 504
    test_sessions: int = 126
    step_sessions: int = 126
    embargo_sessions: int = 20
    maximum_folds: int = 12
    minimum_folds: int = 6
    confidence_threshold: float = 0.55
    n_estimators: int = 200
    learning_rate: float = 0.03
    max_depth: int = 5
    num_leaves: int = 20
    min_child_samples: int = 150
    reg_alpha: float = 0.1
    reg_lambda: float = 0.1
    subsample: float = 0.8
    colsample_bytree: float = 0.8
    random_seed: int = 20260914
    n_jobs: int = 4
    minimum_auc_delta: float = 0.005
    maximum_brier_delta: float = -0.001
    minimum_tail_accuracy_delta: float = 0.005
    minimum_positive_fold_ratio: float = 0.60
    minimum_positive_semester_ratio: float = 0.60

    def __post_init__(self) -> None:
        if self.checkpoint_minutes not in (5, 15, 30, 60):
            raise ValueError("Checkpoint E20-C invalide.")
        if self.embargo_sessions < 0 or self.minimum_train_sessions < 2:
            raise ValueError("Fenêtres temporelles E20-C invalides.")


PRICE_BASE = (
    "directional_oracle_proba_extreme", "directional_oracle_extreme_pct",
)


def feature_columns(checkpoint: int) -> tuple[list[str], list[str]]:
    checkpoints = tuple(item for item in (5, 15, 30, 60) if item <= checkpoint)
    price = list(PRICE_BASE)
    for minute in checkpoints:
        price.extend([
            f"return_{minute}m", f"range_{minute}m", f"max_up_{minute}m",
            f"max_down_{minute}m", f"close_location_{minute}m",
        ])
    volume: list[str] = []
    for minute in checkpoints:
        volume.extend([
            f"log_volume_{minute}m", f"log_trades_{minute}m",
            f"log_average_trade_size_{minute}m", f"vwap_return_{minute}m",
            f"volume_rank_{minute}m", f"trade_count_rank_{minute}m",
            f"average_trade_size_rank_{minute}m",
        ])
    if checkpoint >= 15:
        volume.extend(["volume_share_5_15", "trade_share_5_15"])
    if checkpoint >= 30:
        volume.extend(["volume_share_5_30", "volume_share_15_30",
                       "trade_share_5_30", "trade_share_15_30"])
    if checkpoint >= 60:
        volume.extend(["volume_share_30_60", "trade_share_30_60"])
    return price, volume


def prepare_dataset(events: pd.DataFrame, features: pd.DataFrame, config: E20CConfig) -> pd.DataFrame:
    """Joint les événements et construit uniquement des transformations disponibles au checkpoint."""
    mapped = attach_next_oracle_session(events)
    joined = mapped.merge(
        features, left_on=["target_session", "symbol"],
        right_on=["session_date", "symbol"], how="inner", validate="one_to_one",
    )
    checkpoint = config.checkpoint_minutes
    joined = joined[joined[f"eligible_{checkpoint}m"].fillna(False).astype(bool)].copy()
    joined["date"] = pd.to_datetime(joined["date"]).dt.normalize()
    joined["target_session"] = pd.to_datetime(joined["target_session"]).dt.normalize()
    joined["semester"] = (
        joined["date"].dt.year.astype(str) + "H"
        + np.where(joined["date"].dt.month.le(6), "1", "2")
    )
    joined["target"] = pd.to_numeric(joined["future_return"], errors="coerce").gt(0).astype(int)
    joined = joined[pd.to_numeric(joined["future_return"], errors="coerce").notna()].copy()
    checkpoints = tuple(item for item in (5, 15, 30, 60) if item <= checkpoint)
    for minute in checkpoints:
        volume = pd.to_numeric(joined[f"volume_{minute}m"], errors="coerce")
        trades = pd.to_numeric(joined[f"trade_count_{minute}m"], errors="coerce")
        size = pd.to_numeric(joined[f"average_trade_size_{minute}m"], errors="coerce")
        vwap = pd.to_numeric(joined[f"vwap_{minute}m"], errors="coerce")
        opening = pd.to_numeric(joined["opening_price"], errors="coerce")
        joined[f"log_volume_{minute}m"] = np.log1p(volume.clip(lower=0))
        joined[f"log_trades_{minute}m"] = np.log1p(trades.clip(lower=0))
        joined[f"log_average_trade_size_{minute}m"] = np.log1p(size.clip(lower=0))
        joined[f"vwap_return_{minute}m"] = vwap.div(opening).sub(1)
        group = joined.groupby("target_session", sort=False)
        joined[f"volume_rank_{minute}m"] = group[f"log_volume_{minute}m"].rank(pct=True)
        joined[f"trade_count_rank_{minute}m"] = group[f"log_trades_{minute}m"].rank(pct=True)
        joined[f"average_trade_size_rank_{minute}m"] = group[
            f"log_average_trade_size_{minute}m"
        ].rank(pct=True)
    for numerator, denominator, name in (
        (5, 15, "5_15"), (5, 30, "5_30"), (15, 30, "15_30"),
        (30, 60, "30_60"),
    ):
        if denominator > checkpoint:
            continue
        joined[f"volume_share_{name}"] = (
            pd.to_numeric(joined[f"volume_{numerator}m"], errors="coerce")
            / pd.to_numeric(joined[f"volume_{denominator}m"], errors="coerce").replace(0, np.nan)
        )
        joined[f"trade_share_{name}"] = (
            pd.to_numeric(joined[f"trade_count_{numerator}m"], errors="coerce")
            / pd.to_numeric(joined[f"trade_count_{denominator}m"], errors="coerce").replace(0, np.nan)
        )
    return joined.sort_values(["date", "symbol"]).reset_index(drop=True)


def build_folds(dates: pd.Series, config: E20CConfig) -> list[dict[str, Any]]:
    unique = pd.DatetimeIndex(pd.to_datetime(dates).dropna().unique()).sort_values()
    folds: list[dict[str, Any]] = []
    cursor = config.minimum_train_sessions + config.embargo_sessions
    while cursor < len(unique):
        test_dates = unique[cursor: cursor + config.test_sessions]
        if len(test_dates) < config.test_sessions:
            break
        train_end = cursor - config.embargo_sessions
        folds.append({
            "fold": len(folds), "train_dates": unique[:train_end], "test_dates": test_dates,
            "train_start": unique[0], "train_end": unique[train_end - 1],
            "test_start": test_dates[0], "test_end": test_dates[-1],
        })
        cursor += config.step_sessions
    return folds[-config.maximum_folds:]


def _model(config: E20CConfig) -> lgb.LGBMClassifier:
    return lgb.LGBMClassifier(
        objective="binary", n_estimators=config.n_estimators,
        learning_rate=config.learning_rate, max_depth=config.max_depth,
        num_leaves=config.num_leaves, min_child_samples=config.min_child_samples,
        reg_alpha=config.reg_alpha, reg_lambda=config.reg_lambda,
        subsample=config.subsample, colsample_bytree=config.colsample_bytree,
        random_state=config.random_seed, n_jobs=config.n_jobs, verbosity=-1,
    )


def _safe_auc(target: pd.Series, probability: np.ndarray) -> float:
    return float(roc_auc_score(target, probability)) if target.nunique() == 2 else np.nan


def _metrics(frame: pd.DataFrame, probability: np.ndarray, config: E20CConfig) -> dict[str, float | int]:
    target = frame["target"].astype(int)
    decision = np.where(probability >= 0.5, 1, -1)
    confidence = np.maximum(probability, 1 - probability)
    selected = confidence >= config.confidence_threshold
    tails = pd.to_numeric(frame["oracle_decile"], errors="coerce").isin([1, 10]).to_numpy()
    signed = decision * pd.to_numeric(frame["future_return"], errors="coerce").to_numpy(float)
    return {
        "events": len(frame), "auc": _safe_auc(target, probability),
        "brier": float(brier_score_loss(target, probability)),
        "log_loss": float(log_loss(target, probability, labels=[0, 1])),
        "accuracy": float(accuracy_score(target, probability >= 0.5)),
        "tail_accuracy": float(np.mean((probability[tails] >= 0.5) == target.to_numpy()[tails])) if tails.any() else np.nan,
        "selected_events": int(selected.sum()),
        "selected_accuracy": float(np.mean((probability[selected] >= 0.5) == target.to_numpy()[selected])) if selected.any() else np.nan,
        "mean_signed_target_return": float(np.mean(signed)),
        "selected_mean_signed_target_return": float(np.mean(signed[selected])) if selected.any() else np.nan,
    }


def evaluate(dataset: pd.DataFrame, config: E20CConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    price_columns, volume_columns = feature_columns(config.checkpoint_minutes)
    all_columns = price_columns + volume_columns
    required = set(all_columns) | {"date", "target", "future_return", "oracle_decile", "semester"}
    missing = required - set(dataset.columns)
    if missing:
        raise ValueError(f"Features E20-C manquantes: {sorted(missing)}")
    folds = build_folds(dataset["date"], config)
    if len(folds) < config.minimum_folds:
        raise ValueError(f"Seulement {len(folds)} folds E20-C; minimum={config.minimum_folds}.")
    predictions: list[pd.DataFrame] = []
    rows: list[dict[str, Any]] = []
    for fold in folds:
        train = dataset[dataset["date"].isin(fold["train_dates"])]
        test = dataset[dataset["date"].isin(fold["test_dates"])]
        common = train[all_columns].notna().all(axis=1)
        train = train.loc[common]
        test = test.loc[test[all_columns].notna().all(axis=1)].copy()
        if train.empty or test.empty or train["target"].nunique() < 2:
            raise ValueError(f"Fold {fold['fold']} non entraînable après appariement.")
        fold_predictions: dict[str, np.ndarray] = {}
        for variant, columns in (("price_only", price_columns), ("price_plus_volume", all_columns)):
            model = _model(config)
            model.fit(train[columns], train["target"])
            probability = model.predict_proba(test[columns])[:, 1]
            fold_predictions[variant] = probability
            metrics = _metrics(test, probability, config)
            rows.append({
                "fold": fold["fold"], "variant": variant,
                "train_start": fold["train_start"], "train_end": fold["train_end"],
                "test_start": fold["test_start"], "test_end": fold["test_end"],
                "train_events": len(train), **metrics,
            })
        output = test[[
            "date", "target_session", "symbol", "target", "future_return",
            "oracle_decile", "semester",
        ]].copy()
        output["fold"] = fold["fold"]
        output["proba_price_only"] = fold_predictions["price_only"]
        output["proba_price_plus_volume"] = fold_predictions["price_plus_volume"]
        predictions.append(output)
    return pd.DataFrame(rows), pd.concat(predictions, ignore_index=True)


def summarize(folds: pd.DataFrame, predictions: pd.DataFrame, config: E20CConfig) -> dict[str, Any]:
    overall: dict[str, Any] = {}
    for variant, probability_column in (
        ("price_only", "proba_price_only"),
        ("price_plus_volume", "proba_price_plus_volume"),
    ):
        overall[variant] = _metrics(predictions, predictions[probability_column].to_numpy(), config)
    deltas = {
        key: float(overall["price_plus_volume"][key] - overall["price_only"][key])
        for key in ("auc", "brier", "log_loss", "accuracy", "tail_accuracy",
                    "selected_accuracy", "mean_signed_target_return",
                    "selected_mean_signed_target_return")
    }
    pivot = folds.pivot(index="fold", columns="variant", values=[
        "auc", "brier", "tail_accuracy", "mean_signed_target_return",
    ])
    auc_delta = pivot["auc"]["price_plus_volume"] - pivot["auc"]["price_only"]
    return_delta = (
        pivot["mean_signed_target_return"]["price_plus_volume"]
        - pivot["mean_signed_target_return"]["price_only"]
    )
    semester_rows = []
    for semester, group in predictions.groupby("semester"):
        base = _metrics(group, group["proba_price_only"].to_numpy(), config)
        volume = _metrics(group, group["proba_price_plus_volume"].to_numpy(), config)
        semester_rows.append({
            "semester": semester, "events": len(group),
            "auc_delta": volume["auc"] - base["auc"],
            "signed_return_delta": volume["mean_signed_target_return"] - base["mean_signed_target_return"],
        })
    semesters = pd.DataFrame(semester_rows)
    gates = {
        "minimum_folds": int(folds["fold"].nunique()) >= config.minimum_folds,
        "auc_delta": deltas["auc"] >= config.minimum_auc_delta,
        "brier_delta": deltas["brier"] <= config.maximum_brier_delta,
        "tail_accuracy_delta": deltas["tail_accuracy"] >= config.minimum_tail_accuracy_delta,
        "signed_return_not_degraded": deltas["mean_signed_target_return"] >= 0,
        "positive_fold_ratio": float(auc_delta.gt(0).mean()) >= config.minimum_positive_fold_ratio,
        "positive_semester_ratio": float(semesters["auc_delta"].gt(0).mean()) >= config.minimum_positive_semester_ratio,
    }
    verdict = "GO_ECONOMIC_REPLAY" if all(gates.values()) else "NO_GO_INCREMENTAL_VOLUME"
    return {
        "verdict": verdict, "overall": overall, "deltas": deltas,
        "gates": gates,
        "stability": {
            "folds": int(folds["fold"].nunique()),
            "positive_auc_fold_ratio": float(auc_delta.gt(0).mean()),
            "positive_return_fold_ratio": float(return_delta.gt(0).mean()),
            "semesters": int(len(semesters)),
            "positive_auc_semester_ratio": float(semesters["auc_delta"].gt(0).mean()),
            "by_semester": semester_rows,
        },
        "promotion_authorized": False,
    }


def run(*, batch_id: str, horizon: int, oracle_path: Path, features_path: Path,
        output_root: Path, config: E20CConfig) -> Path:
    engine = get_sqlalchemy_engine()
    events = _load_labeled_events(
        engine, batch_id=batch_id, horizon=horizon, oracle_path=oracle_path,
        start_date=None, end_date=None,
    )
    features = pd.read_parquet(features_path)
    dataset = prepare_dataset(events, features, config)
    fold_metrics, predictions = evaluate(dataset, config)
    result = summarize(fold_metrics, predictions, config)
    run_id = f"e20c-opening-volume-ablation-{datetime.now(UTC):%Y%m%d%H%M%S}"
    output = output_root / run_id
    output.mkdir(parents=True, exist_ok=False)
    fold_metrics.to_csv(output / "paired_metrics_by_fold.csv", index=False)
    predictions.to_parquet(output / "paired_oof_predictions.parquet", index=False)
    report = {
        "schema_version": 1, "experiment": "E20_C_OPENING_VOLUME_ABLATION",
        "status": "complete", "research_only": True, "production_change": False,
        "generated_at": datetime.now(UTC).isoformat(), "run_id": run_id,
        "source": {"batch_id": batch_id, "horizon": horizon,
                   "oracle_path": str(oracle_path), "features_path": str(features_path),
                   "provider": "alpaca", "feed": "sip"},
        "contract": {
            "comparison": "paired OOF price_only vs price_plus_volume",
            "target": "future_return > 0", "checkpoint_minutes": config.checkpoint_minutes,
            "embargo_sessions": config.embargo_sessions,
            "historical_acquisition_is_not_original_pit_availability": True,
            "economic_pnl_claimed": False,
        },
        "config": asdict(config),
        "population": {"oracle_events": len(events), "eligible_events": len(dataset),
                       "oof_events": len(predictions)},
        **result,
    }
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    LOGGER.info("E20-C terminé: %s verdict=%s", output, result["verdict"])
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-id", required=True)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--oracle-path", type=Path)
    parser.add_argument("--features-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path,
                        default=Path("artifacts/research/oracle_opening_volume_ablation"))
    parser.add_argument("--n-jobs", type=int, default=4)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))
    oracle_path = args.oracle_path or Path("artifacts/models") / args.batch_id / "_oracle_oof_gate.parquet"
    output = run(
        batch_id=args.batch_id, horizon=args.horizon, oracle_path=oracle_path,
        features_path=args.features_path, output_root=args.output_root,
        config=E20CConfig(n_jobs=args.n_jobs),
    )
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    print(f"E20-C terminé: {output}")
    print(report["verdict"])


if __name__ == "__main__":
    main()
