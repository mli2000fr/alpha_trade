"""modelFactory/trainer.py — Service d'entraînement mono-symbole."""
from __future__ import annotations

import json
import logging
import pickle
import uuid
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Optional

import numpy as np
import torch
from torch.utils.data import DataLoader

try:
    import lightning as L
    from lightning.pytorch.callbacks import EarlyStopping, ModelCheckpoint
except ImportError:  # pragma: no cover
    import pytorch_lightning as L  # type: ignore[no-redef]
    from pytorch_lightning.callbacks import EarlyStopping, ModelCheckpoint  # type: ignore[no-redef]

from sqlalchemy.engine import Engine

from modelFactory.calibration import PlattCalibrator, margin_from_logits
from modelFactory.config import TrainingConfig
from modelFactory.dataset import (
    FeatureScaler,
    SequenceDataset,
    SymbolDataModule,
    build_sequence_dataset,
    generate_walk_forward_splits,
)
from modelFactory.db_registry import (
    ensure_registry_entry,
    insert_metrics,
    insert_training_run,
    update_training_run,
)
from modelFactory.evaluation import align_sequence_rows, compute_threshold_metrics, optimize_decision_threshold
from modelFactory.features import get_feature_columns
from modelFactory.catboost_baseline import run_catboost_baseline
from modelFactory.lightgbm_baseline import run_lightgbm_baseline
from modelFactory.model import LSTMAttentionModule
from modelFactory.target_optimization import optimize_target_parameters

LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------

class TrainResult:
    """Résultat d'un entraînement mono-symbole."""

    def __init__(self, symbol: str, run_id: str, status: str, metrics: Optional[dict[str, Any]] = None,
                 skip_reason: Optional[str] = None) -> None:
        self.symbol = symbol
        self.run_id = run_id
        self.status = status
        self.metrics = metrics or {}
        self.skip_reason = skip_reason


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_best_epoch(checkpoint_path: Path) -> int | None:
    """Extrait l'epoch sauvegardée dans un checkpoint Lightning."""
    if not checkpoint_path.exists():
        return None
    try:
        payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
    except Exception:
        LOGGER.debug("Unable to read checkpoint epoch path=%s", checkpoint_path, exc_info=True)
        return None
    epoch = payload.get("epoch")
    return int(epoch) if isinstance(epoch, int) else None



def _build_loader(dataset: SequenceDataset | None, batch_size: int, *, shuffle: bool) -> DataLoader | None:
    if dataset is None:
        return None
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=False,
        num_workers=0,
        persistent_workers=False,
        pin_memory=False,
    )


def _selection_score_from_metrics(metrics: dict[str, Any]) -> float:
    return float(
        metrics.get("threshold_business_score")
        or metrics.get("auc")
        or metrics.get("directional_accuracy")
        or 0.0
    )


def _selection_score_from_result(result: dict[str, Any]) -> float:
    if not result or result.get("status") != "completed":
        return float("-inf")
    return float(
        result.get("selection_score")
        or _selection_score_from_metrics(result.get("test", {}))
        or _selection_score_from_metrics(result.get("val", {}))
    )


def _build_challenger_summary(
    *,
    val_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    walk_forward_metrics: dict[str, Any],
    calibration_method: str,
    selection_score: float,
) -> dict[str, Any]:
    return {
        "status": "completed",
        "model_name": "lstm_attention",
        "val": val_metrics,
        "test": test_metrics,
        "walk_forward": walk_forward_metrics,
        "calibration_method": calibration_method,
        "selection_score": selection_score,
    }


def _build_challenger_ranking(challengers: dict[str, dict[str, Any]], champion_name: str) -> list[dict[str, Any]]:
    sortable = sorted(
        challengers.items(),
        key=lambda item: _selection_score_from_result(item[1]),
        reverse=True,
    )
    ranking: list[dict[str, Any]] = []
    for idx, (model_name, result) in enumerate(sortable, start=1):
        status = result.get("status", "unknown")
        if model_name == champion_name and status == "completed":
            status = "selected_default_champion"
        ranking.append(
            {
                "rank": idx,
                "model_name": model_name,
                "selection_score": None if _selection_score_from_result(result) == float("-inf") else _selection_score_from_result(result),
                "status": status,
                "reason": result.get("reason"),
            }
        )
    return ranking



