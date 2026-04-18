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

from modelFactory.config import DataConfig
from modelFactory.data_loader import load_symbol_bars
from modelFactory.dataset import FeatureScaler
from modelFactory.db_registry import insert_predictions
from modelFactory.features import compute_features
from modelFactory.model import LSTMAttentionModule

LOGGER = logging.getLogger(__name__)


def predict_symbol(
    symbol: str,
    artifacts_dir: Path,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: Optional[date] = None,
    run_id: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """Charge le modèle et produit une prédiction pour un symbole.

    Returns:
        DataFrame avec colonnes: symbol, prediction_date, predicted_proba, predicted_class, run_id
        ou None si artefacts manquants.
    """
    sym_dir = artifacts_dir / symbol
    ckpt_path = sym_dir / "best.ckpt"
    scaler_path = sym_dir / "scaler.pkl"
    config_path = sym_dir / "config.json"

    if not ckpt_path.exists() or not scaler_path.exists() or not config_path.exists():
        LOGGER.warning("predict_symbol no_artifacts symbol=%s", symbol)
        return None

    # Load config
    with open(config_path) as f:
        cfg_data = json.load(f)

    data_cfg = DataConfig(
        sequence_length=cfg_data["data"]["sequence_length"],
        forecast_horizon=cfg_data["data"]["forecast_horizon"],
    )
    run_id = run_id or cfg_data.get("run_id", "unknown")

    # Load scaler
    with open(scaler_path, "rb") as f:
        scaler = FeatureScaler.from_state_dict(pickle.load(f))

    # Load bars (last seq_len + buffer days)
    bars = load_symbol_bars(engine, symbol)
    if len(bars) < data_cfg.sequence_length + 60:
        LOGGER.warning("predict_symbol insufficient_bars symbol=%s", symbol)
        return None

    # Feature engineering
    df = compute_features(bars)
    if len(df) < data_cfg.sequence_length:
        return None

    # Take last sequence
    last_rows = df.tail(data_cfg.sequence_length)
    features = scaler.transform(last_rows)
    x = torch.from_numpy(features.astype(np.float32)).unsqueeze(0)  # [1, seq, feat]

    # Load model
    model = LSTMAttentionModule.load_from_checkpoint(str(ckpt_path))
    model.eval()

    with torch.no_grad():
        logits, _ = model(x)
        proba = torch.softmax(logits, dim=1)[0, 1].item()

    pred_date = prediction_date or date.today()
    pred_class = 1 if proba > 0.5 else 0

    result = pd.DataFrame([{
        "symbol": symbol,
        "prediction_date": pred_date,
        "predicted_proba": round(proba, 6),
        "predicted_class": pred_class,
        "run_id": run_id,
    }])

    # Persist
    insert_predictions(engine, result)
    LOGGER.info("predict_symbol symbol=%s date=%s proba=%.4f class=%d", symbol, pred_date, proba, pred_class)
    return result


def predict_batch(
    symbols: list[str],
    artifacts_dir: Path,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: Optional[date] = None,
) -> pd.DataFrame:
    """Exécute les prédictions pour une liste de symboles."""
    all_preds = []
    for sym in symbols:
        pred = predict_symbol(sym, artifacts_dir, engine, prediction_date)
        if pred is not None:
            all_preds.append(pred)
    if all_preds:
        return pd.concat(all_preds, ignore_index=True)
    return pd.DataFrame(columns=["symbol", "prediction_date", "predicted_proba", "predicted_class", "run_id"])

