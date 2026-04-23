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
from modelFactory.cross_sectional import build_cross_sectional_features, merge_cross_sectional_features
from modelFactory.data_loader import load_benchmark_bars, load_symbol_bars, load_symbol_sentiment, load_universe_bars
from modelFactory.dataset import FeatureScaler
from modelFactory.db_registry import insert_predictions, load_candidate_symbols, load_training_run
from modelFactory.features import compute_features, get_feature_columns
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


def _resolve_selected_model_route(
    cfg_data: dict,
    ckpt_path: Path,
    scaler_path: Path,
    config_path: Path,
) -> dict[str, object]:
    routing = cfg_data.get("artifact_routes") or {}
    selected_model = str(routing.get("selected_model") or cfg_data.get("architecture_selected") or "lstm_attention")
    models = routing.get("models") or {}
    if selected_model == "global_model":
        global_route = models.get("global_model") or {}
        if global_route.get("inference_backend") == "global_tabular" and global_route.get("config_path"):
            return {
                "selected_model": "global_model",
                "inference_backend": "global_tabular",
                "config_path": Path(global_route["config_path"]),
                "model_path": Path(global_route["model_path"]) if global_route.get("model_path") else None,
                "calibrator_path": Path(global_route["calibrator_path"]) if global_route.get("calibrator_path") else None,
            }
        LOGGER.warning("predict_symbol selected_model=global_model but route missing -> fallback lstm_attention")

    lstm_route = models.get("lstm_attention") or {}
    routed_ckpt = Path(lstm_route.get("checkpoint_path")) if lstm_route.get("checkpoint_path") else ckpt_path
    routed_scaler = Path(lstm_route.get("scaler_path")) if lstm_route.get("scaler_path") else scaler_path
    return {
        "selected_model": "lstm_attention",
        "inference_backend": "lstm_attention",
        "checkpoint_path": routed_ckpt,
        "scaler_path": routed_scaler,
        "config_path": config_path,
    }


def _load_data_cfg_from_payload(cfg_data: dict) -> DataConfig:
    return DataConfig(
        sequence_length=cfg_data["data"]["sequence_length"],
        forecast_horizon=cfg_data["data"]["forecast_horizon"],
        include_sentiment_features=cfg_data["data"].get("include_sentiment_features", False),
        enable_cross_sectional_features=cfg_data["data"].get("enable_cross_sectional_features", False),
        cross_sectional_min_universe=cfg_data["data"].get("cross_sectional_min_universe", 20),
        feature_set=cfg_data["data"].get("feature_set", "v1"),
        benchmark_symbol=cfg_data["data"].get("benchmark_symbol", "SPY"),
        target_mode=cfg_data["data"].get("target_mode", "binary"),
        target_up_threshold=cfg_data["data"].get("target_up_threshold", 0.0),
        target_down_threshold=cfg_data["data"].get("target_down_threshold", 0.0),
        decision_threshold=cfg_data["data"].get("decision_threshold", cfg_data.get("selected_decision_threshold", 0.5)),
    )


def _prepare_prediction_frame(
    symbol: str,
    *,
    data_cfg: DataConfig,
    engine: "Engine",  # type: ignore[name-defined]
    cutoff_date: date | None,
) -> pd.DataFrame:
    bars = load_symbol_bars(engine, symbol, end_date=cutoff_date)
    if len(bars) < data_cfg.sequence_length + 60:
        LOGGER.warning("predict_symbol insufficient_bars symbol=%s", symbol)
        return pd.DataFrame()

    sentiment_df = None
    if data_cfg.include_sentiment_features:
        sentiment_df = load_symbol_sentiment(engine, symbol, end_date=cutoff_date)
    benchmark_df = None
    if data_cfg.feature_set == "expert" or data_cfg.enable_cross_sectional_features:
        benchmark_df = load_benchmark_bars(engine, data_cfg.benchmark_symbol, end_date=cutoff_date)
    df = compute_features(
        bars,
        sentiment_df=sentiment_df,
        include_sentiment=data_cfg.include_sentiment_features,
        benchmark_df=benchmark_df,
        feature_set=data_cfg.feature_set,
    )
    if data_cfg.enable_cross_sectional_features:
        universe_symbols = load_candidate_symbols(engine)
        if symbol not in universe_symbols:
            universe_symbols.append(symbol)
        universe_df = load_universe_bars(engine, universe_symbols, end_date=cutoff_date)
        cross_sectional_df, _ = build_cross_sectional_features(
            universe_df,
            benchmark_df=benchmark_df,
            min_universe_size=data_cfg.cross_sectional_min_universe,
        )
        df = merge_cross_sectional_features(df, cross_sectional_df)
        active_features = get_feature_columns(
            data_cfg.include_sentiment_features,
            feature_set=data_cfg.feature_set,
            include_cross_sectional=True,
        )
        df = df.dropna(subset=active_features).reset_index(drop=True)
    return df


