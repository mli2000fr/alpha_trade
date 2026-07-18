"""modelFactory/trainer.py — Service d'entraînement mono-symbole."""
from __future__ import annotations

import json
import logging
import pickle
import inspect
import uuid
from dataclasses import asdict, replace
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory
from typing import Any, Optional

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

try:
    import lightning as L
    from lightning.pytorch.callbacks import Callback, EarlyStopping, ModelCheckpoint
except ImportError:  # pragma: no cover
    import pytorch_lightning as L  # type: ignore[no-redef]
    from pytorch_lightning.callbacks import Callback, EarlyStopping, ModelCheckpoint  # type: ignore[no-redef]

from sqlalchemy.engine import Engine

from core.ternary_decision_policy import TernaryDecisionPolicy, decide_ternary_side_batch


def _build_ternary_policy(cfg: TrainingConfig) -> TernaryDecisionPolicy:
    """Construit une TernaryDecisionPolicy à partir de la config d'entraînement."""
    return TernaryDecisionPolicy(
        threshold_short=float(cfg.model.ternary_threshold_short),
        threshold_long=float(cfg.model.ternary_threshold_long),
        top2_margin=float(cfg.model.ternary_top2_margin),
    )
from modelFactory.calibration import PlattCalibrator, TemperatureScaler, margin_from_logits
from modelFactory.champion_selection import (
    build_challenger_ranking,
    persist_artifact_signature_manifest,
    select_champion,
)
from modelFactory.config import ReproducibilityConfig, TrainingConfig
from modelFactory.dataset import (
    FeatureScaler,
    SequenceDataset,
    SymbolDataModule,
    build_sequence_dataset,
    chrono_split,
    generate_walk_forward_splits,
    prepare_symbol_frame,
)
from modelFactory.db_registry import (
    ensure_registry_entry,
    insert_metrics,
    insert_training_run,
    replace_model_governance,
    update_training_run,
    upsert_directional_oos_metrics,
    upsert_metrics_full,
)
from modelFactory.evaluation import (
    align_sequence_rows,
    compute_directional_oos_metrics,
    compute_threshold_metrics,
    optimize_decision_threshold,
)
from modelFactory.features import build_feature_contract, get_feature_columns
from modelFactory.features import fingerprint as compute_feature_fingerprint
from modelFactory.catboost_baseline import run_catboost_baseline
from modelFactory.lightgbm_baseline import run_lightgbm_baseline
from modelFactory.model import LSTMAttentionModule
from modelFactory.reproducibility import apply_reproducibility, build_torch_generator, derive_seed
from modelFactory.runtime_status import update_runtime_status
from modelFactory.target_optimization import optimize_target_parameters

LOGGER = logging.getLogger(__name__)


def _atomic_write_json(path: Path, data: Any, *, indent: int = 2) -> None:
    """Écrit un fichier JSON de façon atomique (tempfile + rename).

    Garantit qu'un crash mid-write ne laisse jamais un fichier partiellement
    écrit : on écrit dans un fichier temporaire du même dossier, puis on le
    renomme. Sur Windows, ``Path.replace()`` est atomique au niveau du
    système de fichiers.
    """
    tmp_path: Path | None = None
    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.tmp.",
            suffix=".json",
            delete=False,
        ) as fh:
            tmp_path = Path(fh.name)
            json.dump(data, fh, indent=indent, default=str)
            fh.flush()
        tmp_path.replace(path)
    except Exception:
        if tmp_path is not None and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _metric_to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if isinstance(value, torch.Tensor):
            if value.numel() != 1:
                return None
            return float(value.detach().cpu().item())
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_metric(value: Any) -> str:
    numeric = _metric_to_float(value)
    return f"{numeric:.4f}" if numeric is not None else "n/a"


class _EpochProgressLogger(Callback):
    """Callback Lightning minimaliste pour produire des heartbeats lisibles en log."""

    def __init__(
        self,
        *,
        symbol: str,
        phase: str,
        debug_enabled: bool = False,
        split_index: int | None = None,
    ) -> None:
        super().__init__()
        self.symbol = symbol
        self.phase = phase
        self.debug_enabled = debug_enabled
        self.split_index = split_index

    def on_validation_epoch_end(self, trainer: "L.Trainer", pl_module: L.LightningModule) -> None:  # type: ignore[override]
        if trainer.sanity_checking:
            return
        metrics = trainer.callback_metrics
        parts = [f"training_progress phase={self.phase}", f"symbol={self.symbol}"]
        if self.split_index is not None:
            parts.append(f"split={self.split_index}")
        epoch_text = f"epoch={trainer.current_epoch + 1}/{trainer.max_epochs}"
        metric_parts = [
            f"train_loss={_format_metric(metrics.get('train_loss'))}",
            f"val_loss={_format_metric(metrics.get('val_loss'))}",
            f"val_acc={_format_metric(metrics.get('val_acc'))}",
            f"val_auc={_format_metric(metrics.get('val_auc'))}",
        ]
        if self.debug_enabled:
            metric_parts.extend(
                [
                    f"train_acc={_format_metric(metrics.get('train_acc'))}",
                    f"val_precision={_format_metric(metrics.get('val_precision'))}",
                    f"val_recall={_format_metric(metrics.get('val_recall'))}",
                ]
            )
        parts.extend([epoch_text, *metric_parts])
        update_runtime_status(
            current_phase=self.phase,
            current_symbol=self.symbol,
            progress_item=self.symbol,
            phase_detail=" ".join([epoch_text, *metric_parts]),
            current_epoch=trainer.current_epoch + 1,
            total_epochs=trainer.max_epochs,
            current_split_index=self.split_index,
        )
        LOGGER.info(" ".join(parts))


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



def _build_loader(dataset: SequenceDataset | None, batch_size: int, *, shuffle: bool, seed: int) -> DataLoader | None:
    if dataset is None:
        return None
    worker_init_fn = None
    if torch.cuda.is_available():
        worker_init_fn = None
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        drop_last=False,
        num_workers=0,
        persistent_workers=False,
        pin_memory=False,
        generator=build_torch_generator(seed),
        worker_init_fn=worker_init_fn,
    )


