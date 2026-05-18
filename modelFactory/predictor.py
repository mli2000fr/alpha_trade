"""modelFactory/predictor.py — Service d'inférence pour les modèles entraînés."""
from __future__ import annotations

import json
import logging
import pickle
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import torch

from modelFactory.calibration import calibrator_from_state_dict, margin_from_logits
from modelFactory.config import DataConfig
from modelFactory.cross_sectional import build_cross_sectional_features, merge_cross_sectional_features
from modelFactory.data_loader import load_benchmark_bars, load_symbol_bars, load_symbol_sentiment, load_universe_bars
from modelFactory.dataset import FeatureScaler
from modelFactory.db_registry import insert_predictions, load_candidate_symbols, load_training_run
from modelFactory.features import compute_features, get_feature_columns, validate_feature_contract
from modelFactory.model import LSTMAttentionModule
from modelFactory.runtime_status import increment_runtime_counter, update_runtime_status

LOGGER = logging.getLogger(__name__)


class ArtifactIntegrityError(RuntimeError):
    """Erreur explicite quand un artefact requis est absent, illisible ou corrompu."""

    def __init__(self, reason: str, *, path: Path | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.path = path


def _record_artifact_issue(symbol: str, *, reason: str, path: Path | None = None) -> None:
    increment_runtime_counter("prediction_artifact_issue_count", 1)
    update_runtime_status(
        last_prediction_symbol=symbol,
        last_artifact_issue_reason=reason,
        last_artifact_issue_path=str(path) if path is not None else None,
    )


def _record_prediction_fallback(
    symbol: str,
    *,
    requested_model: object,
    served_model: object,
    reason: str,
) -> None:
    increment_runtime_counter("prediction_fallback_count", 1)
    update_runtime_status(
        last_prediction_symbol=symbol,
        last_requested_model=str(requested_model or ""),
        last_served_model=str(served_model or ""),
        last_fallback_reason=reason,
    )


def _load_json_dict(path: Path, *, symbol: str, artifact_kind: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
    except FileNotFoundError as exc:
        reason = f"{artifact_kind}_missing"
        LOGGER.error("predict_symbol %s symbol=%s path=%s", reason, symbol, path)
        _record_artifact_issue(symbol, reason=reason, path=path)
        raise ArtifactIntegrityError(reason, path=path) from exc
    except json.JSONDecodeError as exc:
        reason = f"{artifact_kind}_json_invalid"
        LOGGER.error("predict_symbol %s symbol=%s path=%s error=%s", reason, symbol, path, exc)
        _record_artifact_issue(symbol, reason=reason, path=path)
        raise ArtifactIntegrityError(reason, path=path) from exc
    except Exception as exc:  # noqa: BLE001
        reason = f"{artifact_kind}_read_failed"
        LOGGER.error("predict_symbol %s symbol=%s path=%s error=%s", reason, symbol, path, exc)
        _record_artifact_issue(symbol, reason=reason, path=path)
        raise ArtifactIntegrityError(reason, path=path) from exc
    if not isinstance(payload, dict):
        reason = f"{artifact_kind}_payload_not_object"
        LOGGER.error("predict_symbol %s symbol=%s path=%s", reason, symbol, path)
        _record_artifact_issue(symbol, reason=reason, path=path)
        raise ArtifactIntegrityError(reason, path=path)
    return payload


def _load_optional_calibrator(
    calibrator_path: Path | None,
    *,
    symbol: str,
    selected_model: str,
) -> Any:
    if calibrator_path is None or not calibrator_path.exists():
        return None
    try:
        return load_calibrator_cached(calibrator_path)
    except Exception as exc:  # noqa: BLE001
        reason = f"calibrator_corrupted:{selected_model}"
        LOGGER.warning(
            "predict_symbol calibrator_fallback symbol=%s selected_model=%s path=%s error=%s",
            symbol,
            selected_model,
            calibrator_path,
            exc,
        )
        increment_runtime_counter("prediction_calibration_fallback_count", 1)
        update_runtime_status(
            last_prediction_symbol=symbol,
            last_calibration_fallback_reason=reason,
            last_calibration_fallback_path=str(calibrator_path),
        )
        return None


def _path_from_value(value: object) -> Path | None:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    return None


def _numeric_threshold(value: object, default: float) -> float:
    try:
        if value is None:
            raise TypeError
        return float(value)
    except (TypeError, ValueError):
        return float(default)


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


def _check_feature_contract(cfg_data: dict, *, symbol: str, config_path: Path) -> str | None:
    data_cfg = cfg_data.get("data") or {}
    try:
        reason = validate_feature_contract(
            cfg_data.get("feature_contract"),
            include_sentiment=bool(data_cfg.get("include_sentiment_features", False)),
            feature_set=str(data_cfg.get("feature_set", "v1")),
            include_cross_sectional=bool(data_cfg.get("enable_cross_sectional_features", False)),
            persisted_feature_columns=cfg_data.get("feature_columns"),
            persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
            allow_legacy_missing_contract=True,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("feature_contract_check_failed symbol=%s error=%s", symbol, exc)
        return f"feature_contract_check_failed:{exc}"
    if reason is not None:
        LOGGER.error("feature_contract_violation symbol=%s reason=%s", symbol, reason)
        _record_artifact_issue(symbol, reason=f"feature_contract_violation:{reason}", path=config_path)
    return reason


# Phase 4.2.c — chargement format natif (.txt/.cbm) avec rétrocompat .pkl.
class _LightGBMBoosterAdapter:
    """Adapter exposant ``predict_proba`` pour un Booster LightGBM natif."""

    def __init__(self, booster: Any) -> None:
        self._booster = booster

    def predict_proba(self, X: Any) -> np.ndarray:  # type: ignore[name-defined]
        import numpy as _np
        proba_pos = self._booster.predict(X)
        proba_pos = _np.asarray(proba_pos, dtype=float).ravel()
        return _np.column_stack([1.0 - proba_pos, proba_pos])


def _load_tabular_model(model_path: Path, *, selected_model: str) -> Any:
    """Charge un modèle tabulaire en routant selon l'extension.

    - ``.txt`` → LightGBM Booster natif (``lgb.Booster(model_file=)``).
    - ``.cbm`` → CatBoostClassifier natif (``load_model``).
    - ``.pkl`` → rétrocompat pickle + WARNING déprécié (Phase 4.2.c).
    """
    suffix = model_path.suffix.lower()
    if suffix == ".txt":
        import lightgbm as lgb  # type: ignore[import-not-found]
        booster = lgb.Booster(model_file=str(model_path))
        return _LightGBMBoosterAdapter(booster)
    if suffix == ".cbm":
        from catboost import CatBoostClassifier  # type: ignore[import-not-found]
        model = CatBoostClassifier()
        model.load_model(str(model_path))
        return model
    if suffix == ".pkl":
        LOGGER.warning(
            "tabular_model_pkl_deprecated symbol_model=%s path=%s "
            "(Phase 4.2.c : ré-entraîner pour migrer vers format natif)",
            selected_model, model_path,
        )
        with open(model_path, "rb") as fh:
            return pickle.load(fh)
    raise ValueError(f"Extension non supportée pour modèle tabulaire : {model_path.suffix}")


# ---------------------------------------------------------------------------
# Phase 4.2.d — Cache LRU des modèles / scalers / calibrators.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=128)
def _cached_tabular_model(model_path_str: str, mtime_ns: int, selected_model: str) -> Any:
    return _load_tabular_model(Path(model_path_str), selected_model=selected_model)


@lru_cache(maxsize=128)
def _cached_scaler(scaler_path_str: str, mtime_ns: int) -> Any:
    with open(scaler_path_str, "rb") as fh:
        return FeatureScaler.from_state_dict(pickle.load(fh))


@lru_cache(maxsize=128)
def _cached_calibrator(calibrator_path_str: str, mtime_ns: int) -> Any:
    with open(calibrator_path_str, "rb") as fh:
        return calibrator_from_state_dict(pickle.load(fh))


@lru_cache(maxsize=64)
def _cached_lstm_module(ckpt_path_str: str, mtime_ns: int, device_str: str) -> Any:
    import torch as _torch
    device_obj = _torch.device(device_str)
    module = LSTMAttentionModule.load_from_checkpoint(ckpt_path_str, map_location=device_obj)
    module.to(device_obj)
    module.eval()
    return module


def _safe_mtime_ns(path: Path) -> int:
    try:
        return int(path.stat().st_mtime_ns)
    except OSError:
        return 0


def load_tabular_model_cached(model_path: Path, *, selected_model: str) -> Any:
    """API publique du cache (Phase 4.2.d)."""
    return _cached_tabular_model(str(model_path.resolve()), _safe_mtime_ns(model_path), selected_model)


def load_scaler_cached(scaler_path: Path) -> Any:
    return _cached_scaler(str(scaler_path.resolve()), _safe_mtime_ns(scaler_path))


def load_calibrator_cached(calibrator_path: Path) -> Any:
    return _cached_calibrator(str(calibrator_path.resolve()), _safe_mtime_ns(calibrator_path))


def load_lstm_module_cached(ckpt_path: Path, device: Any) -> Any:
    return _cached_lstm_module(str(ckpt_path.resolve()), _safe_mtime_ns(ckpt_path), str(device))


def clear_model_cache() -> None:
    """Vide tous les caches LRU de modèles/scalers/calibrators (Phase 4.2.d)."""
    _cached_tabular_model.cache_clear()
    _cached_scaler.cache_clear()
    _cached_calibrator.cache_clear()
    _cached_lstm_module.cache_clear()


def _resolve_selected_model_route(
    cfg_data: dict,
    ckpt_path: Path,
    scaler_path: Path,
    config_path: Path,
) -> dict[str, object]:
    routing = cfg_data.get("artifact_routes") or {}
    selected_model = str(routing.get("selected_model") or cfg_data.get("architecture_selected") or "lstm_attention")
    models = routing.get("models") or {}
    fallback_reason: str | None = None
    if selected_model == "global_model":
        global_route = models.get("global_model") or {}
        if global_route.get("inference_backend") == "global_tabular" and global_route.get("config_path"):
            return {
                "requested_model": selected_model,
                "selected_model": "global_model",
                "inference_backend": "global_tabular",
                "config_path": Path(global_route["config_path"]),
                "model_path": Path(global_route["model_path"]) if global_route.get("model_path") else None,
                "calibrator_path": Path(global_route["calibrator_path"]) if global_route.get("calibrator_path") else None,
                "feature_columns": list(global_route.get("feature_columns") or []),
                "feature_fingerprint": global_route.get("feature_fingerprint"),
                "feature_contract": global_route.get("feature_contract"),
            }
        fallback_reason = "selected_model=global_model route_missing -> fallback_lstm_attention"
        LOGGER.warning("predict_symbol %s", fallback_reason)

    if selected_model in {"lightgbm", "catboost"}:
        local_route = models.get(selected_model) or {}
        expected_backend = f"{selected_model}_tabular"
        route_config_path = Path(local_route["config_path"]) if local_route.get("config_path") else config_path
        if local_route.get("inference_backend") == expected_backend and local_route.get("model_path"):
            return {
                "requested_model": selected_model,
                "selected_model": selected_model,
                "inference_backend": expected_backend,
                "config_path": route_config_path,
                "model_path": Path(local_route["model_path"]),
                "calibrator_path": Path(local_route["calibrator_path"]) if local_route.get("calibrator_path") else None,
                "feature_columns": list(local_route.get("feature_columns") or []),
                "feature_fingerprint": local_route.get("feature_fingerprint"),
                "feature_contract": local_route.get("feature_contract"),
                "selected_decision_threshold": local_route.get("selected_decision_threshold"),
            }
        fallback_reason = f"selected_model={selected_model} route_missing -> fallback_lstm_attention"
        LOGGER.warning("predict_symbol %s", fallback_reason)

    lstm_route = models.get("lstm_attention") or {}
    routed_ckpt = Path(lstm_route.get("checkpoint_path")) if lstm_route.get("checkpoint_path") else ckpt_path
    routed_scaler = Path(lstm_route.get("scaler_path")) if lstm_route.get("scaler_path") else scaler_path
    return {
        "requested_model": selected_model,
        "selected_model": "lstm_attention",
        "inference_backend": "lstm_attention",
        "checkpoint_path": routed_ckpt,
        "scaler_path": routed_scaler,
        "config_path": config_path,
        "fallback_reason": fallback_reason,
    }


def _build_lstm_fallback_route(
    cfg_data: dict,
    *,
    ckpt_path: Path,
    scaler_path: Path,
    config_path: Path,
    requested_model: object,
    reason: str,
) -> dict[str, object]:
    routing = cfg_data.get("artifact_routes") or {}
    models = routing.get("models") or {}
    lstm_route = models.get("lstm_attention") or {}
    routed_ckpt = _path_from_value(lstm_route.get("checkpoint_path")) or ckpt_path
    routed_scaler = _path_from_value(lstm_route.get("scaler_path")) or scaler_path
    routed_config = _path_from_value(lstm_route.get("config_path")) or config_path
    return {
        "requested_model": str(requested_model or routing.get("selected_model") or cfg_data.get("architecture_selected") or "lstm_attention"),
        "selected_model": "lstm_attention",
        "inference_backend": "lstm_attention",
        "checkpoint_path": routed_ckpt,
        "scaler_path": routed_scaler,
        "config_path": routed_config,
        "fallback_reason": reason,
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
    config_path: Path,
    model_path: Path,
    calibrator_path: Path | None,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: date | None,
    as_of_date: date | None,
    persist: bool,
) -> Optional[pd.DataFrame]:
    return _predict_with_tabular_model(
        symbol,
        selected_model="global_model",
        cfg_data=cfg_data,
        model_path=model_path,
        calibrator_path=calibrator_path,
        engine=engine,
        prediction_date=prediction_date,
        as_of_date=as_of_date,
        persist=persist,
        feature_columns=cfg_data.get("feature_columns"),
        decision_threshold=cfg_data.get("selected_decision_threshold"),
        config_path=config_path,
    )


def _predict_with_tabular_model(
    symbol: str,
    *,
    selected_model: str,
    cfg_data: dict,
    model_path: Path,
    calibrator_path: Path | None,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: date | None,
    as_of_date: date | None,
    persist: bool,
    feature_columns: list[str] | None = None,
    decision_threshold: float | None = None,
    config_path: Path | None = None,
    route_feature_fingerprint: object = None,
    route_feature_contract: object = None,
) -> Optional[pd.DataFrame]:
    if not model_path.exists():
        reason = f"tabular_model_missing:{selected_model}"
        LOGGER.error("predict_symbol %s symbol=%s path=%s", reason, symbol, model_path)
        _record_artifact_issue(symbol, reason=reason, path=model_path)
        raise ArtifactIntegrityError(reason, path=model_path)
    data_cfg = _load_data_cfg_from_payload(cfg_data)
    cutoff_date = as_of_date or prediction_date
    df = _prepare_prediction_frame(symbol, data_cfg=data_cfg, engine=engine, cutoff_date=cutoff_date)
    resolved_feature_columns = list(feature_columns or cfg_data.get("feature_columns") or get_feature_columns(
        data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
    ))
    if df.empty or len(df) == 0:
        return None
    last_row = df.tail(1)
    contract_reason = validate_feature_contract(
        route_feature_contract if isinstance(route_feature_contract, dict) else cfg_data.get("feature_contract"),
        include_sentiment=data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
        persisted_feature_columns=cfg_data.get("feature_columns"),
        persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
        route_feature_columns=resolved_feature_columns,
        route_feature_fingerprint=route_feature_fingerprint,
        runtime_feature_columns=list(last_row.columns),
        allow_legacy_missing_contract=True,
    )
    if contract_reason is not None:
        LOGGER.error(
            "predict_symbol feature_contract_violation symbol=%s selected_model=%s reason=%s",
            symbol,
            selected_model,
            contract_reason,
        )
        _record_artifact_issue(symbol, reason=f"feature_contract_violation:{selected_model}", path=config_path)
        return None
    missing_columns = [col for col in resolved_feature_columns if col not in last_row.columns]
    if missing_columns:
        LOGGER.error(
            "predict_symbol feature_contract_violation symbol=%s selected_model=%s missing=%s expected=%s",
            symbol,
            selected_model,
            missing_columns,
            resolved_feature_columns,
        )
        return None
    try:
        model = load_tabular_model_cached(model_path, selected_model=selected_model)
    except Exception as exc:  # noqa: BLE001
        reason = f"tabular_model_corrupted:{selected_model}"
        LOGGER.error(
            "predict_symbol %s symbol=%s path=%s error=%s",
            reason,
            symbol,
            model_path,
            exc,
        )
        _record_artifact_issue(symbol, reason=reason, path=model_path)
        raise ArtifactIntegrityError(reason, path=model_path) from exc
    raw_proba = float(model.predict_proba(last_row[resolved_feature_columns])[:, 1][0])
    calibrator = _load_optional_calibrator(calibrator_path, symbol=symbol, selected_model=selected_model)
    proba = raw_proba
    if calibrator is not None and calibrator.fitted:
        eps = 1e-6
        margin = np.log(np.clip(raw_proba, eps, 1 - eps) / np.clip(1 - raw_proba, eps, 1 - eps))
        proba = float(calibrator.predict_proba(np.array([margin], dtype=np.float64))[0])
    threshold_value = decision_threshold if decision_threshold is not None else cfg_data.get("selected_decision_threshold", data_cfg.decision_threshold)
    effective_threshold = _numeric_threshold(threshold_value, data_cfg.decision_threshold)
    pred_date = prediction_date or date.today()
    pred_class = 1 if proba >= effective_threshold else 0
    signal_label = "long" if pred_class == 1 else "no_trade"
    calibration_method = getattr(calibrator, "method", "none") if calibrator is not None and calibrator.fitted else "none"
    result = pd.DataFrame([{
        "symbol": symbol,
        "prediction_date": pred_date,
        "predicted_proba": round(proba, 6),
        "predicted_class": pred_class,
        "run_id": cfg_data.get("run_id", cfg_data.get("artifact_symbol", selected_model)),
        "raw_proba": round(raw_proba, 6),
        "decision_threshold": effective_threshold,
        "signal_label": signal_label,
        "calibration_method": calibration_method,
        "selected_model": selected_model,
    }])
    update_runtime_status(
        last_prediction_symbol=symbol,
        last_requested_model=selected_model,
        last_served_model=selected_model,
        last_decision_threshold=effective_threshold,
        last_calibration_method=calibration_method,
        last_prediction_date=pred_date.isoformat(),
    )
    if persist:
        insert_predictions(engine, result)
    LOGGER.info(
        "predict_symbol served symbol=%s selected_model=%s threshold=%.4f calibration=%s proba=%.4f class=%d",
        symbol,
        selected_model,
        effective_threshold,
        calibration_method,
        proba,
        pred_class,
    )
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

    if not config_path.exists():
        LOGGER.warning("predict_symbol no_artifacts symbol=%s path=%s", symbol, config_path)
        _record_artifact_issue(symbol, reason="config_missing", path=config_path)
        return None

    device = _resolve_inference_device(accelerator)

    # Load config
    try:
        cfg_data = _load_json_dict(config_path, symbol=symbol, artifact_kind="config")
    except ArtifactIntegrityError:
        return None

    fingerprint_reason = _check_feature_contract(cfg_data, symbol=symbol, config_path=config_path)
    if fingerprint_reason is not None:
        LOGGER.error("predict_symbol aborted symbol=%s reason=%s", symbol, fingerprint_reason)
        return None

    route = _resolve_selected_model_route(cfg_data, ckpt_path, scaler_path, config_path)
    selected_architecture = str(route["selected_model"])
    if route.get("inference_backend") == "global_tabular":
        global_config_path = _path_from_value(route.get("config_path"))
        model_path = _path_from_value(route.get("model_path"))
        if global_config_path is None or not global_config_path.exists() or model_path is None or not model_path.exists():
            route = _build_lstm_fallback_route(
                cfg_data,
                ckpt_path=ckpt_path,
                scaler_path=scaler_path,
                config_path=config_path,
                requested_model=route.get("requested_model"),
                reason="requested_model=global_model route_unservable -> fallback_lstm_attention",
            )
            selected_architecture = str(route["selected_model"])
        else:
            try:
                global_cfg_data = _load_json_dict(global_config_path, symbol=symbol, artifact_kind="global_config")
                return _predict_with_global_model(
                    symbol,
                    cfg_data=global_cfg_data,
                    config_path=global_config_path,
                    model_path=model_path,
                    calibrator_path=_path_from_value(route.get("calibrator_path")),
                    engine=engine,
                    prediction_date=prediction_date,
                    as_of_date=as_of_date,
                    persist=persist,
                )
            except ArtifactIntegrityError as exc:
                route = _build_lstm_fallback_route(
                    cfg_data,
                    ckpt_path=ckpt_path,
                    scaler_path=scaler_path,
                    config_path=config_path,
                    requested_model=route.get("requested_model"),
                    reason=f"requested_model=global_model {exc.reason} -> fallback_lstm_attention",
                )
                selected_architecture = str(route["selected_model"])

    if route.get("inference_backend") in {"lightgbm_tabular", "catboost_tabular"}:
        local_config_path = _path_from_value(route.get("config_path")) or config_path
        model_path = _path_from_value(route.get("model_path"))
        if not local_config_path.exists() or model_path is None or not model_path.exists():
            route = _build_lstm_fallback_route(
                cfg_data,
                ckpt_path=ckpt_path,
                scaler_path=scaler_path,
                config_path=config_path,
                requested_model=route.get("requested_model"),
                reason=f"requested_model={selected_architecture} route_unservable -> fallback_lstm_attention",
            )
            selected_architecture = str(route["selected_model"])
        else:
            local_cfg_data = cfg_data
            try:
                if local_config_path.resolve() != config_path.resolve():
                    local_cfg_data = _load_json_dict(local_config_path, symbol=symbol, artifact_kind=f"{selected_architecture}_config")
                return _predict_with_tabular_model(
                    symbol,
                    selected_model=selected_architecture,
                    cfg_data=local_cfg_data,
                    model_path=model_path,
                    calibrator_path=_path_from_value(route.get("calibrator_path")),
                    engine=engine,
                    prediction_date=prediction_date,
                    as_of_date=as_of_date,
                    persist=persist,
                    feature_columns=list(route.get("feature_columns") or []),
                    decision_threshold=_numeric_threshold(route.get("selected_decision_threshold"), cfg_data.get("data", {}).get("decision_threshold", 0.5)) if route.get("selected_decision_threshold") is not None else None,
                    config_path=local_config_path,
                    route_feature_fingerprint=route.get("feature_fingerprint"),
                    route_feature_contract=route.get("feature_contract"),
                )
            except ArtifactIntegrityError as exc:
                route = _build_lstm_fallback_route(
                    cfg_data,
                    ckpt_path=ckpt_path,
                    scaler_path=scaler_path,
                    config_path=config_path,
                    requested_model=route.get("requested_model"),
                    reason=f"requested_model={selected_architecture} {exc.reason} -> fallback_lstm_attention",
                )
                selected_architecture = str(route["selected_model"])

    if route.get("fallback_reason"):
        _record_prediction_fallback(
            symbol,
            requested_model=route.get("requested_model"),
            served_model=route.get("selected_model"),
            reason=str(route.get("fallback_reason")),
        )
        LOGGER.warning(
            "predict_symbol route_fallback symbol=%s requested_model=%s served_model=%s reason=%s",
            symbol,
            route.get("requested_model"),
            route.get("selected_model"),
            route.get("fallback_reason"),
        )

    ckpt_path = Path(route["checkpoint_path"])
    scaler_path = Path(route["scaler_path"])
    if not ckpt_path.exists() or not scaler_path.exists():
        LOGGER.warning("predict_symbol routed_artifacts_missing symbol=%s selected_model=%s", symbol, selected_architecture)
        missing_path = ckpt_path if not ckpt_path.exists() else scaler_path
        _record_artifact_issue(symbol, reason=f"lstm_route_missing:{selected_architecture}", path=missing_path)
        return None

    data_cfg = _load_data_cfg_from_payload(cfg_data)
    run_id = selected_run_id or cfg_data.get("run_id", "unknown")

    # Load scaler (Phase 4.2.d : cache LRU)
    try:
        scaler = load_scaler_cached(scaler_path)
    except Exception as exc:  # noqa: BLE001
        reason = f"lstm_scaler_corrupted:{selected_architecture}"
        LOGGER.error("predict_symbol %s symbol=%s path=%s error=%s", reason, symbol, scaler_path, exc)
        _record_artifact_issue(symbol, reason=reason, path=scaler_path)
        return None

    calibrator_path_raw = cfg_data.get("calibrator_path")
    calibrator_path = Path(calibrator_path_raw) if calibrator_path_raw else config_path.with_name("calibrator.pkl")
    calibrator = _load_optional_calibrator(calibrator_path, symbol=symbol, selected_model=selected_architecture)

    cutoff_date = as_of_date or prediction_date
    df = _prepare_prediction_frame(symbol, data_cfg=data_cfg, engine=engine, cutoff_date=cutoff_date)
    if len(df) < data_cfg.sequence_length:
        LOGGER.warning("predict_symbol insufficient_sequences symbol=%s rows=%d required=%d", symbol, len(df), data_cfg.sequence_length)
        return None

    contract_reason = validate_feature_contract(
        cfg_data.get("feature_contract"),
        include_sentiment=data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
        persisted_feature_columns=cfg_data.get("feature_columns"),
        persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
        scaler_feature_names=list(getattr(scaler, "feature_names", [])),
        route_feature_columns=route.get("feature_columns"),
        route_feature_fingerprint=route.get("feature_fingerprint"),
        runtime_feature_columns=list(df.columns),
        allow_legacy_missing_contract=True,
    )
    if contract_reason is not None:
        LOGGER.error(
            "predict_symbol feature_contract_violation symbol=%s selected_model=%s reason=%s",
            symbol,
            selected_architecture,
            contract_reason,
        )
        _record_artifact_issue(symbol, reason=f"feature_contract_violation:{selected_architecture}", path=config_path)
        return None

    # Take last sequence
    last_rows = df.tail(data_cfg.sequence_length)
    try:
        features = scaler.transform(last_rows)
    except KeyError as exc:
        LOGGER.error("predict_symbol feature_contract_violation symbol=%s selected_model=%s error=%s", symbol, selected_architecture, exc)
        return None
    x = torch.from_numpy(features.astype(np.float32)).unsqueeze(0).to(device=device, non_blocking=device.type == "cuda")  # [1, seq, feat]

    # Load model (Phase 4.2.d : cache LRU)
    if device.type == "cuda":
        torch.set_float32_matmul_precision("medium")
    try:
        model = load_lstm_module_cached(ckpt_path, device)
    except Exception as exc:  # noqa: BLE001
        reason = f"lstm_checkpoint_corrupted:{selected_architecture}"
        LOGGER.error("predict_symbol %s symbol=%s path=%s error=%s", reason, symbol, ckpt_path, exc)
        _record_artifact_issue(symbol, reason=reason, path=ckpt_path)
        return None

    device_name = torch.cuda.get_device_name(device) if device.type == "cuda" else "cpu"
    update_runtime_status(
        last_prediction_symbol=symbol,
        resolved_accelerator=str(device),
        resolved_device_name=device_name,
        last_served_model=selected_architecture,
    )
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
    calibration_method = getattr(calibrator, "method", "none") if calibrator is not None and calibrator.fitted else "none"

    result = pd.DataFrame([{
        "symbol": symbol,
        "prediction_date": pred_date,
        "predicted_proba": round(proba, 6),
        "predicted_class": pred_class,
        "run_id": run_id,
        "raw_proba": round(raw_proba, 6),
        "decision_threshold": data_cfg.decision_threshold,
        "signal_label": signal_label,
        "calibration_method": calibration_method,
        "selected_model": selected_architecture,
    }])
    update_runtime_status(
        last_prediction_symbol=symbol,
        last_requested_model=str(route.get("requested_model") or selected_architecture),
        last_served_model=selected_architecture,
        last_decision_threshold=float(data_cfg.decision_threshold),
        last_calibration_method=calibration_method,
        last_prediction_date=pred_date.isoformat(),
    )

    # Persist
    if persist:
        insert_predictions(engine, result)
    LOGGER.info(
        "predict_symbol served symbol=%s selected_model=%s requested_model=%s date=%s proba=%.4f raw_proba=%.4f class=%d signal=%s threshold=%.4f calibration=%s",
        symbol,
        selected_architecture,
        str(route.get("requested_model") or selected_architecture),
        pred_date,
        proba,
        raw_proba,
        pred_class,
        signal_label,
        float(data_cfg.decision_threshold),
        calibration_method,
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
    completed = 0
    skipped = 0
    total = len(symbols)
    update_runtime_status(
        current_phase="predict_batch_start",
        progress_label="🔮 Progression ML Predict",
        progress_total=total,
        progress_current=0,
        current_symbol=None,
        current_symbol_index=0,
        current_symbol_total=total,
        symbols_total=total,
        symbols_completed=0,
        symbols_skipped=0,
        symbols_failed=0,
    )
    for index, sym in enumerate(symbols, start=1):
        update_runtime_status(
            current_phase="predict_symbol_start",
            current_symbol=sym,
            current_symbol_index=index,
            progress_item=sym,
        )
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
            completed += 1
            phase = "predict_symbol_completed"
        else:
            skipped += 1
            phase = "predict_symbol_skipped"
        update_runtime_status(
            current_phase=phase,
            current_symbol=sym,
            current_symbol_index=index,
            progress_current=completed + skipped,
            symbols_completed=completed,
            symbols_skipped=skipped,
            symbols_failed=0,
            progress_item=sym,
        )
    update_runtime_status(
        current_phase="predict_batch_completed",
        progress_current=completed + skipped,
        symbols_completed=completed,
        symbols_skipped=skipped,
        symbols_failed=0,
        progress_item=None,
    )
    if all_preds:
        return pd.concat(all_preds, ignore_index=True)
    return pd.DataFrame(columns=["symbol", "prediction_date", "predicted_proba", "predicted_class", "run_id"])

