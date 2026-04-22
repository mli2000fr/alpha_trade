"""modelFactory/predictor.py — Service d'inférence pour les modèles entraînés."""
from __future__ import annotations

import json
import logging
import pickle
from datetime import date
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import torch

from modelFactory.calibration import calibrator_from_state_dict, margin_from_logits
from modelFactory.config import DataConfig
from modelFactory.data_loader import load_symbol_bars, load_symbol_sentiment
from modelFactory.dataset import FeatureScaler
from modelFactory.db_registry import insert_predictions, load_training_run
from modelFactory.features import compute_features
from modelFactory.model import LSTMAttentionModule

LOGGER = logging.getLogger(__name__)


def _resolve_inference_device(accelerator: str = "auto") -> torch.device:
    requested = accelerator.strip().lower()
    if requested not in {"auto", "cpu", "gpu"}:
        raise ValueError("accelerator doit être 'auto', 'cpu' ou 'gpu'.")

    if requested == "cpu":
        return torch.device("cpu")

    if requested == "gpu":
        if torch.cuda.is_available():
            return torch.device("cuda:0")
        LOGGER.warning("predict accelerator=gpu requested but cuda unavailable -> fallback cpu")
        return torch.device("cpu")

    return torch.device("cuda:0") if torch.cuda.is_available() else torch.device("cpu")


def _resolve_artifact_paths(
    symbol: str,
    artifacts_dir: Path,
    engine: "Engine",  # type: ignore[name-defined]
    run_id: Optional[str],
) -> tuple[Path, Path, Path, Optional[str]]:
    """Résout les artefacts depuis le registre DB, sinon via le dossier canonique du symbole."""
    selected_run = load_training_run(engine, symbol, run_id=run_id)
    if selected_run is not None:
        ckpt_path = Path(selected_run["checkpoint_path"])
        scaler_path = Path(selected_run["scaler_path"])
        config_path = Path(selected_run["config_path"])
        if ckpt_path.exists() and scaler_path.exists() and config_path.exists():
            return ckpt_path, scaler_path, config_path, str(selected_run["run_id"])
        LOGGER.warning(
            "predict_symbol registry_artifacts_missing symbol=%s run_id=%s fallback=canonical_dir",
            symbol,
            selected_run.get("run_id"),
        )

    sym_dir = artifacts_dir / symbol
    return sym_dir / "best.ckpt", sym_dir / "scaler.pkl", sym_dir / "config.json", run_id