def _selection_score_from_metrics(metrics: dict[str, Any]) -> float:
    # Ternary : utiliser f1_macro comme score principal
    if metrics.get("num_classes") == 3:
        return float(
            metrics.get("f1_macro")
            or metrics.get("accuracy")
            or 0.0
        )
    return float(
        metrics.get("threshold_business_score")
        or metrics.get("auc")
        or metrics.get("directional_accuracy")
        or 0.0
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


def _skip_train_symbol(
    *,
    symbol: str,
    run_id: str,
    reason: str,
    engine: Optional[Engine],
) -> TrainResult:
    LOGGER.warning("train_symbol skipped symbol=%s reason=%s", symbol, reason)
    if engine is not None:
        try:
            update_training_run(engine, run_id, status="skipped", skip_reason=reason, finished_at=datetime.now(timezone.utc))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("train_symbol registry_write_failed symbol=%s run_id=%s operation=update_training_run error=%s", symbol, run_id, exc)
    return TrainResult(symbol, run_id, "skipped", skip_reason=reason)


def _record_training_db_issue(symbol: str, run_id: str, *, operation: str, exc: Exception) -> None:
    LOGGER.warning(
        "train_symbol registry_write_failed symbol=%s run_id=%s operation=%s error=%s",
        symbol,
        run_id,
        operation,
        exc,
    )
    update_runtime_status(
        last_db_issue_operation=operation,
        last_db_issue_reason=f"training_db_issue:{type(exc).__name__}",
        last_prediction_symbol=symbol,
    )


def _run_training_registry_writes(
    engine: Engine,
    *,
    run_id: str,
    symbol: str,
    trainer: Any,
    best_ckpt: Path,
    scaler_path: Path,
    config_path: Path,
    val_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    walk_forward_metrics: dict[str, Any],
    all_metrics: dict[str, Any],
    challengers: dict[str, Any],
    artifact_routes_models: dict[str, Any],
    selected_architecture: str,
    selection_mode: str,
    selection_metric: str,
    challenger_ranking: list[dict[str, Any]],
) -> None:
    best_epoch = _extract_best_epoch(best_ckpt) if best_ckpt.exists() else None
    completed_at = datetime.now(timezone.utc)
    update_training_run(
        engine, run_id,
        status="completed",
        finished_at=completed_at,
        epochs_run=trainer.current_epoch,
        best_epoch=best_epoch or 0,
        checkpoint_path=str(best_ckpt),
        scaler_path=str(scaler_path),
        config_path=str(config_path),
    )
    # ── LSTM metrics ──
    insert_metrics(engine, run_id, symbol, "val", val_metrics, model_name="lstm_attention")
    if test_metrics:
        insert_metrics(engine, run_id, symbol, "test", test_metrics, model_name="lstm_attention")
    wf_mean = walk_forward_metrics.get("mean") if walk_forward_metrics else None
    if wf_mean:
        insert_metrics(engine, run_id, symbol, "wf", wf_mean, model_name="lstm_attention")

    directional_metrics_by_split = {
        split_name: metrics["directional_oos_metrics"]
        for split_name, metrics in (("val", val_metrics), ("test", test_metrics))
        if isinstance(metrics.get("directional_oos_metrics"), dict)
    }
    if directional_metrics_by_split:
        upsert_directional_oos_metrics(
            engine,
            run_id=run_id,
            symbol=symbol,
            as_of_date=completed_at.date(),
            metrics_by_split=directional_metrics_by_split,
        )

    # ── LightGBM challenger metrics ──
    lgbm_metrics = challengers.get("lightgbm") if isinstance(challengers, dict) else None
    if isinstance(lgbm_metrics, dict) and lgbm_metrics.get("status") == "completed":
        lgbm_val = lgbm_metrics.get("val")
        if isinstance(lgbm_val, dict):
            insert_metrics(engine, run_id, symbol, "val", lgbm_val, model_name="lightgbm")
        lgbm_test = lgbm_metrics.get("test")
        if isinstance(lgbm_test, dict):
            insert_metrics(engine, run_id, symbol, "test", lgbm_test, model_name="lightgbm")
        lgbm_wf = lgbm_metrics.get("wf")
        if isinstance(lgbm_wf, dict):
            insert_metrics(engine, run_id, symbol, "wf", lgbm_wf, model_name="lightgbm")

    # ── CatBoost challenger metrics ──
    cb_metrics = challengers.get("catboost") if isinstance(challengers, dict) else None
    if isinstance(cb_metrics, dict) and cb_metrics.get("status") == "completed":
        cb_val = cb_metrics.get("val")
        if isinstance(cb_val, dict):
            insert_metrics(engine, run_id, symbol, "val", cb_val, model_name="catboost")
        cb_test = cb_metrics.get("test")
        if isinstance(cb_test, dict):
            insert_metrics(engine, run_id, symbol, "test", cb_test, model_name="catboost")
        cb_wf = cb_metrics.get("wf")
        if isinstance(cb_wf, dict):
            insert_metrics(engine, run_id, symbol, "wf", cb_wf, model_name="catboost")

    upsert_metrics_full(engine, run_id=run_id, symbol=symbol, metrics=all_metrics)
    replace_model_governance(
        engine,
        run_id=run_id,
        symbol=symbol,
        challengers=challengers,
        artifact_routes_models=artifact_routes_models,
        selected_model=selected_architecture,
        selection_mode=selection_mode,
        selection_metric=selection_metric,
        ranking=challenger_ranking,
    )


def _build_feature_contract_for_columns(cfg: TrainingConfig, feature_columns: list[str]) -> dict[str, Any] | None:
    if not feature_columns:
        return None
    return build_feature_contract(
        include_sentiment=cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_selector_context=cfg.data.include_selector_context_features,
        include_short_score=cfg.data.include_short_score_features,
        feature_columns=feature_columns,
        scaler_feature_names=feature_columns,
    )


def _build_tabular_artifact_route(
    *,
    metrics: dict[str, Any] | None,
    config_path: Path,
    feature_contract: dict[str, Any] | None,
    default_backend: str,
) -> dict[str, Any]:
    artifact_paths = (metrics or {}).get("artifact_paths") or {}
    return {
        "status": (metrics or {}).get("status", "disabled"),
        "model_path": artifact_paths.get("model_path"),
        "calibrator_path": artifact_paths.get("calibrator_path"),
        "config_path": str(config_path),
        "feature_columns": list((metrics or {}).get("feature_columns") or []) or None,
        "feature_fingerprint": (
            (metrics or {}).get("feature_fingerprint")
            or (feature_contract or {}).get("feature_fingerprint")
        ),
        "feature_contract": feature_contract,
        "selected_decision_threshold": (metrics or {}).get("selected_decision_threshold"),
        "inference_backend": (metrics or {}).get("inference_backend", default_backend),
    }


def _prepare_target_optimization_summary(
    *,
    bars_df: "pd.DataFrame",
    cfg: TrainingConfig,
    sentiment_df: "pd.DataFrame | None" = None,
    benchmark_df: "pd.DataFrame | None" = None,
    universe_df: "pd.DataFrame | None" = None,
    selector_df: "pd.DataFrame | None" = None,
) -> dict[str, Any]:
    prepared_df = prepare_symbol_frame(
        bars_df,
        cfg.data,
        sentiment_df=sentiment_df,
        benchmark_df=benchmark_df,
        universe_df=universe_df,
        selector_df=selector_df,
    )
    label_horizon = (
        cfg.data.triple_barrier_max_sessions
        if cfg.data.label_method == "triple_barrier"
        else cfg.data.forecast_horizon
    )
    split = chrono_split(
        prepared_df,
        cfg.data.train_ratio,
        cfg.data.val_ratio,
        forecast_horizon=label_horizon,
    )
    train_df = split.train.reset_index(drop=True)
    summary: dict[str, Any] = {
        "fit_scope": "train_split_only",
        "fit_rows": int(len(train_df)),
        "prepared_rows": int(len(prepared_df)),
        "val_rows": int(len(split.val)),
        "test_rows": int(len(split.test)),
    }
    if train_df.empty:
        summary["skipped_reason"] = "insufficient_train_rows_for_target_optimization"
        return summary
    optimized = optimize_target_parameters(
        train_df,
        data_cfg=cfg.data,
        opt_cfg=cfg.target_optimization,
    )
    summary.update(optimized)
    return summary


def _collect_outputs(model: LSTMAttentionModule, dataloader: DataLoader | None, device: torch.device) -> dict[str, np.ndarray]:
    if dataloader is None:
        return {
            "logits": np.empty((0, 2), dtype=np.float32),
            "labels": np.empty(0, dtype=np.int64),
            "raw_proba": np.empty(0, dtype=np.float64),
            "margins": np.empty(0, dtype=np.float64),
            "num_classes": 2,
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
    probs = torch.softmax(logits, dim=1)
    num_classes = logits.shape[1]
    if num_classes == 3:
        # Ternary : on garde toutes les probas + prédictions
        raw_proba = probs.numpy().astype(np.float64)  # [N, 3]
        margins = np.zeros((len(logits),), dtype=np.float64)  # pas de marge binaire
    else:
        raw_proba = probs[:, 1].numpy().astype(np.float64)  # [N]
        margins = margin_from_logits(logits)
    return {
        "logits": logits.numpy(),
        "labels": labels.numpy().astype(np.int64),
        "raw_proba": raw_proba,
        "margins": margins,
        "num_classes": num_classes,
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
    calibrator: PlattCalibrator | TemperatureScaler | None = None,
    future_returns: np.ndarray | None = None,
    ternary_policy: "TernaryDecisionPolicy | None" = None,
) -> dict[str, Any]:
    labels = outputs["labels"]
    logits = outputs["logits"]
    num_classes = int(outputs.get("num_classes", 2))
    if len(labels) == 0:
        return {}

    if num_classes == 3:
        # ── Ternary metrics ──────────────────────────────────────
        probs = (
            calibrator.predict_proba(logits)
            if isinstance(calibrator, TemperatureScaler) and calibrator.fitted
            else outputs["raw_proba"]
        )
        _pol = ternary_policy if ternary_policy is not None else TernaryDecisionPolicy()
        preds = decide_ternary_side_batch(probs, policy=_pol)  # {0=short, 1=flat, 2=long}
        # Décale labels {-1, 0, 1} → {0, 1, 2}
        labels_shifted = labels + 1
        accuracy = float((preds == labels_shifted).mean())
        loss = float(torch.nn.functional.cross_entropy(
            torch.as_tensor(logits, dtype=torch.float32),
            torch.as_tensor(labels_shifted, dtype=torch.long),
        ).item())

        # F1 par classe
        f1_per_class = {}
        for cls_idx, cls_name in enumerate(["short", "flat", "long"]):
            tp = int(((preds == cls_idx) & (labels_shifted == cls_idx)).sum())
            fp = int(((preds == cls_idx) & (labels_shifted != cls_idx)).sum())
            fn = int(((preds != cls_idx) & (labels_shifted == cls_idx)).sum())
            prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            f1_per_class[f"f1_{cls_name}"] = float(2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0)

        # Distribution des prédictions
        pred_dist = {
            "pred_short_pct": float((preds == 0).mean() * 100),
            "pred_flat_pct": float((preds == 1).mean() * 100),
            "pred_long_pct": float((preds == 2).mean() * 100),
        }
        label_dist = {
            "true_short_pct": float((labels_shifted == 0).mean() * 100),
            "true_flat_pct": float((labels_shifted == 1).mean() * 100),
            "true_long_pct": float((labels_shifted == 2).mean() * 100),
        }
        # Probas moyennes brutes (avant calibration) et calibrées
        raw = outputs.get("raw_proba")
        avg_prob_dist: dict[str, float | None] = {
            "avg_prob_short": None, "avg_prob_flat": None, "avg_prob_long": None,
            "avg_calib_prob_short": None, "avg_calib_prob_flat": None, "avg_calib_prob_long": None,
        }
        if raw is not None and len(raw) > 0:
            avg_prob_dist["avg_prob_short"] = float(np.mean(raw[:, 0]))
            avg_prob_dist["avg_prob_flat"] = float(np.mean(raw[:, 1]))
            avg_prob_dist["avg_prob_long"] = float(np.mean(raw[:, 2]))
        if probs is not None and len(probs) > 0:
            avg_prob_dist["avg_calib_prob_short"] = float(np.mean(probs[:, 0]))
            avg_prob_dist["avg_calib_prob_flat"] = float(np.mean(probs[:, 1]))
            avg_prob_dist["avg_calib_prob_long"] = float(np.mean(probs[:, 2]))

        # F1 macro (moyenne des 3 classes)
        f1_values = [v for k, v in f1_per_class.items() if v is not None]
        f1_macro = float(np.mean(f1_values)) if f1_values else 0.0

        # ── Binarised precision / recall / AUC for "long" class (P2 2026-06-30)
        # En ternaire, precision/recall/auc sont definis en one-vs-rest :
        #   classe positive = long (idx 2), classe negative = short+flat (idx 0,1)
        tp_long = int(((preds == 2) & (labels_shifted == 2)).sum())
        fp_long = int(((preds == 2) & (labels_shifted != 2)).sum())
        fn_long = int(((preds != 2) & (labels_shifted == 2)).sum())
        bin_precision = float(tp_long / (tp_long + fp_long)) if (tp_long + fp_long) > 0 else 0.0
        bin_recall = float(tp_long / (tp_long + fn_long)) if (tp_long + fn_long) > 0 else 0.0
        # AUC binarisee : proba colonne 2 (long) vs label 1=long, 0=reste
        bin_labels_long = (labels_shifted == 2).astype(np.int64)
        bin_proba_long = probs[:, 2].astype(np.float64)
        bin_auc = _binary_auc(bin_labels_long, bin_proba_long)
        # Directional accuracy binarisee (compatible colonne DB existante)
        bin_preds = (preds == 2).astype(np.int64)
        bin_acc = float((bin_preds == bin_labels_long).mean())

        metrics = {
            "loss": loss,
            "accuracy": accuracy,
            "directional_accuracy": bin_acc,
            "precision": bin_precision,
            "recall": bin_recall,
            "auc": bin_auc,
            "n_samples": int(len(labels)),
            "num_classes": 3,
            "f1_macro": f1_macro,
            **f1_per_class,
            **pred_dist,
            **label_dist,
            **avg_prob_dist,
        }
        if future_returns is not None:
            metrics["directional_oos_metrics"] = compute_directional_oos_metrics(
                probs,
                future_returns,
            )
        return metrics

    # ── Binary metrics (comportement existant) ──────────────────
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
) -> PlattCalibrator | TemperatureScaler | None:
    from modelFactory.calibration import PlattCalibrator, TemperatureScaler

    if cfg.calibration.method != "platt":
        return None
    labels = outputs["labels"]
    if len(labels) < cfg.calibration.min_samples:
        LOGGER.info("calibration skipped reason=too_few_samples samples=%d", len(labels))
        return None
    if len(np.unique(labels)) < 2:
        LOGGER.info("calibration skipped reason=single_class samples=%d", len(labels))
        return None

    num_classes = int(outputs.get("num_classes", 2))
    if num_classes != 2:
        # ── Temperature Scaling pour mode ternaire (2026-06-25) ──
        LOGGER.info(
            "calibration mode=temperature_scaling classes=%d samples=%d",
            num_classes, len(labels),
        )
        logits = outputs["logits"]
        # Les labels sont {-1, 0, 1} → shifter vers {0, 1, 2}
        labels_shifted = labels + 1
        scaler = TemperatureScaler(max_iter=cfg.calibration.max_iter)
        return scaler.fit(logits, labels_shifted)

    margins = outputs["margins"]
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
    ternary_policy: "TernaryDecisionPolicy | None" = None,
 ) -> tuple[dict[str, Any], dict[str, Any], PlattCalibrator | TemperatureScaler | None, dict[str, Any], float]:
    model = LSTMAttentionModule.load_from_checkpoint(str(ckpt_path), map_location="cpu")
    device = torch.device("cpu")
    val_outputs = _collect_outputs(
        model,
        _build_loader(
            val_ds,
            batch_size,
            shuffle=False,
            seed=derive_seed(cfg.reproducibility.seed, "evaluate_best_checkpoint", "val"),
        ),
        device,
    )
    calibrator = _fit_calibrator(val_outputs, cfg)
    selected_decision_threshold = float(cfg.data.decision_threshold)
    val_future_returns = val_frame["future_return"].to_numpy() if val_frame is not None and "future_return" in val_frame else None
    threshold_optimization_summary: dict[str, Any] = {
        "enabled": False,
        "selection_status": "disabled",
        "selected_threshold": selected_decision_threshold,
        "candidates": [],
    }
    num_classes = int(val_outputs.get("num_classes", 2))
    if cfg.threshold_optimization.enabled and len(val_outputs["labels"]) > 0 and num_classes == 2:
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
        ternary_policy=ternary_policy,
    )

    test_metrics: dict[str, Any] = {}
    if test_ds is not None and len(test_ds) > 0:
        test_outputs = _collect_outputs(
            model,
            _build_loader(
                test_ds,
                batch_size,
                shuffle=False,
                seed=derive_seed(cfg.reproducibility.seed, "evaluate_best_checkpoint", "test"),
            ),
            device,
        )
        test_metrics = _compute_metrics(
            test_outputs,
            decision_threshold=selected_decision_threshold,
            calibrator=calibrator,
            future_returns=test_frame["future_return"].to_numpy() if test_frame is not None and "future_return" in test_frame else None,
            ternary_policy=ternary_policy,
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
        # P2 (2026-07-01) — F1 ternaire pour le walk-forward
        "f1_macro",
        "f1_short",
        "f1_flat",
        "f1_long",
        # Distribution true / pred (ternaire)
        "true_short_pct",
        "true_flat_pct",
        "true_long_pct",
        "pred_short_pct",
        "pred_flat_pct",
        "pred_long_pct",
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
        forecast_horizon=cfg.data.forecast_horizon,
    )
    if not splits:
        LOGGER.warning("walk_forward skipped symbol=%s reason=no_valid_split", symbol)
        update_runtime_status(current_phase="walk_forward_skipped", current_symbol=symbol, progress_item=symbol)
        return {}

    update_runtime_status(
        current_phase="walk_forward_start",
        current_symbol=symbol,
        progress_item=symbol,
        walk_forward_splits=len(splits),
        current_split_index=0,
    )
    LOGGER.info(
        "walk_forward start symbol=%s splits=%d prepared_rows=%d max_epochs=%d accelerator=%s",
        symbol,
        len(splits),
        len(prepared_df),
        cfg.model.max_epochs,
        cfg.accelerator,
    )

    feature_cols = get_feature_columns(
        cfg.data.include_sentiment_features,
        feature_set=cfg.data.feature_set,
        include_cross_sectional=cfg.data.enable_cross_sectional_features,
        include_selector_context=cfg.data.include_selector_context_features,
        include_short_score=cfg.data.include_short_score_features,
    )
    fold_metrics: list[dict[str, Any]] = []
    walk_forward_seed = derive_seed(cfg.reproducibility.seed, "walk_forward", symbol)

    for split in splits:
        split_seed = derive_seed(walk_forward_seed, split.split_index)
        apply_reproducibility(
            ReproducibilityConfig(seed=split_seed, deterministic=cfg.reproducibility.deterministic),
            context=f"walk_forward:{symbol}:split_{split.split_index}",
        )
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

        LOGGER.info(
            "walk_forward split_start symbol=%s split=%d train_rows=%d val_rows=%d test_rows=%d train_sequences=%d val_sequences=%d test_sequences=%d",
            symbol,
            split.split_index,
            len(split.train),
            len(split.val),
            len(split.test),
            len(train_ds),
            len(val_ds),
            len(test_ds),
        )
        update_runtime_status(
            current_phase="walk_forward_split_start",
            current_symbol=symbol,
            progress_item=symbol,
            current_split_index=split.split_index,
            phase_detail=(
                f"split={split.split_index} train_rows={len(split.train)} val_rows={len(split.val)} "
                f"test_rows={len(split.test)} train_sequences={len(train_ds)} val_sequences={len(val_ds)} test_sequences={len(test_ds)}"
            ),
        )

        with TemporaryDirectory(prefix=f"mf_wf_{symbol}_{split.split_index}_") as tmp_dir:
            ckpt_callback = ModelCheckpoint(
                dirpath=tmp_dir,
                filename="best",
                monitor="val_loss",
                mode="min",
                save_top_k=1,
            )
            early_stop = EarlyStopping(monitor="val_loss", patience=cfg.model.patience, mode="min")
            progress_logger = _EpochProgressLogger(
                symbol=symbol,
                phase="walk_forward",
                debug_enabled=cfg.debug_train,
                split_index=split.split_index,
            )
            wf_model = LSTMAttentionModule(
                input_size=len(feature_cols),
                hidden_size=cfg.model.hidden_size,
                num_layers=cfg.model.num_layers,
                dropout=cfg.model.dropout,
                learning_rate=cfg.model.learning_rate,
                weight_decay=cfg.model.weight_decay,
                num_classes=cfg.model.num_classes,
                ternary_weight_short=cfg.model.ternary_weight_short,
                ternary_weight_flat=cfg.model.ternary_weight_flat,
                ternary_weight_long=cfg.model.ternary_weight_long,
            )
            trainer = L.Trainer(
                max_epochs=cfg.model.max_epochs,
                accelerator=cfg.accelerator,
                devices=1,
                callbacks=[ckpt_callback, early_stop, progress_logger],
                enable_progress_bar=False,
                logger=False,
                enable_model_summary=False,
            )
            LOGGER.info(
                "walk_forward fit_start symbol=%s split=%d accelerator=%s max_epochs=%d",
                symbol,
                split.split_index,
                cfg.accelerator,
                cfg.model.max_epochs,
            )
            update_runtime_status(
                current_phase="walk_forward_fit_start",
                current_symbol=symbol,
                progress_item=symbol,
                current_split_index=split.split_index,
                current_epoch=0,
                total_epochs=cfg.model.max_epochs,
                phase_detail=f"split={split.split_index} accelerator={cfg.accelerator}",
            )
            trainer.fit(
                wf_model,
                train_dataloaders=_build_loader(
                    train_ds,
                    cfg.model.batch_size,
                    shuffle=True,
                    seed=derive_seed(split_seed, "train_loader"),
                ),
                val_dataloaders=_build_loader(
                    val_ds,
                    cfg.model.batch_size,
                    shuffle=False,
                    seed=derive_seed(split_seed, "val_loader"),
                ),
            )
            best_path = Path(ckpt_callback.best_model_path) if ckpt_callback.best_model_path else Path(tmp_dir) / "best.ckpt"
            LOGGER.info(
                "walk_forward fit_completed symbol=%s split=%d epochs_ran=%d best_model_path=%s",
                symbol,
                split.split_index,
                trainer.current_epoch,
                best_path,
            )
            update_runtime_status(
                current_phase="walk_forward_fit_completed",
                current_symbol=symbol,
                progress_item=symbol,
                current_split_index=split.split_index,
                current_epoch=trainer.current_epoch,
                total_epochs=cfg.model.max_epochs,
                phase_detail=f"split={split.split_index} best_model_path={best_path}",
            )
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
                ternary_policy=_build_ternary_policy(cfg),
            )
            if test_metrics:
                _train_dates = split.train["date"] if "date" in split.train.columns else None
                _val_dates = split.val["date"] if "date" in split.val.columns else None
                _test_dates = split.test["date"] if "date" in split.test.columns else None
                fold_metrics.append({
                    "split_index": split.split_index,
                    "train_rows": len(split.train),
                    "val_rows": len(split.val),
                    "test_rows": len(split.test),
                    "train_start_date": str(_train_dates.min().date()) if _train_dates is not None and not _train_dates.empty else None,
                    "train_end_date": str(_train_dates.max().date()) if _train_dates is not None and not _train_dates.empty else None,
                    "val_start_date": str(_val_dates.min().date()) if _val_dates is not None and not _val_dates.empty else None,
                    "val_end_date": str(_val_dates.max().date()) if _val_dates is not None and not _val_dates.empty else None,
                    "test_start_date": str(_test_dates.min().date()) if _test_dates is not None and not _test_dates.empty else None,
                    "test_end_date": str(_test_dates.max().date()) if _test_dates is not None and not _test_dates.empty else None,
                    "calibration_method": calibrator.method if calibrator is not None and calibrator.fitted else "none",
                    "threshold_optimization": threshold_summary,
                    **test_metrics,
                })

    summary = _aggregate_walk_forward_metrics(fold_metrics)
    if summary:
        update_runtime_status(
            current_phase="walk_forward_completed",
            current_symbol=symbol,
            progress_item=symbol,
            phase_detail=f"splits={summary['n_splits']} mean_auc={summary['mean'].get('auc')}",
        )
        LOGGER.info(
            "walk_forward completed symbol=%s splits=%d mean_auc=%s",
            symbol,
            summary["n_splits"],
            summary["mean"].get("auc"),
        )
    else:
        update_runtime_status(current_phase="walk_forward_completed", current_symbol=symbol, progress_item=symbol)
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
    selector_df: "pd.DataFrame | None" = None,
    *,
    cross_sectional_df: "pd.DataFrame | None" = None,
    batch_id: str | None = None,
) -> TrainResult:
    """Entraîne un modèle LSTM+Attention pour un symbole unique.

    Returns:
        TrainResult avec status completed|skipped|failed.
    """
    torch.set_float32_matmul_precision("medium")

    run_id = f"{symbol}_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}"
    registry_id: int = 0

    if engine is not None:
        try:
            registry_id = ensure_registry_entry(engine, symbol)
            # Extraire les bornes des données d'entraînement pour le calibrateur
            _train_start: date | None = None
            _train_end: date | None = None
            if not bars_df.empty and "date" in bars_df.columns:
                _min_raw = bars_df["date"].min()
                _max_raw = bars_df["date"].max()
                _train_start = _min_raw.date() if hasattr(_min_raw, "date") else None
                _train_end = _max_raw.date() if hasattr(_max_raw, "date") else None
            insert_training_run(
                engine, run_id, registry_id, symbol, status="running",
                train_start_date=_train_start, train_end_date=_train_end,
                **({"batch_id": batch_id} if batch_id is not None else {}),
            )
        except Exception as exc:  # noqa: BLE001
            _record_training_db_issue(symbol, run_id, operation="insert_training_run", exc=exc)
            engine = None

    try:
        symbol_seed = derive_seed(cfg.reproducibility.seed, "train_symbol", symbol)
        reproducibility_state = apply_reproducibility(
            ReproducibilityConfig(seed=symbol_seed, deterministic=cfg.reproducibility.deterministic),
            context=f"train_symbol:{symbol}",
        )
        update_runtime_status(
            reproducibility_seed=int(reproducibility_state.get("seed", symbol_seed) or symbol_seed),
            reproducibility_deterministic=bool(reproducibility_state.get("deterministic_requested", cfg.reproducibility.deterministic)),
            reproducibility_deterministic_applied=bool(reproducibility_state.get("deterministic_applied", False)),
        )
        if len(bars_df) < cfg.data.min_history_days:
            reason = f"history_too_short rows={len(bars_df)} min={cfg.data.min_history_days}"
            return _skip_train_symbol(symbol=symbol, run_id=run_id, reason=reason, engine=engine)

        # ── Log target configuration (P2 2026-07-01) ───────────────
        LOGGER.info(
            "ml_train symbol=%s run_id=%s target_mode=%s horizon=%dj up=%.4f down=%.4f decision_threshold=%.2f calibration=%s",
            symbol,
            run_id,
            cfg.data.target_mode,
            cfg.data.forecast_horizon,
            cfg.data.target_up_threshold,
            cfg.data.target_down_threshold,
            cfg.data.decision_threshold,
            cfg.calibration.method,
        )

        effective_cfg = cfg
        target_optimization_summary: dict[str, Any] = {}
        if cfg.target_optimization.enabled:
            target_optimization_summary = _prepare_target_optimization_summary(
                bars_df=bars_df,
                cfg=cfg,
                sentiment_df=sentiment_df,
                benchmark_df=benchmark_df,
                universe_df=universe_df,
                selector_df=selector_df,
            )
            selected_horizon = int(target_optimization_summary.get("selected_horizon", cfg.data.forecast_horizon))
            selected_up_threshold = float(target_optimization_summary.get("selected_target_up_threshold", cfg.data.target_up_threshold))
            selected_down_threshold = float(target_optimization_summary.get("selected_target_down_threshold", cfg.data.target_down_threshold))
            selected_stop_atr_mult = float(target_optimization_summary.get("selected_triple_barrier_stop_atr_mult", cfg.data.triple_barrier_stop_atr_mult))
            selected_tp_atr_mult = float(target_optimization_summary.get("selected_triple_barrier_tp_atr_mult", cfg.data.triple_barrier_tp_atr_mult))
            selected_max_sessions = int(target_optimization_summary.get("selected_triple_barrier_max_sessions", cfg.data.triple_barrier_max_sessions))
            effective_forecast_horizon = (
                selected_max_sessions
                if cfg.data.label_method == "triple_barrier"
                else selected_horizon
            )
            if (
                effective_forecast_horizon != cfg.data.forecast_horizon
                or selected_up_threshold != cfg.data.target_up_threshold
                or selected_down_threshold != cfg.data.target_down_threshold
                or selected_stop_atr_mult != cfg.data.triple_barrier_stop_atr_mult
                or selected_tp_atr_mult != cfg.data.triple_barrier_tp_atr_mult
                or selected_max_sessions != cfg.data.triple_barrier_max_sessions
            ):
                effective_cfg = replace(
                    cfg,
                    data=replace(
                        cfg.data,
                        forecast_horizon=effective_forecast_horizon,
                        target_up_threshold=selected_up_threshold,
                        target_down_threshold=selected_down_threshold,
                        triple_barrier_stop_atr_mult=selected_stop_atr_mult,
                        triple_barrier_tp_atr_mult=selected_tp_atr_mult,
                        triple_barrier_max_sessions=selected_max_sessions,
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
        if selector_df is not None:
            datamodule_kwargs["selector_df"] = selector_df
        if cross_sectional_df is not None:
            datamodule_kwargs["cross_sectional_df"] = cross_sectional_df
        datamodule_signature = inspect.signature(SymbolDataModule)
        if "reproducibility_seed" in datamodule_signature.parameters:
            datamodule_kwargs["reproducibility_seed"] = derive_seed(symbol_seed, "symbol_datamodule")
        dm = SymbolDataModule(
            bars_df,
            effective_cfg.data,
            effective_cfg.model,
            **datamodule_kwargs,
        )
        update_runtime_status(current_phase="dataset_setup", current_symbol=symbol, progress_item=symbol)
        dm.setup()

        if dm.train_ds is None or dm.val_ds is None or len(dm.train_ds) == 0 or len(dm.val_ds) == 0:
            reason = "insufficient_sequences_after_split"
            return _skip_train_symbol(symbol=symbol, run_id=run_id, reason=reason, engine=engine)

        walk_forward_metrics: dict[str, Any] = {}
        prepared_df = getattr(dm, "prepared_df", None)
        if prepared_df is not None:
            walk_forward_metrics = _run_walk_forward_validation(symbol, prepared_df, effective_cfg)

        sym_dir = (Path(cfg.artifacts_dir) / symbol).resolve()
        sym_dir.mkdir(parents=True, exist_ok=True)

        final_fit_seed = derive_seed(symbol_seed, "final_fit")
        apply_reproducibility(
            ReproducibilityConfig(seed=final_fit_seed, deterministic=effective_cfg.reproducibility.deterministic),
            context=f"train_symbol:{symbol}:final_fit",
        )

        model = LSTMAttentionModule(
            input_size=dm.n_features,
            hidden_size=effective_cfg.model.hidden_size,
            num_layers=effective_cfg.model.num_layers,
            dropout=effective_cfg.model.dropout,
            learning_rate=effective_cfg.model.learning_rate,
            weight_decay=effective_cfg.model.weight_decay,
            num_classes=effective_cfg.model.num_classes,
            ternary_weight_short=effective_cfg.model.ternary_weight_short,
            ternary_weight_flat=effective_cfg.model.ternary_weight_flat,
            ternary_weight_long=effective_cfg.model.ternary_weight_long,
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
            callbacks=[
                ckpt_callback,
                early_stop,
                _EpochProgressLogger(symbol=symbol, phase="final_train", debug_enabled=effective_cfg.debug_train),
            ],
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

        LOGGER.info(
            "train_symbol fit_start symbol=%s max_epochs=%d walk_forward_enabled=%s",
            symbol,
            effective_cfg.model.max_epochs,
            effective_cfg.walk_forward.enabled,
        )
        update_runtime_status(
            current_phase="final_fit_start",
            current_symbol=symbol,
            progress_item=symbol,
            current_epoch=0,
            total_epochs=effective_cfg.model.max_epochs,
            phase_detail=f"walk_forward_enabled={effective_cfg.walk_forward.enabled}",
        )

        trainer.fit(model, datamodule=dm)

        LOGGER.info(
            "train_symbol fit_completed symbol=%s epochs_ran=%d best_model_path=%s",
            symbol,
            trainer.current_epoch,
            ckpt_callback.best_model_path or (sym_dir / "best.ckpt"),
        )
        update_runtime_status(
            current_phase="final_fit_completed",
            current_symbol=symbol,
            progress_item=symbol,
            current_epoch=trainer.current_epoch,
            total_epochs=effective_cfg.model.max_epochs,
            phase_detail=f"best_model_path={ckpt_callback.best_model_path or (sym_dir / 'best.ckpt')}",
        )

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
            ternary_policy=_build_ternary_policy(effective_cfg),
        )
        if selected_decision_threshold != effective_cfg.data.decision_threshold:
            effective_cfg = replace(
                effective_cfg,
                data=replace(effective_cfg.data, decision_threshold=selected_decision_threshold),
            )

        baseline_metrics: dict[str, Any] = {}
        if prepared_df is not None and effective_cfg.baseline.enabled:
            update_runtime_status(current_phase="baseline_lightgbm", current_symbol=symbol, progress_item=symbol)
            baseline_metrics = run_lightgbm_baseline(prepared_df, effective_cfg, artifact_dir=sym_dir, ternary_policy=_build_ternary_policy(effective_cfg))
            # LightGBM walk-forward
            if effective_cfg.walk_forward.enabled and baseline_metrics.get("status") == "completed":
                from modelFactory.tabular_baseline import run_tabular_walk_forward
                lgbm_wf = run_tabular_walk_forward(
                    prepared_df, effective_cfg,
                    model_name="lightgbm",
                    model_builder=lambda seed: __import__("lightgbm").LGBMClassifier(
                        objective="multiclass" if effective_cfg.data.target_mode == "ternary" else "binary",
                        num_class=3 if effective_cfg.data.target_mode == "ternary" else 1,
                        max_depth=effective_cfg.baseline.max_depth,
                        n_estimators=effective_cfg.baseline.n_estimators,
                        learning_rate=effective_cfg.baseline.learning_rate,
                        random_state=seed, verbosity=-1,
                    ),
                    ternary_policy=_build_ternary_policy(effective_cfg),
                )
                if lgbm_wf.get("status") == "completed" and lgbm_wf.get("mean"):
                    baseline_metrics["wf"] = lgbm_wf["mean"]
                    baseline_metrics["walk_forward"] = lgbm_wf
        catboost_metrics: dict[str, Any] = {}
        if prepared_df is not None and effective_cfg.baseline.enable_catboost:
            update_runtime_status(current_phase="baseline_catboost", current_symbol=symbol, progress_item=symbol)
            catboost_metrics = run_catboost_baseline(prepared_df, effective_cfg, artifact_dir=sym_dir, ternary_policy=_build_ternary_policy(effective_cfg))
            # CatBoost walk-forward
            if effective_cfg.walk_forward.enabled and catboost_metrics.get("status") == "completed":
                from modelFactory.tabular_baseline import run_tabular_walk_forward
                cb_wf = run_tabular_walk_forward(
                    prepared_df, effective_cfg,
                    model_name="catboost",
                    model_builder=lambda seed: __import__("catboost").CatBoostClassifier(
                        depth=effective_cfg.baseline.catboost_depth,
                        iterations=effective_cfg.baseline.catboost_iterations,
                        learning_rate=effective_cfg.baseline.catboost_learning_rate,
                        random_seed=seed,
                        loss_function="MultiClass" if effective_cfg.data.target_mode == "ternary" else "Logloss",
                        verbose=False, allow_writing_files=False,
                    ),
                    ternary_policy=_build_ternary_policy(effective_cfg),
                )
                if cb_wf.get("status") == "completed" and cb_wf.get("mean"):
                    catboost_metrics["wf"] = cb_wf["mean"]
                    catboost_metrics["walk_forward"] = cb_wf

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
        feature_contract = build_feature_contract(
            include_sentiment=effective_cfg.data.include_sentiment_features,
            feature_set=effective_cfg.data.feature_set,
            include_cross_sectional=effective_cfg.data.enable_cross_sectional_features,
            include_selector_context=effective_cfg.data.include_selector_context_features,
            include_short_score=effective_cfg.data.include_short_score_features,
            feature_columns=list(dm.scaler.feature_names),
            scaler_feature_names=list(dm.scaler.feature_names),
        )
        lightgbm_feature_columns = list(baseline_metrics.get("feature_columns") or []) if baseline_metrics else []
        lightgbm_feature_contract = (
            baseline_metrics.get("feature_contract")
            if baseline_metrics and baseline_metrics.get("feature_contract")
            else _build_feature_contract_for_columns(effective_cfg, lightgbm_feature_columns)
        )
        catboost_feature_columns = list(catboost_metrics.get("feature_columns") or []) if catboost_metrics else []
        catboost_feature_contract = (
            catboost_metrics.get("feature_contract")
            if catboost_metrics and catboost_metrics.get("feature_contract")
            else _build_feature_contract_for_columns(effective_cfg, catboost_feature_columns)
        )
        artifact_routes_models = {
            "lstm_attention": {
                "checkpoint_path": str(sym_dir / "best.ckpt"),
                "scaler_path": str(sym_dir / "scaler.pkl"),
                "config_path": str(config_path),
                "calibrator_path": calibrator_path,
                "feature_columns": list(dm.scaler.feature_names),
                "feature_fingerprint": feature_contract.get("feature_fingerprint"),
                "feature_contract": feature_contract,
                "selected_decision_threshold": effective_cfg.data.decision_threshold,
                "inference_backend": "lstm_attention",
            },
            "lightgbm": _build_tabular_artifact_route(
                metrics=baseline_metrics,
                config_path=config_path,
                feature_contract=lightgbm_feature_contract,
                default_backend="lightgbm_tabular",
            ),
            "catboost": _build_tabular_artifact_route(
                metrics=catboost_metrics,
                config_path=config_path,
                feature_contract=catboost_feature_contract,
                default_backend="catboost_tabular",
            ),
        }
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
        champion_decision = select_champion(challengers, artifact_routes_models, effective_cfg.champion_selection)
        challengers = champion_decision["annotated_challengers"]
        selected_architecture = str(champion_decision["selected_model"])
        selection_mode = str(champion_decision["selection_mode"])
        challenger_ranking = build_challenger_ranking(
            challengers,
            artifact_routes_models,
            selected_architecture,
            selection_mode=selection_mode,
            champion_cfg=effective_cfg.champion_selection,
        )
        cross_sectional_feature_columns = list(getattr(dm, "cross_sectional_feature_columns", []))
        cross_sectional_diagnostics = dict(getattr(dm, "cross_sectional_diagnostics", {}))
        trained_through_date = None
        if not bars_df.empty and "date" in bars_df.columns:
            trained_through_raw = bars_df["date"].max()
            trained_through_date = trained_through_raw.date().isoformat() if hasattr(trained_through_raw, "date") else str(trained_through_raw)
        config_data = {
            "data": asdict(effective_cfg.data),
            "model": {**asdict(effective_cfg.model), "input_size": dm.n_features},
            "calibration": asdict(effective_cfg.calibration),
            "walk_forward": asdict(effective_cfg.walk_forward),
            "baseline": asdict(effective_cfg.baseline),
            "champion_selection": asdict(effective_cfg.champion_selection),
            "target_optimization": asdict(effective_cfg.target_optimization),
            "threshold_optimization": asdict(effective_cfg.threshold_optimization),
            "reproducibility": {
                **asdict(effective_cfg.reproducibility),
                "symbol_seed": int(symbol_seed),
                "final_fit_seed": int(final_fit_seed),
                "deterministic_applied": bool(reproducibility_state.get("deterministic_applied", False)),
            },
            "symbol": symbol,
            "run_id": run_id,
            "batch_id": batch_id,
            "artifacts_dir": str(cfg.artifacts_dir),
            "feature_columns": dm.scaler.feature_names,
            "feature_contract": feature_contract,
            "cross_sectional_feature_columns": cross_sectional_feature_columns,
            "cross_sectional_diagnostics": cross_sectional_diagnostics,
            "calibrator_path": calibrator_path,
            "selected_forecast_horizon": effective_cfg.data.forecast_horizon,
            "selected_target_up_threshold": effective_cfg.data.target_up_threshold,
            "selected_target_down_threshold": effective_cfg.data.target_down_threshold,
            "selected_triple_barrier_stop_atr_mult": effective_cfg.data.triple_barrier_stop_atr_mult,
            "selected_triple_barrier_tp_atr_mult": effective_cfg.data.triple_barrier_tp_atr_mult,
            "selected_triple_barrier_max_sessions": effective_cfg.data.triple_barrier_max_sessions,
            "selected_decision_threshold": effective_cfg.data.decision_threshold,
            "trained_through_date": trained_through_date,
            "architecture_selected": selected_architecture,
            "selection_mode": selection_mode,
            "selection_reason": champion_decision.get("selection_reason"),
            "selected_model_eligible": bool(champion_decision.get("selected_model_eligible", False)),
            "artifact_signature_required": True,
            "artifact_signature_manifest_path": str(sym_dir / "artifact_signature_manifest.json"),
            "artifact_routes": {
                "selected_model": selected_architecture,
                "models": artifact_routes_models,
            },
            "feature_fingerprint": compute_feature_fingerprint(
                include_sentiment=effective_cfg.data.include_sentiment_features,
                feature_set=effective_cfg.data.feature_set,
                include_cross_sectional=effective_cfg.data.enable_cross_sectional_features,
                include_selector_context=effective_cfg.data.include_selector_context_features,
                include_short_score=effective_cfg.data.include_short_score_features,
                feature_columns=list(dm.scaler.feature_names),
            ),
        }
        _atomic_write_json(config_path, config_data)

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
                "feature_contract": feature_contract,
                "cross_sectional_feature_columns": cross_sectional_feature_columns,
                "cross_sectional_diagnostics": cross_sectional_diagnostics,
            },
            "champion": {
                "model_name": selected_architecture,
                "selection_mode": selection_mode,
                "selection_metric": effective_cfg.champion_selection.selection_metric,
                "selection_score": champion_decision.get("selection_score", challengers.get(selected_architecture, {}).get("selection_score", lstm_selection_score)),
                "selection_reason": champion_decision.get("selection_reason"),
                "selected_model_eligible": bool(champion_decision.get("selected_model_eligible", False)),
            },
            "challengers": {
                "ranking": challenger_ranking,
                **challengers,
            },
        }
        _atomic_write_json(sym_dir / "metrics.json", all_metrics)
        persist_artifact_signature_manifest(
            sym_dir / "artifact_signature_manifest.json",
            symbol=symbol,
            run_id=run_id,
            selected_model=selected_architecture,
            artifact_routes_models=artifact_routes_models,
        )

        if engine is not None:
            try:
                _run_training_registry_writes(
                    engine,
                    run_id=run_id,
                    symbol=symbol,
                    trainer=trainer,
                    best_ckpt=best_ckpt,
                    scaler_path=scaler_path,
                    config_path=config_path,
                    val_metrics=val_metrics,
                    test_metrics=test_metrics,
                    walk_forward_metrics=walk_forward_metrics,
                    all_metrics=all_metrics,
                    challengers=challengers,
                    artifact_routes_models=artifact_routes_models,
                    selected_architecture=selected_architecture,
                    selection_mode=selection_mode,
                    selection_metric=effective_cfg.champion_selection.selection_metric,
                    challenger_ranking=challenger_ranking,
                )
            except Exception as exc:  # noqa: BLE001
                _record_training_db_issue(symbol, run_id, operation="training_registry_writes", exc=exc)

        LOGGER.info(
            "train_symbol completed symbol=%s run_id=%s val_loss=%.4f calibration=%s decision_threshold=%.2f",
            symbol,
            run_id,
            float(val_metrics.get("loss", -1.0) or -1.0),
            calibrator.method if calibrator is not None and calibrator.fitted else "none",
            effective_cfg.data.decision_threshold,
        )
        update_runtime_status(
            current_phase="train_symbol_completed",
            current_symbol=symbol,
            progress_item=symbol,
            phase_detail=f"run_id={run_id} decision_threshold={effective_cfg.data.decision_threshold:.2f}",
        )
        return TrainResult(symbol, run_id, "completed", metrics=all_metrics)

    except Exception as exc:
        LOGGER.exception("train_symbol failed symbol=%s run_id=%s", symbol, run_id)
        update_runtime_status(
            current_phase="train_symbol_failed",
            current_symbol=symbol,
            progress_item=symbol,
            phase_detail=str(exc)[:200],
        )
        if engine is not None:
            try:
                update_training_run(engine, run_id, status="failed", skip_reason=str(exc)[:200], finished_at=datetime.now(timezone.utc))
            except Exception as db_exc:  # noqa: BLE001
                _record_training_db_issue(symbol, run_id, operation="update_training_run_failed", exc=db_exc)
        return TrainResult(symbol, run_id, "failed", skip_reason=str(exc))