def _collect_outputs(model: LSTMAttentionModule, dataloader: DataLoader | None, device: torch.device) -> dict[str, np.ndarray]:
    if dataloader is None:
        return {
            "logits": np.empty((0, 2), dtype=np.float32),
            "labels": np.empty(0, dtype=np.int64),
            "raw_proba": np.empty(0, dtype=np.float64),
            "margins": np.empty(0, dtype=np.float64),
        }

    logits_parts: list[torch.Tensor] = []
    labels_parts: list[torch.Tensor] = []
    model.to(device)
    model.eval()
    with torch.no_grad():
        for x, y in dataloader:
            x = x.to(device)
            logits, _ = model(x)
            logits_parts.append(logits.detach().cpu())
            labels_parts.append(y.detach().cpu())

    if not logits_parts:
        return {
            "logits": np.empty((0, 2), dtype=np.float32),
            "labels": np.empty(0, dtype=np.int64),
            "raw_proba": np.empty(0, dtype=np.float64),
            "margins": np.empty(0, dtype=np.float64),
        }

    logits = torch.cat(logits_parts, dim=0)
    labels = torch.cat(labels_parts, dim=0)
    raw_proba = torch.softmax(logits, dim=1)[:, 1].numpy().astype(np.float64)
    margins = margin_from_logits(logits)
    return {
        "logits": logits.numpy(),
        "labels": labels.numpy().astype(np.int64),
        "raw_proba": raw_proba,
        "margins": margins,
    }