def _predict_with_global_model(
    symbol: str,
    *,
    cfg_data: dict,
    model_path: Path,
    calibrator_path: Path | None,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: date | None,
    as_of_date: date | None,
    persist: bool,
) -> Optional[pd.DataFrame]:
    if not model_path.exists():
        LOGGER.warning("predict_symbol global_model_missing symbol=%s path=%s", symbol, model_path)
        return None
    data_cfg = _load_data_cfg_from_payload(cfg_data)
    cutoff_date = as_of_date or prediction_date
    df = _prepare_prediction_frame(symbol, data_cfg=data_cfg, engine=engine, cutoff_date=cutoff_date)
    feature_columns = cfg_data.get("feature_columns") or get_feature_columns(
        data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
    )
    if df.empty or len(df) == 0:
        return None
    last_row = df.tail(1)
    with open(model_path, "rb") as fh:
        model = pickle.load(fh)
    raw_proba = float(model.predict_proba(last_row[feature_columns])[:, 1][0])
    calibrator = None
    if calibrator_path is not None and calibrator_path.exists():
        with open(calibrator_path, "rb") as fh:
            calibrator = calibrator_from_state_dict(pickle.load(fh))
    proba = raw_proba
    if calibrator is not None and calibrator.fitted:
        eps = 1e-6
        margin = np.log(np.clip(raw_proba, eps, 1 - eps) / np.clip(1 - raw_proba, eps, 1 - eps))
        proba = float(calibrator.predict_proba(np.array([margin], dtype=np.float64))[0])
    pred_date = prediction_date or date.today()
    pred_class = 1 if proba >= data_cfg.decision_threshold else 0
    signal_label = "long" if pred_class == 1 else "no_trade"
    result = pd.DataFrame([{
        "symbol": symbol,
        "prediction_date": pred_date,
        "predicted_proba": round(proba, 6),
        "predicted_class": pred_class,
        "run_id": cfg_data.get("run_id", cfg_data.get("artifact_symbol", "global_model")),
        "raw_proba": round(raw_proba, 6),
        "decision_threshold": data_cfg.decision_threshold,
        "signal_label": signal_label,
        "calibration_method": getattr(calibrator, "method", "none") if calibrator is not None and calibrator.fitted else "none",
        "selected_model": "global_model",
    }])
    if persist:
        insert_predictions(engine, result)
    return result


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

    route = _resolve_selected_model_route(cfg_data, ckpt_path, scaler_path, config_path)
    selected_architecture = str(route["selected_model"])
    if route.get("inference_backend") == "global_tabular":
        global_config_path = route.get("config_path")
        if global_config_path is None or not Path(global_config_path).exists():
            LOGGER.warning("predict_symbol global_route_missing_config symbol=%s", symbol)
            return None
        with open(Path(global_config_path), encoding="utf-8") as fh:
            global_cfg_data = json.load(fh)
        return _predict_with_global_model(
            symbol,
            cfg_data=global_cfg_data,
            model_path=Path(route["model_path"]),
            calibrator_path=Path(route["calibrator_path"]) if route.get("calibrator_path") else None,
            engine=engine,
            prediction_date=prediction_date,
            as_of_date=as_of_date,
            persist=persist,
        )

    ckpt_path = Path(route["checkpoint_path"])
    scaler_path = Path(route["scaler_path"])
    if not ckpt_path.exists() or not scaler_path.exists():
        LOGGER.warning("predict_symbol routed_artifacts_missing symbol=%s selected_model=%s", symbol, selected_architecture)
        return None

    data_cfg = _load_data_cfg_from_payload(cfg_data)
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
    df = _prepare_prediction_frame(symbol, data_cfg=data_cfg, engine=engine, cutoff_date=cutoff_date)
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
        "selected_model": selected_architecture,
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