def predict_symbol(
    symbol: str,
    artifacts_dir: Path,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: Optional[date] = None,
    run_id: Optional[str] = None,
    as_of_date: Optional[date] = None,
    persist: bool = True,
    accelerator: str = "auto",
) -> Optional[pd.DataFrame]:
    """Charge le modèle et produit une prédiction pour un symbole.

    Returns:
        DataFrame avec colonnes: symbol, prediction_date, predicted_proba, predicted_class, run_id
        ou None si artefacts manquants.
    """
    ckpt_path, scaler_path, config_path, selected_run_id = _resolve_artifact_paths(symbol, artifacts_dir, engine, run_id)

    if not ckpt_path.exists() or not scaler_path.exists() or not config_path.exists():
        LOGGER.warning("predict_symbol no_artifacts symbol=%s", symbol)
        return None

    device = _resolve_inference_device(accelerator)

    # Load config
    with open(config_path) as f:
        cfg_data = json.load(f)

    data_cfg = DataConfig(
        sequence_length=cfg_data["data"]["sequence_length"],
        forecast_horizon=cfg_data["data"]["forecast_horizon"],
        include_sentiment_features=cfg_data["data"].get("include_sentiment_features", False),
        target_mode=cfg_data["data"].get("target_mode", "binary"),
        target_up_threshold=cfg_data["data"].get("target_up_threshold", 0.0),
        target_down_threshold=cfg_data["data"].get("target_down_threshold", 0.0),
        decision_threshold=cfg_data["data"].get("decision_threshold", 0.5),
    )
    run_id = selected_run_id or cfg_data.get("run_id", "unknown")

    # Load scaler
    with open(scaler_path, "rb") as f:
        scaler = FeatureScaler.from_state_dict(pickle.load(f))

    calibrator = None
    calibrator_path_raw = cfg_data.get("calibrator_path")
    calibrator_path = Path(calibrator_path_raw) if calibrator_path_raw else config_path.with_name("calibrator.pkl")
    if calibrator_path.exists():
        with open(calibrator_path, "rb") as f:
            calibrator = calibrator_from_state_dict(pickle.load(f))

    cutoff_date = as_of_date or prediction_date

    # Load bars (last seq_len + buffer days) bornés à cutoff_date pour rester PIT-safe.
    bars = load_symbol_bars(engine, symbol, end_date=cutoff_date)
    if len(bars) < data_cfg.sequence_length + 60:
        LOGGER.warning("predict_symbol insufficient_bars symbol=%s", symbol)
        return None

    # Feature engineering (with optional sentiment)
    sentiment_df = None
    if data_cfg.include_sentiment_features:
        sentiment_df = load_symbol_sentiment(engine, symbol, end_date=cutoff_date)
    df = compute_features(bars, sentiment_df=sentiment_df, include_sentiment=data_cfg.include_sentiment_features)
    if len(df) < data_cfg.sequence_length:
        return None

    # Take last sequence
    last_rows = df.tail(data_cfg.sequence_length)
    features = scaler.transform(last_rows)
    x = torch.from_numpy(features.astype(np.float32)).unsqueeze(0).to(device=device, non_blocking=device.type == "cuda")  # [1, seq, feat]

    # Load model
    if device.type == "cuda":
        torch.set_float32_matmul_precision("medium")
    model = LSTMAttentionModule.load_from_checkpoint(str(ckpt_path), map_location=device)
    model.to(device)
    model.eval()

    device_name = torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu"
    LOGGER.info(
        "predict_symbol initialized symbol=%s requested_accelerator=%s resolved_device=%s device_name=%s",
        symbol,
        accelerator,
        device,
        device_name,
    )

    with torch.no_grad():
        logits, _ = model(x)
        raw_proba = torch.softmax(logits, dim=1)[0, 1].item()

    proba = raw_proba
    if calibrator is not None and calibrator.fitted:
        proba = float(calibrator.predict_proba(margin_from_logits(logits.cpu().numpy()))[0])

    pred_date = prediction_date or date.today()
    pred_class = 1 if proba >= data_cfg.decision_threshold else 0
    signal_label = "long" if pred_class == 1 else "no_trade"

    result = pd.DataFrame([{
        "symbol": symbol,
        "prediction_date": pred_date,
        "predicted_proba": round(proba, 6),
        "predicted_class": pred_class,
        "run_id": run_id,
        "raw_proba": round(raw_proba, 6),
        "decision_threshold": data_cfg.decision_threshold,
        "signal_label": signal_label,
        "calibration_method": getattr(calibrator, "method", "none") if calibrator is not None and calibrator.fitted else "none",
    }])

    # Persist
    if persist:
        insert_predictions(engine, result)
    LOGGER.info(
        "predict_symbol symbol=%s date=%s proba=%.4f raw_proba=%.4f class=%d signal=%s",
        symbol,
        pred_date,
        proba,
        raw_proba,
        pred_class,
        signal_label,
    )
    return result


def predict_batch(
    symbols: list[str],
    artifacts_dir: Path,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: Optional[date] = None,
    as_of_date: Optional[date] = None,
    persist: bool = True,
    accelerator: str = "auto",
) -> pd.DataFrame:
    """Exécute les prédictions pour une liste de symboles."""
    all_preds = []
    for sym in symbols:
        pred = predict_symbol(
            sym,
            artifacts_dir,
            engine,
            prediction_date,
            as_of_date=as_of_date,
            persist=persist,
            accelerator=accelerator,
        )
        if pred is not None:
            all_preds.append(pred)
    if all_preds:
        return pd.concat(all_preds, ignore_index=True)
    return pd.DataFrame(columns=["symbol", "prediction_date", "predicted_proba", "predicted_class", "run_id"])