def _binary_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    n_pos = int((labels == 1).sum())
    n_neg = int((labels == 0).sum())
    if n_pos == 0 or n_neg == 0:
        return None

    order = np.argsort(scores)
    sorted_scores = scores[order]
    ranks = np.empty(len(scores), dtype=np.float64)
    i = 0
    while i < len(sorted_scores):
        j = i
        while j + 1 < len(sorted_scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        avg_rank = (i + j + 2) / 2.0
        ranks[order[i:j + 1]] = avg_rank
        i = j + 1

    sum_pos = ranks[labels == 1].sum()
    return float((sum_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))



def _expected_calibration_error(labels: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
    labels = np.asarray(labels, dtype=np.float64)
    proba = np.asarray(proba, dtype=np.float64)
    if len(labels) == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        left, right = edges[i], edges[i + 1]
        if i == n_bins - 1:
            mask = (proba >= left) & (proba <= right)
        else:
            mask = (proba >= left) & (proba < right)
        if not np.any(mask):
            continue
        confidence = float(proba[mask].mean())
        accuracy = float(labels[mask].mean())
        ece += (mask.mean()) * abs(accuracy - confidence)
    return float(ece)



def _compute_metrics(
    outputs: dict[str, np.ndarray],
    *,
    decision_threshold: float,
    calibrator: PlattCalibrator | None = None,
    future_returns: np.ndarray | None = None,
) -> dict[str, Any]:
    labels = outputs["labels"]
    logits = outputs["logits"]
    if len(labels) == 0:
        return {}

    raw_proba = outputs["raw_proba"]
    margins = outputs["margins"]
    proba = calibrator.predict_proba(margins) if calibrator is not None and calibrator.fitted else raw_proba
    threshold_metrics = compute_threshold_metrics(
        proba,
        labels,
        future_returns,
        decision_threshold=decision_threshold,
        n_buckets=5,
    )
    loss = float(torch.nn.functional.cross_entropy(
        torch.as_tensor(logits, dtype=torch.float32),
        torch.as_tensor(labels, dtype=torch.long),
    ).item())

    metrics: dict[str, Any] = {
        "loss": loss,
        "directional_accuracy": float(((proba >= decision_threshold).astype(np.int64) == labels).mean()),
        "precision": float(threshold_metrics["precision_long"]),
        "recall": float(threshold_metrics["recall_long"]),
        "auc": _binary_auc(labels, proba),
        "brier_score": float(np.mean((proba - labels) ** 2)),
        "ece": _expected_calibration_error(labels, proba),
        "action_rate": float(threshold_metrics["coverage_at_threshold"]),
        "base_rate": float(labels.mean()),
        "calibration_method": calibrator.method if calibrator is not None and calibrator.fitted else "none",
        "n_samples": int(len(labels)),
        **threshold_metrics,
    }
    return metrics



def _fit_calibrator(
    outputs: dict[str, np.ndarray],
    cfg: TrainingConfig,
) -> PlattCalibrator | None:
    if cfg.calibration.method != "platt":
        return None
    labels = outputs["labels"]
    margins = outputs["margins"]
    if len(labels) < cfg.calibration.min_samples:
        LOGGER.info("calibration skipped reason=too_few_samples samples=%d", len(labels))
        return None
    if len(np.unique(labels)) < 2:
        LOGGER.info("calibration skipped reason=single_class samples=%d", len(labels))
        return None
    calibrator = PlattCalibrator(max_iter=cfg.calibration.max_iter)
    return calibrator.fit(margins, labels)



def _evaluate_best_checkpoint(
    ckpt_path: Path,
    *,
    batch_size: int,
    val_ds: SequenceDataset | None,
    test_ds: SequenceDataset | None,
    val_frame: "pd.DataFrame | None",
    test_frame: "pd.DataFrame | None",
    cfg: TrainingConfig,
 ) -> tuple[dict[str, Any], dict[str, Any], PlattCalibrator | None, dict[str, Any], float]:
    model = LSTMAttentionModule.load_from_checkpoint(str(ckpt_path), map_location="cpu")
    device = torch.device("cpu")
    val_outputs = _collect_outputs(model, _build_loader(val_ds, batch_size, shuffle=False), device)
    calibrator = _fit_calibrator(val_outputs, cfg)
    selected_decision_threshold = float(cfg.data.decision_threshold)
    val_future_returns = val_frame["future_return"].to_numpy() if val_frame is not None and "future_return" in val_frame else None
    threshold_optimization_summary: dict[str, Any] = {
        "enabled": False,
        "selection_status": "disabled",
        "selected_threshold": selected_decision_threshold,
        "candidates": [],
    }
    if cfg.threshold_optimization.enabled and len(val_outputs["labels"]) > 0:
        calibrated_val_proba = (
            calibrator.predict_proba(val_outputs["margins"])
            if calibrator is not None and calibrator.fitted
            else val_outputs["raw_proba"]
        )
        threshold_optimization_summary = optimize_decision_threshold(
            calibrated_val_proba,
            val_outputs["labels"],
            val_future_returns,
            candidate_thresholds=cfg.threshold_optimization.candidate_decision_thresholds,
            default_threshold=cfg.data.decision_threshold,
            min_action_rate=cfg.threshold_optimization.min_action_rate,
            max_action_rate=cfg.threshold_optimization.max_action_rate,
            min_precision_long=cfg.threshold_optimization.min_precision_long,
            n_buckets=5,
        )
        selected_decision_threshold = float(threshold_optimization_summary.get("selected_threshold", selected_decision_threshold))
    val_metrics = _compute_metrics(
        val_outputs,
        decision_threshold=selected_decision_threshold,
        calibrator=calibrator,
        future_returns=val_future_returns,
    )

    test_metrics: dict[str, Any] = {}
    if test_ds is not None and len(test_ds) > 0:
        test_outputs = _collect_outputs(model, _build_loader(test_ds, batch_size, shuffle=False), device)
        test_metrics = _compute_metrics(
            test_outputs,
            decision_threshold=selected_decision_threshold,
            calibrator=calibrator,
            future_returns=test_frame["future_return"].to_numpy() if test_frame is not None and "future_return" in test_frame else None,
        )
    return val_metrics, test_metrics, calibrator, threshold_optimization_summary, selected_decision_threshold



def _aggregate_walk_forward_metrics(split_metrics: list[dict[str, Any]]) -> dict[str, Any]:
    if not split_metrics:
        return {}
    keys = [
        "loss",
        "directional_accuracy",
        "precision",
        "recall",
        "precision_long",
        "recall_long",
        "auc",
        "brier_score",
        "ece",
        "action_rate",
        "coverage_at_threshold",
        "base_rate",
        "avg_future_return_on_actions",
        "median_future_return_on_actions",
        "hit_rate_on_actions",
        "payoff_ratio",
        "top_bucket_hit_rate",
        "top_bucket_avg_future_return",
        "top_minus_bottom_bucket_hit_rate",
        "top_minus_bottom_bucket_return",
        "threshold_business_score",
        "decision_threshold",
    ]
    mean_metrics: dict[str, float | None] = {}
    std_metrics: dict[str, float | None] = {}
    for key in keys:
        vals = [float(m[key]) for m in split_metrics if m.get(key) is not None]
        mean_metrics[key] = float(np.mean(vals)) if vals else None
        std_metrics[key] = float(np.std(vals)) if vals else None
    return {
        "n_splits": len(split_metrics),
        "mean": mean_metrics,
        "std": std_metrics,
        "splits": split_metrics,
    }



def _run_walk_forward_validation(
    symbol: str,
    prepared_df: "pd.DataFrame",
    cfg: TrainingConfig,
) -> dict[str, Any]:
    import pandas as pd  # noqa: F401

    if not cfg.walk_forward.enabled:
        return {}

    splits = generate_walk_forward_splits(
        prepared_df,
        min_train_size=cfg.walk_forward.min_train_size,
        val_size=cfg.walk_forward.val_size,
        test_size=cfg.walk_forward.test_size,
        step_size=cfg.walk_forward.step_size,
        max_splits=cfg.walk_forward.max_splits,
    )
    if not splits:
        LOGGER.warning("walk_forward skipped symbol=%s reason=no_valid_split", symbol)
        return {}

    feature_cols = get_feature_columns(
        cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
    )
    fold_metrics: list[dict[str, Any]] = []

    for split in splits:
        scaler = FeatureScaler(feature_names=feature_cols)
        scaler.fit(split.train)
        train_ds = build_sequence_dataset(split.train, scaler, cfg.data.sequence_length)
        val_ds = build_sequence_dataset(split.val, scaler, cfg.data.sequence_length)
        test_ds = build_sequence_dataset(split.test, scaler, cfg.data.sequence_length)
        if train_ds is None or val_ds is None or test_ds is None:
            LOGGER.info(
                "walk_forward skipped split symbol=%s split=%d reason=insufficient_sequences",
                symbol,
                split.split_index,
            )
            continue

        with TemporaryDirectory(prefix=f"mf_wf_{symbol}_{split.split_index}_") as tmp_dir:
            ckpt_callback = ModelCheckpoint(
                dirpath=tmp_dir,
                filename="best",
                monitor="val_loss",
                mode="min",
                save_top_k=1,
            )
            early_stop = EarlyStopping(monitor="val_loss", patience=cfg.model.patience, mode="min")
            wf_model = LSTMAttentionModule(
                input_size=len(feature_cols),
                hidden_size=cfg.model.hidden_size,
                num_layers=cfg.model.num_layers,
                dropout=cfg.model.dropout,
                learning_rate=cfg.model.learning_rate,
                weight_decay=cfg.model.weight_decay,
                num_classes=cfg.model.num_classes,
            )
            trainer = L.Trainer(
                max_epochs=cfg.model.max_epochs,
                accelerator=cfg.accelerator,
                devices=1,
                callbacks=[ckpt_callback, early_stop],
                enable_progress_bar=False,
                logger=False,
                enable_model_summary=False,
            )
            trainer.fit(
                wf_model,
                train_dataloaders=_build_loader(train_ds, cfg.model.batch_size, shuffle=True),
                val_dataloaders=_build_loader(val_ds, cfg.model.batch_size, shuffle=False),
            )
            best_path = Path(ckpt_callback.best_model_path) if ckpt_callback.best_model_path else Path(tmp_dir) / "best.ckpt"
            if not best_path.exists():
                continue
            _, test_metrics, calibrator, threshold_summary, _ = _evaluate_best_checkpoint(
                best_path,
                batch_size=cfg.model.batch_size,
                val_ds=val_ds,
                test_ds=test_ds,
                val_frame=align_sequence_rows(split.val, cfg.data.sequence_length),
                test_frame=align_sequence_rows(split.test, cfg.data.sequence_length),
                cfg=cfg,
            )
            if test_metrics:
                fold_metrics.append({
                    "split_index": split.split_index,
                    "train_rows": len(split.train),
                    "val_rows": len(split.val),
                    "test_rows": len(split.test),
                    "calibration_method": calibrator.method if calibrator is not None and calibrator.fitted else "none",
                    "threshold_optimization": threshold_summary,
                    **test_metrics,
                })

    summary = _aggregate_walk_forward_metrics(fold_metrics)
    if summary:
        LOGGER.info(
            "walk_forward completed symbol=%s splits=%d mean_auc=%s",
            symbol,
            summary["n_splits"],
            summary["mean"].get("auc"),
        )
    return summary


# ---------------------------------------------------------------------------
# Trainer service
# ---------------------------------------------------------------------------


def train_symbol(
    symbol: str,
    bars_df: "pd.DataFrame",
    cfg: TrainingConfig,
    engine: Optional[Engine] = None,
    sentiment_df: "pd.DataFrame | None" = None,
    benchmark_df: "pd.DataFrame | None" = None,
    universe_df: "pd.DataFrame | None" = None,
) -> TrainResult:
    """Entraîne un modèle LSTM+Attention pour un symbole unique.

    Returns:
        TrainResult avec status completed|skipped|failed.
    """
    import pandas as pd  # noqa: F811 (lazy import pour picklability worker)

    torch.set_float32_matmul_precision("medium")

    run_id = f"{symbol}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    registry_id: int = 0

    if engine is not None:
        registry_id = ensure_registry_entry(engine, symbol)
        insert_training_run(engine, run_id, registry_id, symbol, status="running")

    try:
        if len(bars_df) < cfg.data.min_history_days:
            reason = f"history_too_short rows={len(bars_df)} min={cfg.data.min_history_days}"
            LOGGER.warning("train_symbol skipped symbol=%s reason=%s", symbol, reason)
            if engine:
                update_training_run(engine, run_id, status="skipped", skip_reason=reason, finished_at=datetime.now(timezone.utc))
            return TrainResult(symbol, run_id, "skipped", skip_reason=reason)

        effective_cfg = cfg
        target_optimization_summary: dict[str, Any] = {}
        if cfg.target_optimization.enabled:
            target_optimization_summary = optimize_target_parameters(
                bars_df,
                data_cfg=cfg.data,
                opt_cfg=cfg.target_optimization,
            )
            selected_horizon = int(target_optimization_summary.get("selected_horizon", cfg.data.forecast_horizon))
            selected_up_threshold = float(target_optimization_summary.get("selected_target_up_threshold", cfg.data.target_up_threshold))
            selected_down_threshold = float(target_optimization_summary.get("selected_target_down_threshold", cfg.data.target_down_threshold))
            if (
                selected_horizon != cfg.data.forecast_horizon
                or selected_up_threshold != cfg.data.target_up_threshold
                or selected_down_threshold != cfg.data.target_down_threshold
            ):
                effective_cfg = replace(
                    cfg,
                    data=replace(
                        cfg.data,
                        forecast_horizon=selected_horizon,
                        target_up_threshold=selected_up_threshold,
                        target_down_threshold=selected_down_threshold,
                    ),
                )
                LOGGER.info(
                    "target optimization selected params symbol=%s horizon=%d->%d up=%.4f->%.4f down=%.4f->%.4f score=%.6f",
                    symbol,
                    cfg.data.forecast_horizon,
                    selected_horizon,
                    cfg.data.target_up_threshold,
                    selected_up_threshold,
                    cfg.data.target_down_threshold,
                    selected_down_threshold,
                    float(target_optimization_summary.get("selected_score", 0.0)),
                )

        datamodule_kwargs: dict[str, Any] = {"sentiment_df": sentiment_df}
        if benchmark_df is not None:
            datamodule_kwargs["benchmark_df"] = benchmark_df
        if universe_df is not None:
            datamodule_kwargs["universe_df"] = universe_df
        dm = SymbolDataModule(
            bars_df,
            effective_cfg.data,
            effective_cfg.model,
            **datamodule_kwargs,
        )
        dm.setup()

        if dm.train_ds is None or dm.val_ds is None or len(dm.train_ds) == 0 or len(dm.val_ds) == 0:
            reason = "insufficient_sequences_after_split"
            LOGGER.warning("train_symbol skipped symbol=%s reason=%s", symbol, reason)
            if engine:
                update_training_run(engine, run_id, status="skipped", skip_reason=reason, finished_at=datetime.now(timezone.utc))
            return TrainResult(symbol, run_id, "skipped", skip_reason=reason)

        walk_forward_metrics: dict[str, Any] = {}
        prepared_df = getattr(dm, "prepared_df", None)
        if prepared_df is not None:
            walk_forward_metrics = _run_walk_forward_validation(symbol, prepared_df, effective_cfg)

        sym_dir = (Path(cfg.artifacts_dir) / symbol).resolve()
        sym_dir.mkdir(parents=True, exist_ok=True)

        model = LSTMAttentionModule(
            input_size=dm.n_features,
            hidden_size=effective_cfg.model.hidden_size,
            num_layers=effective_cfg.model.num_layers,
            dropout=effective_cfg.model.dropout,
            learning_rate=effective_cfg.model.learning_rate,
            weight_decay=effective_cfg.model.weight_decay,
            num_classes=effective_cfg.model.num_classes,
        )

        ckpt_callback = ModelCheckpoint(
            dirpath=str(sym_dir),
            filename="best",
            monitor="val_loss",
            mode="min",
            save_top_k=1,
        )
        early_stop = EarlyStopping(monitor="val_loss", patience=effective_cfg.model.patience, mode="min")

        trainer = L.Trainer(
            max_epochs=effective_cfg.model.max_epochs,
            accelerator=effective_cfg.accelerator,
            devices=1,
            callbacks=[ckpt_callback, early_stop],
            enable_progress_bar=False,
            logger=False,
            enable_model_summary=False,
        )

        root_device = str(trainer.strategy.root_device)
        device_name = torch.cuda.get_device_name(0) if root_device.startswith("cuda") and torch.cuda.is_available() else root_device
        LOGGER.info(
            "trainer initialized symbol=%s requested_accelerator=%s resolved_device=%s device_name=%s batch_size=%d train_workers=%d",
            symbol,
            effective_cfg.accelerator,
            root_device,
            device_name,
            effective_cfg.model.batch_size,
            dm.train_dataloader().num_workers,
        )

        trainer.fit(model, datamodule=dm)

        best_source = Path(ckpt_callback.best_model_path) if ckpt_callback.best_model_path else sym_dir / "best.ckpt"
        split = dm.split
        val_frame = align_sequence_rows(split.val, effective_cfg.data.sequence_length) if split is not None else None
        test_frame = align_sequence_rows(split.test, effective_cfg.data.sequence_length) if split is not None else None
        val_metrics, test_metrics, calibrator, threshold_optimization_summary, selected_decision_threshold = _evaluate_best_checkpoint(
            best_source,
            batch_size=effective_cfg.model.batch_size,
            val_ds=dm.val_ds,
            test_ds=dm.test_ds,
            val_frame=val_frame,
            test_frame=test_frame,
            cfg=effective_cfg,
        )
        if selected_decision_threshold != effective_cfg.data.decision_threshold:
            effective_cfg = replace(
                effective_cfg,
                data=replace(effective_cfg.data, decision_threshold=selected_decision_threshold),
            )

        baseline_metrics: dict[str, Any] = {}
        if prepared_df is not None and effective_cfg.baseline.enabled:
            baseline_metrics = run_lightgbm_baseline(prepared_df, effective_cfg)
        catboost_metrics: dict[str, Any] = {}
        if prepared_df is not None and effective_cfg.baseline.enable_catboost:
            catboost_metrics = run_catboost_baseline(prepared_df, effective_cfg)

        best_ckpt = sym_dir / "best.ckpt"
        if best_source.exists() and best_source.resolve() != best_ckpt.resolve():
            best_ckpt.unlink(missing_ok=True)
            best_source.replace(best_ckpt)
        elif best_source.exists() and not best_ckpt.exists():
            best_ckpt = best_source.resolve()

        scaler_path = sym_dir / "scaler.pkl"
        with open(scaler_path, "wb") as f:
            pickle.dump(dm.scaler.state_dict(), f)

        calibrator_path: str | None = None
        if calibrator is not None and calibrator.fitted:
            cal_path = sym_dir / "calibrator.pkl"
            with open(cal_path, "wb") as f:
                pickle.dump(calibrator.state_dict(), f)
            calibrator_path = str(cal_path)

        config_path = sym_dir / "config.json"
        calibration_method = calibrator.method if calibrator is not None and calibrator.fitted else "none"
        lstm_selection_score = _selection_score_from_metrics(test_metrics or val_metrics)
        challengers = {
            "lstm_attention": _build_challenger_summary(
                val_metrics=val_metrics,
                test_metrics=test_metrics,
                walk_forward_metrics=walk_forward_metrics,
                calibration_method=calibration_method,
                selection_score=lstm_selection_score,
            ),
            "lightgbm": baseline_metrics,
            "catboost": catboost_metrics,
        }
        selected_architecture = "lstm_attention"
        challenger_ranking = _build_challenger_ranking(challengers, selected_architecture)
        cross_sectional_feature_columns = list(getattr(dm, "cross_sectional_feature_columns", []))
        cross_sectional_diagnostics = dict(getattr(dm, "cross_sectional_diagnostics", {}))
        config_data = {
            "data": asdict(effective_cfg.data),
            "model": {**asdict(effective_cfg.model), "input_size": dm.n_features},
            "calibration": asdict(effective_cfg.calibration),
            "walk_forward": asdict(effective_cfg.walk_forward),
            "baseline": asdict(effective_cfg.baseline),
            "target_optimization": asdict(effective_cfg.target_optimization),
            "threshold_optimization": asdict(effective_cfg.threshold_optimization),
            "symbol": symbol,
            "run_id": run_id,
            "feature_columns": dm.scaler.feature_names,
            "cross_sectional_feature_columns": cross_sectional_feature_columns,
            "cross_sectional_diagnostics": cross_sectional_diagnostics,
            "calibrator_path": calibrator_path,
            "selected_forecast_horizon": effective_cfg.data.forecast_horizon,
            "selected_target_up_threshold": effective_cfg.data.target_up_threshold,
            "selected_target_down_threshold": effective_cfg.data.target_down_threshold,
            "selected_decision_threshold": effective_cfg.data.decision_threshold,
            "architecture_selected": selected_architecture,
            "selection_mode": "default_lstm_champion",
            "artifact_routes": {
                "selected_model": selected_architecture,
                "models": {
                    "lstm_attention": {
                        "checkpoint_path": str(sym_dir / "best.ckpt"),
                        "scaler_path": str(sym_dir / "scaler.pkl"),
                        "config_path": str(config_path),
                        "calibrator_path": calibrator_path,
                        "inference_backend": "lstm_attention",
                    },
                    "lightgbm": {
                        "status": baseline_metrics.get("status", "disabled") if baseline_metrics else "disabled",
                        "inference_backend": "not_yet_supported",
                    },
                    "catboost": {
                        "status": catboost_metrics.get("status", "disabled") if catboost_metrics else "disabled",
                        "inference_backend": "not_yet_supported",
                    },
                },
            },
        }
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2, default=str)

        all_metrics = {
            "val": val_metrics,
            "test": test_metrics,
            "walk_forward": walk_forward_metrics,
            "baseline_lightgbm": baseline_metrics,
            "baseline_catboost": catboost_metrics,
            "target_optimization": target_optimization_summary,
            "threshold_optimization": threshold_optimization_summary,
            "optimization": {
                "target_search": target_optimization_summary,
                "decision_threshold_search": threshold_optimization_summary,
            },
            "diagnostics": {
                "feature_columns": dm.scaler.feature_names,
                "cross_sectional_feature_columns": cross_sectional_feature_columns,
                "cross_sectional_diagnostics": cross_sectional_diagnostics,
            },
            "champion": {
                "model_name": selected_architecture,
                "selection_mode": "default_lstm_champion",
                "selection_score": lstm_selection_score,
            },
            "challengers": {
                "ranking": challenger_ranking,
                **challengers,
            },
        }
        with open(sym_dir / "metrics.json", "w") as f:
            json.dump(all_metrics, f, indent=2)

        if engine is not None:
            best_epoch = _extract_best_epoch(best_ckpt) if best_ckpt.exists() else None
            update_training_run(
                engine, run_id,
                status="completed",
                finished_at=datetime.now(timezone.utc),
                epochs_run=trainer.current_epoch,
                best_epoch=best_epoch or 0,
                checkpoint_path=str(best_ckpt),
                scaler_path=str(scaler_path),
                config_path=str(config_path),
            )
            insert_metrics(engine, run_id, symbol, "val", val_metrics)
            if test_metrics:
                insert_metrics(engine, run_id, symbol, "test", test_metrics)
            wf_mean = walk_forward_metrics.get("mean") if walk_forward_metrics else None
            if wf_mean:
                insert_metrics(engine, run_id, symbol, "wf", wf_mean)

        LOGGER.info(
            "train_symbol completed symbol=%s run_id=%s val_loss=%.4f calibration=%s decision_threshold=%.2f",
            symbol,
            run_id,
            float(val_metrics.get("loss", -1.0) or -1.0),
            calibrator.method if calibrator is not None and calibrator.fitted else "none",
            effective_cfg.data.decision_threshold,
        )
        return TrainResult(symbol, run_id, "completed", metrics=all_metrics)

    except Exception as exc:
        LOGGER.exception("train_symbol failed symbol=%s run_id=%s", symbol, run_id)
        if engine is not None:
            update_training_run(engine, run_id, status="failed", skip_reason=str(exc)[:200], finished_at=datetime.now(timezone.utc))
        return TrainResult(symbol, run_id, "failed", skip_reason=str(exc))








