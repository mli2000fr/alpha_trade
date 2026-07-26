"""modelFactory/predictor.py — Service d'inférence pour les modèles entraînés."""
from __future__ import annotations

import json
import logging
import pickle
from collections import OrderedDict
from datetime import date
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import Any, Optional

import numpy as np
import pandas as pd
import torch

from modelFactory.calibration import calibrator_from_state_dict, margin_from_logits
from modelFactory.champion_selection import ArtifactSignatureError, verify_route_artifact_signatures
from modelFactory.config import DataConfig
from modelFactory.cross_sectional import build_cross_sectional_features, merge_cross_sectional_features
from core.ternary_decision_policy import decide_ternary_side, TernaryDecisionPolicy
from common.data_availability import (
    DataAvailabilityInfo,
    FutureDataError,
    QualityState,
    make_availability_from_bar_date,
    validate_availability,
)
from modelFactory.data_loader import (
    load_benchmark_bars,
    load_symbol_bars,
    load_symbol_selector_context,
    load_symbol_sentiment,
    load_universe_bars,
)
from modelFactory.dataset import FeatureScaler
from modelFactory.db_registry import insert_predictions, load_tradable_universe_symbols, load_training_run
from modelFactory.features import compute_features, get_feature_columns, validate_feature_contract
from modelFactory.model import LSTMAttentionModule
from modelFactory.runtime_status import increment_runtime_counter, update_runtime_status

LOGGER = logging.getLogger(__name__)

_BENCHMARK_FRAME_CACHE_MAX_ENTRIES = 8
_benchmark_frame_cache: OrderedDict[tuple[int, str, str | None], pd.DataFrame] = OrderedDict()
_benchmark_frame_cache_lock = Lock()
_CROSS_SECTIONAL_FRAME_CACHE_MAX_ENTRIES = 8
_cross_sectional_frame_cache: OrderedDict[tuple[object, ...], pd.DataFrame] = OrderedDict()
_cross_sectional_frame_cache_lock = Lock()
# Cache global_rank par cutoff_date (pour éviter de recalculer à chaque symbole)
_global_rank_prediction_cache: dict[str, pd.DataFrame | None] = {}
_global_rank_fallback_symbols: list[str] = []  # symboles ayant utilisé le fallback 0.5


class ArtifactIntegrityError(RuntimeError):
    """Erreur explicite quand un artefact requis est absent, illisible ou corrompu."""

    def __init__(self, reason: str, *, path: Path | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.path = path


def _record_db_issue(
    *,
    operation: str,
    symbol: str | None = None,
    reason: str,
) -> None:
    increment_runtime_counter("prediction_db_issue_count", 1)
    update_runtime_status(
        last_prediction_symbol=symbol,
        last_db_issue_operation=operation,
        last_db_issue_reason=reason,
    )


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


def _apply_optional_calibration(
    *,
    symbol: str,
    selected_model: str,
    calibrator: Any,
    margin: np.ndarray,
    calibrator_path: Path | None,
    raw_proba: float,
) -> tuple[float, str]:
    if calibrator is None or not getattr(calibrator, "fitted", False):
        return raw_proba, "none"
    # Temperature Scaling est géré séparément dans predict_symbol (ternaire)
    if getattr(calibrator, "method", None) == "temperature":
        return raw_proba, "none"
    try:
        calibrated = float(calibrator.predict_proba(margin)[0])
    except Exception as exc:  # noqa: BLE001
        reason = f"calibrator_incompatible:{selected_model}"
        LOGGER.warning(
            "predict_symbol calibrator_runtime_fallback symbol=%s selected_model=%s path=%s error=%s",
            symbol,
            selected_model,
            calibrator_path,
            exc,
        )
        increment_runtime_counter("prediction_calibration_fallback_count", 1)
        update_runtime_status(
            last_prediction_symbol=symbol,
            last_calibration_fallback_reason=reason,
            last_calibration_fallback_path=str(calibrator_path) if calibrator_path is not None else None,
        )
        return raw_proba, "none"
    return calibrated, str(getattr(calibrator, "method", "none") or "none")


def _extract_positive_class_probability(
    prediction_output: Any,
    *,
    symbol: str,
    selected_model: str,
    model_path: Path,
    target_mode: str = "binary",
) -> float:
    """Extrait la probabilite de la classe positive (long) depuis predict_proba.

    - binaire : colonne [:, 1] = classe positive
    - ternaire : colonne [:, 2] = long (apres label shift {0=short, 1=flat, 2=long})
    """
    try:
        proba = np.asarray(prediction_output, dtype=float)
    except Exception as exc:  # noqa: BLE001
        reason = f"tabular_model_incompatible:{selected_model}"
        LOGGER.error(
            "predict_symbol %s symbol=%s path=%s error=%s",
            reason,
            symbol,
            model_path,
            exc,
        )
        _record_artifact_issue(symbol, reason=reason, path=model_path)
        raise ArtifactIntegrityError(reason, path=model_path) from exc
    if proba.ndim != 2 or proba.shape[0] < 1 or proba.shape[1] < 2:
        reason = f"tabular_model_incompatible:{selected_model}"
        LOGGER.error(
            "predict_symbol %s symbol=%s path=%s shape=%s",
            reason,
            symbol,
            model_path,
            getattr(proba, "shape", None),
        )
        _record_artifact_issue(symbol, reason=reason, path=model_path)
        raise ArtifactIntegrityError(reason, path=model_path)
    # Ternary : 3 colonnes [short, flat, long] -> colonne 2 = long
    if target_mode == "ternary" and proba.shape[1] >= 3:
        return float(proba[0, 2])
    return float(proba[0, 1])


def _persist_predictions_best_effort(
    engine: "Engine",  # type: ignore[name-defined]
    result: pd.DataFrame,
    *,
    symbol: str,
) -> None:
    try:
        insert_predictions(engine, result)
    except Exception as exc:  # noqa: BLE001
        reason = f"prediction_persist_failed:{type(exc).__name__}"
        LOGGER.warning(
            "predict_symbol persistence_degraded symbol=%s rows=%d error=%s",
            symbol,
            len(result),
            exc,
        )
        _record_db_issue(operation="insert_predictions", symbol=symbol, reason=reason)


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
        return float(value if isinstance(value, (int, float, str)) else default)
    except (TypeError, ValueError):
        return float(default)


def _resolve_route_decision_threshold(route: dict[str, object], cfg_data: dict[str, Any]) -> float | None:
    threshold_value = route.get("selected_decision_threshold")
    if threshold_value is None:
        return None
    return _numeric_threshold(threshold_value, cfg_data.get("data", {}).get("decision_threshold", 0.5))


def _resolve_artifact_signature_manifest_path(cfg_data: dict[str, Any], *, config_path: Path) -> Path:
    raw_value = cfg_data.get("artifact_signature_manifest_path")
    resolved = _path_from_value(raw_value)
    return resolved or config_path.with_name("artifact_signature_manifest.json")


def _verify_route_signature_if_needed(
    *,
    cfg_data: dict[str, Any],
    route: dict[str, object],
    manifest_path: Path,
    symbol: str,
) -> None:
    required = bool(cfg_data.get("artifact_signature_required", False))
    if not required and not manifest_path.exists():
        return
    model_name = str(route.get("selected_model") or "").strip() or "unknown"
    try:
        verify_route_artifact_signatures(
            manifest_path=manifest_path,
            model_name=model_name,
            route=dict(route),
            required=required,
        )
    except ArtifactSignatureError as exc:
        LOGGER.error(
            "predict_symbol artifact_signature_failed symbol=%s model=%s manifest=%s reason=%s",
            symbol,
            model_name,
            manifest_path,
            exc.reason,
        )
        _record_artifact_issue(symbol, reason=exc.reason, path=exc.path or manifest_path)
        raise ArtifactIntegrityError(exc.reason, path=exc.path or manifest_path) from exc


def _build_prediction_result(
    *,
    symbol: str,
    prediction_date: date,
    proba: float,
    pred_class: int,
    run_id: str,
    raw_proba: float,
    decision_threshold: float,
    signal_label: str,
    calibration_method: str,
    selected_model: str,
    # ML Sprint 3 — champs ternaires optionnels
    predicted_side: str | None = None,
    proba_long: float | None = None,
    proba_flat: float | None = None,
    proba_short: float | None = None,
    # Sprint Maître 0 — policy partagée
    decision_policy_version: int = 1,
    decision_reason: str | None = None,
    # Sprint Maître 2 — PIT
    data_availability: DataAvailabilityInfo | None = None,
    data_quality: QualityState = QualityState.PRESENT,
) -> pd.DataFrame:
    row: dict[str, object] = {
        "symbol": symbol,
        "prediction_date": prediction_date,
        "predicted_proba": round(proba, 6),
        "predicted_class": pred_class,
        "run_id": run_id,
        "raw_proba": round(raw_proba, 6),
        "decision_threshold": decision_threshold,
        "signal_label": signal_label,
        "calibration_method": calibration_method,
        "selected_model": selected_model,
        "decision_policy_version": decision_policy_version,
    }
    if decision_reason is not None:
        row["decision_reason"] = decision_reason
    # ── Sprint Maître 2 : qualité PIT ──────────────────────────────────
    if data_availability is not None:
        row["data_source"] = data_availability.source
        row["data_available_at"] = data_availability.available_at.isoformat()
    row["data_quality"] = data_quality.value
    # Ajoute les colonnes ternaires si presentes
    if predicted_side is not None:
        row["predicted_side"] = predicted_side
        row["proba_long"] = round(proba_long, 6) if proba_long is not None else None
        row["proba_flat"] = round(proba_flat, 6) if proba_flat is not None else None
        row["proba_short"] = round(proba_short, 6) if proba_short is not None else None
    return pd.DataFrame([row])


def _has_matching_latest_feature_date(df: pd.DataFrame, cutoff_date: date | None) -> bool:
    if cutoff_date is None or df.empty or "date" not in df.columns:
        return True
    try:
        last_feature_date = pd.Timestamp(df["date"].iloc[-1]).date()
    except Exception:  # noqa: BLE001
        return False
    return last_feature_date == cutoff_date


# ── Sprint Maître 2 : validation PIT ─────────────────────────────────────────

def _pit_validate_bars(
    bars: pd.DataFrame,
    *,
    symbol: str,
    cutoff_date: date | None,
) -> None:
    """Valide qu'aucune barre n'est postérieure au cutoff (Sprint Maître 2).

    Cette fonction est un gate critique : toute barre future détectée
    est loggée comme erreur et doit être investiguée.
    """
    if cutoff_date is None or bars.empty or "date" not in bars.columns:
        return
    bar_dates = pd.to_datetime(bars["date"], errors="coerce").dt.date
    future_mask = bar_dates > cutoff_date
    if future_mask.any():
        future_dates = sorted(set(bar_dates[future_mask]))
        LOGGER.error(
            "PIT_VIOLATION future_bars symbol=%s cutoff=%s future_dates=%s count=%d",
            symbol, cutoff_date, future_dates[:5], future_mask.sum(),
        )
        increment_runtime_counter("pit_future_data_count", int(future_mask.sum()))
        update_runtime_status(
            last_prediction_symbol=symbol,
            last_pit_violation=f"future_bars:{future_dates[:3]}",
        )
        raise FutureDataError(
            make_availability_from_bar_date(str(future_dates[0])),
            pd.Timestamp(cutoff_date, tz="UTC").to_pydatetime(),
        )

    if "available_at" not in bars.columns:
        return
    available_at = pd.to_datetime(bars["available_at"], errors="coerce", utc=True)
    cutoff_timestamp = pd.Timestamp(cutoff_date, tz="UTC") + pd.Timedelta(days=1)
    unavailable_mask = available_at.isna() | (available_at > cutoff_timestamp)
    if unavailable_mask.any():
        increment_runtime_counter("pit_unavailable_data_count", int(unavailable_mask.sum()))
        update_runtime_status(
            last_prediction_symbol=symbol,
            last_pit_violation="unavailable_bars",
        )
        raise FutureDataError(
            make_availability_from_bar_date(str(bar_dates[unavailable_mask].iloc[0])),
            cutoff_timestamp.to_pydatetime(),
        )


def _pit_build_availability(
    bars: pd.DataFrame,
    *,
    symbol: str,
    cutoff_date: date | None,
    source: str = "eodhd",
) -> DataAvailabilityInfo | None:
    """Construit l'info de disponibilité PIT pour la barre la plus récente."""
    if cutoff_date is None or bars.empty or "date" not in bars.columns:
        return None
    try:
        latest_date = pd.Timestamp(bars["date"].iloc[-1]).date()
    except Exception:
        return None
    if "available_at" in bars.columns:
        latest_available_at = pd.to_datetime(bars["available_at"].iloc[-1], errors="coerce", utc=True)
        if not pd.isna(latest_available_at):
            return DataAvailabilityInfo(
                event_time=pd.Timestamp(bars["date"].iloc[-1], tz="UTC").to_pydatetime(),
                available_at=latest_available_at.to_pydatetime(),
                source=str(bars.get("data_source", pd.Series([source])).iloc[-1] or source),
            )
    return make_availability_from_bar_date(str(latest_date), source=source)


def _record_route_fallback_if_any(symbol: str, route: dict[str, object]) -> None:
    fallback_reason = route.get("fallback_reason")
    if not fallback_reason:
        return
    _record_prediction_fallback(
        symbol,
        requested_model=route.get("requested_model"),
        served_model=route.get("selected_model"),
        reason=str(fallback_reason),
    )
    LOGGER.warning(
        "predict_symbol route_fallback symbol=%s requested_model=%s served_model=%s reason=%s",
        symbol,
        route.get("requested_model"),
        route.get("selected_model"),
        fallback_reason,
    )


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
    batch_id: Optional[str] = None,
) -> tuple[Path, Path, Path, Optional[str]]:
    """Résout les artefacts depuis le registre DB, sinon via le dossier de campagne du symbole."""
    try:
        if batch_id is not None:
            selected_run = load_training_run(engine, symbol, run_id=run_id, batch_id=batch_id)
        else:
            selected_run = load_training_run(engine, symbol, run_id=run_id)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning(
            "predict_symbol registry_lookup_failed symbol=%s run_id=%s batch_id=%s fallback=artifact_dir error=%s",
            symbol,
            run_id,
            batch_id,
            exc,
        )
        _record_db_issue(operation="load_training_run", symbol=symbol, reason=f"registry_lookup_failed:{type(exc).__name__}")
        selected_run = None
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

    sym_dir = artifacts_dir / batch_id / symbol if batch_id is not None else artifacts_dir / symbol
    return sym_dir / "best.ckpt", sym_dir / "scaler.pkl", sym_dir / "config.json", run_id


def _check_feature_contract(cfg_data: dict, *, symbol: str, config_path: Path) -> str | None:
    data_cfg = cfg_data.get("data") or {}
    try:
        reason = validate_feature_contract(
            cfg_data.get("feature_contract"),
            include_sentiment=bool(data_cfg.get("include_sentiment_features", False)),
            feature_set=str(data_cfg.get("feature_set", "v1")),
            include_cross_sectional=bool(data_cfg.get("enable_cross_sectional_features", False)),
            include_screener_scores=bool(data_cfg.get("include_screener_scores", False)),
            include_short_score=bool(data_cfg.get("include_short_score_features", False)),
            persisted_feature_columns=cfg_data.get("feature_columns"),
            persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
            allow_legacy_missing_contract=False,
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
def _cached_tabular_model(model_path_str: str, cache_token: tuple[int, int], selected_model: str) -> Any:
    return _load_tabular_model(Path(model_path_str), selected_model=selected_model)


@lru_cache(maxsize=128)
def _cached_scaler(scaler_path_str: str, cache_token: tuple[int, int]) -> Any:
    with open(scaler_path_str, "rb") as fh:
        return FeatureScaler.from_state_dict(pickle.load(fh))


@lru_cache(maxsize=128)
def _cached_calibrator(calibrator_path_str: str, cache_token: tuple[int, int]) -> Any:
    with open(calibrator_path_str, "rb") as fh:
        return calibrator_from_state_dict(pickle.load(fh))


@lru_cache(maxsize=64)
def _cached_lstm_module(ckpt_path_str: str, cache_token: tuple[int, int], device_str: str) -> Any:
    import torch as _torch
    device_obj = _torch.device(device_str)
    module = LSTMAttentionModule.load_from_checkpoint(ckpt_path_str, map_location=device_obj)
    module.to(device_obj)
    module.eval()
    return module


def _safe_cache_token(path: Path) -> tuple[int, int]:
    try:
        stat_result = path.stat()
        return int(stat_result.st_mtime_ns), int(stat_result.st_size)
    except OSError:
        return 0, 0


def load_tabular_model_cached(model_path: Path, *, selected_model: str) -> Any:
    """API publique du cache (Phase 4.2.d)."""
    return _cached_tabular_model(str(model_path.resolve()), _safe_cache_token(model_path), selected_model)


def load_scaler_cached(scaler_path: Path) -> Any:
    return _cached_scaler(str(scaler_path.resolve()), _safe_cache_token(scaler_path))


def load_calibrator_cached(calibrator_path: Path) -> Any:
    return _cached_calibrator(str(calibrator_path.resolve()), _safe_cache_token(calibrator_path))


def load_lstm_module_cached(ckpt_path: Path, device: Any) -> Any:
    return _cached_lstm_module(str(ckpt_path.resolve()), _safe_cache_token(ckpt_path), str(device))


def clear_model_cache() -> None:
    """Vide tous les caches LRU de modèles/scalers/calibrators (Phase 4.2.d)."""
    _cached_tabular_model.cache_clear()
    _cached_scaler.cache_clear()
    _cached_calibrator.cache_clear()
    _cached_lstm_module.cache_clear()


def clear_prediction_data_cache() -> None:
    """Vide le cache des données immuables réutilisées entre symboles."""
    with _benchmark_frame_cache_lock:
        _benchmark_frame_cache.clear()
    with _cross_sectional_frame_cache_lock:
        _cross_sectional_frame_cache.clear()


def _load_benchmark_bars_cached(
    engine: "Engine",  # type: ignore[name-defined]
    benchmark_symbol: str,
    *,
    cutoff_date: date | None,
) -> pd.DataFrame:
    """Charge une fois les barres benchmark par cutoff pour tout un batch.

    Les prédictions LSTM sont servies symbole par symbole. Sans ce cache, les
    mêmes barres SPY sont lues depuis SQL pour chaque symbole. Une copie
    défensive est toujours rendue car ``compute_features`` peut enrichir son
    entrée.
    """
    cache_key = (id(engine), benchmark_symbol.upper(), cutoff_date.isoformat() if cutoff_date else None)
    with _benchmark_frame_cache_lock:
        cached = _benchmark_frame_cache.get(cache_key)
        if cached is not None:
            _benchmark_frame_cache.move_to_end(cache_key)
            return cached.copy(deep=True)

        benchmark_frame = load_benchmark_bars(engine, benchmark_symbol, end_date=cutoff_date)
        _benchmark_frame_cache[cache_key] = benchmark_frame.copy(deep=True)
        _benchmark_frame_cache.move_to_end(cache_key)
        while len(_benchmark_frame_cache) > _BENCHMARK_FRAME_CACHE_MAX_ENTRIES:
            _benchmark_frame_cache.popitem(last=False)
        return benchmark_frame.copy(deep=True)

def _load_cross_sectional_features_cached(
    engine: "Engine",  # type: ignore[name-defined]
    *,
    required_symbol: str,
    cutoff_date: date | None,
    benchmark_symbol: str,
    benchmark_df: pd.DataFrame | None,
    min_universe_size: int,
) -> pd.DataFrame:
    """Construit une fois le snapshot cross-sectionnel PIT d'une séance.

    Les rangs cross-sectionnels sont identiques quel que soit le symbole servi
    à une même date. Le cache évite donc de recharger l'univers complet et de
    recalculer ses rangs pour chaque ``predict_symbol``. La clé inclut le
    cutoff, le benchmark et le seuil de l'univers, ce qui préserve le contrat
    PIT et sépare les configurations pouvant produire des rangs différents.
    """
    cache_key: tuple[object, ...] = (
        id(engine),
        cutoff_date.isoformat() if cutoff_date else None,
        benchmark_symbol.upper(),
        int(min_universe_size),
    )
    with _cross_sectional_frame_cache_lock:
        cached = _cross_sectional_frame_cache.get(cache_key)
        if cached is not None and required_symbol in set(cached.get("symbol", pd.Series(dtype=str)).astype(str)):
            _cross_sectional_frame_cache.move_to_end(cache_key)
            return cached.copy(deep=True)

        universe_symbols = load_tradable_universe_symbols(engine, trade_date=cutoff_date)
        if required_symbol not in universe_symbols:
            cache_key = (*cache_key, required_symbol.upper())
            cached = _cross_sectional_frame_cache.get(cache_key)
            if cached is not None:
                _cross_sectional_frame_cache.move_to_end(cache_key)
                return cached.copy(deep=True)
        if required_symbol not in universe_symbols:
            universe_symbols.append(required_symbol)
        universe_df = load_universe_bars(engine, universe_symbols, end_date=cutoff_date)
        cross_sectional_df, _ = build_cross_sectional_features(
            universe_df,
            benchmark_df=benchmark_df,
            min_universe_size=min_universe_size,
        )
        _cross_sectional_frame_cache[cache_key] = cross_sectional_df.copy(deep=True)
        _cross_sectional_frame_cache.move_to_end(cache_key)
        while len(_cross_sectional_frame_cache) > _CROSS_SECTIONAL_FRAME_CACHE_MAX_ENTRIES:
            _cross_sectional_frame_cache.popitem(last=False)
        return cross_sectional_df.copy(deep=True)


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
    routed_ckpt = _path_from_value(lstm_route.get("checkpoint_path")) or ckpt_path
    routed_scaler = _path_from_value(lstm_route.get("scaler_path")) or scaler_path
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
        include_screener_scores=cfg_data["data"].get("include_screener_scores", False),
        include_short_score_features=cfg_data["data"].get("include_short_score_features", False),
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
    include_global_stacking: bool = False,
) -> pd.DataFrame:
    """Prépare le DataFrame de features pour un symbole.

    Sprint Maître 2 : ajout de la validation PIT (pas de donnée future).
    """
    try:
        bars = load_symbol_bars(engine, symbol, end_date=cutoff_date)
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("predict_symbol db_read_failed symbol=%s stage=load_symbol_bars error=%s", symbol, exc)
        _record_db_issue(operation="load_symbol_bars", symbol=symbol, reason=f"db_read_failed:{type(exc).__name__}")
        return pd.DataFrame()
    if len(bars) < data_cfg.sequence_length + 60:
        LOGGER.warning("predict_symbol insufficient_bars symbol=%s", symbol)
        return pd.DataFrame()

    # ── Sprint Maître 2 : validation PIT ───────────────────────────────
    _pit_validate_bars(bars, symbol=symbol, cutoff_date=cutoff_date)

    sentiment_df = None
    if data_cfg.include_sentiment_features:
        try:
            sentiment_df = load_symbol_sentiment(engine, symbol, end_date=cutoff_date)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("predict_symbol db_read_failed symbol=%s stage=load_symbol_sentiment error=%s", symbol, exc)
            _record_db_issue(operation="load_symbol_sentiment", symbol=symbol, reason=f"db_read_failed:{type(exc).__name__}")
            return pd.DataFrame()
    benchmark_df = None
    if data_cfg.feature_set == "expert" or data_cfg.enable_cross_sectional_features:
        try:
            benchmark_df = _load_benchmark_bars_cached(
                engine,
                data_cfg.benchmark_symbol,
                cutoff_date=cutoff_date,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("predict_symbol db_read_failed symbol=%s stage=load_benchmark_bars error=%s", symbol, exc)
            _record_db_issue(operation="load_benchmark_bars", symbol=symbol, reason=f"db_read_failed:{type(exc).__name__}")
            return pd.DataFrame()
    selector_df = None
    if data_cfg.include_screener_scores or data_cfg.include_short_score_features:
        try:
            selector_df = load_symbol_selector_context(engine, symbol, end_date=cutoff_date)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("predict_symbol db_read_failed symbol=%s stage=load_symbol_selector_context error=%s", symbol, exc)
            _record_db_issue(operation="load_symbol_selector_context", symbol=symbol, reason=f"db_read_failed:{type(exc).__name__}")
            return pd.DataFrame()
    try:
        df = compute_features(
            bars,
            sentiment_df=sentiment_df,
            include_sentiment=data_cfg.include_sentiment_features,
            benchmark_df=benchmark_df,
            feature_set=data_cfg.feature_set,
            selector_df=selector_df,
            include_screener_scores=data_cfg.include_screener_scores,
            include_short_score=data_cfg.include_short_score_features,
            include_macro_vix=data_cfg.include_macro_vix_features,
            include_macro_vxn=data_cfg.include_macro_vxn_features,
            include_macro_vix3m=data_cfg.include_macro_vix3m_features,
            include_macro_move=data_cfg.include_macro_move_features,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("predict_symbol feature_build_failed symbol=%s error=%s", symbol, exc)
        _record_db_issue(operation="compute_features", symbol=symbol, reason=f"feature_build_failed:{type(exc).__name__}")
        return pd.DataFrame()
    if data_cfg.enable_cross_sectional_features:
        try:
            cross_sectional_df = _load_cross_sectional_features_cached(
                engine,
                required_symbol=symbol,
                cutoff_date=cutoff_date,
                benchmark_symbol=data_cfg.benchmark_symbol,
                benchmark_df=benchmark_df,
                min_universe_size=data_cfg.cross_sectional_min_universe,
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("predict_symbol db_read_failed symbol=%s stage=load_cross_sectional_inputs error=%s", symbol, exc)
            _record_db_issue(operation="load_universe_bars", symbol=symbol, reason=f"db_read_failed:{type(exc).__name__}")
            return pd.DataFrame()
        try:
            df = merge_cross_sectional_features(df, cross_sectional_df)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("predict_symbol feature_build_failed symbol=%s stage=cross_sectional error=%s", symbol, exc)
            _record_db_issue(operation="build_cross_sectional_features", symbol=symbol, reason=f"feature_build_failed:{type(exc).__name__}")
            return pd.DataFrame()
        active_features = get_feature_columns(
            data_cfg.include_sentiment_features,
            feature_set=data_cfg.feature_set,
            include_cross_sectional=True,
            include_screener_scores=data_cfg.include_screener_scores,
            include_short_score=data_cfg.include_short_score_features,
            include_macro_vix=data_cfg.include_macro_vix_features,
            include_macro_vxn=data_cfg.include_macro_vxn_features,
            include_macro_vix3m=data_cfg.include_macro_vix3m_features,
            include_macro_move=data_cfg.include_macro_move_features,
            include_global_stacking=include_global_stacking,
        )
        # ── Fallback global_rank : si attendu mais absent → chercher dans le cache ──
        if include_global_stacking and "global_rank" not in df.columns and "global_rank_3" not in df.columns:
            _cache_key = str(cutoff_date) if cutoff_date else "__today__"
            _cached = _global_rank_prediction_cache.get(_cache_key)
            if _cached is not None and not _cached.empty:
                # Merger toutes les colonnes global_rank* depuis le cache
                _rank_cols = [c for c in _cached.columns if c.startswith("global_rank")]
                if _rank_cols:
                    df = df.merge(
                        _cached[["symbol", "date"] + _rank_cols],
                        on=["symbol", "date"], how="left",
                    )
                for _rc in _rank_cols:
                    if _rc not in df.columns or df[_rc].isna().all():
                        df[_rc] = 0.5
                if all(df.get(rc, pd.Series(0.5)).isna().all() for rc in _rank_cols):
                    _global_rank_fallback_symbols.append(symbol)
            else:
                LOGGER.warning(
                    "predict_symbol global_rank missing for %s, filling with 0.5 (neutral)",
                    symbol,
                )
                df["global_rank"] = 0.5
                _global_rank_fallback_symbols.append(symbol)
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
    _stacking = bool(
        cfg_data.get("global_model", {}).get("stacking_enabled", False)
    )
    cutoff_date = as_of_date or prediction_date
    df = _prepare_prediction_frame(
        symbol, data_cfg=data_cfg, engine=engine, cutoff_date=cutoff_date,
        include_global_stacking=_stacking,
    )
    resolved_feature_columns = list(feature_columns or cfg_data.get("feature_columns") or get_feature_columns(
        data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
        include_screener_scores=data_cfg.include_screener_scores,
        include_short_score=data_cfg.include_short_score_features,
        include_macro_vix=data_cfg.include_macro_vix_features,
        include_macro_vxn=data_cfg.include_macro_vxn_features,
        include_macro_vix3m=data_cfg.include_macro_vix3m_features,
        include_macro_move=data_cfg.include_macro_move_features,
        include_global_stacking=_stacking,
    ))
    if df.empty or len(df) == 0:
        return None
    if not _has_matching_latest_feature_date(df, cutoff_date):
        LOGGER.warning(
            "predict_symbol stale_feature_row symbol=%s selected_model=%s cutoff_date=%s last_feature_date=%s",
            symbol,
            selected_model,
            cutoff_date,
            pd.Timestamp(df["date"].iloc[-1]).date() if "date" in df.columns and not df.empty else None,
        )
        return None
    last_row = df.tail(1)
    contract_reason = validate_feature_contract(
        route_feature_contract if isinstance(route_feature_contract, dict) else cfg_data.get("feature_contract"),
        include_sentiment=data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
        include_screener_scores=data_cfg.include_screener_scores,
        include_short_score=data_cfg.include_short_score_features,
        persisted_feature_columns=cfg_data.get("feature_columns"),
        persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
        route_feature_columns=resolved_feature_columns,
        route_feature_fingerprint=route_feature_fingerprint,
        runtime_feature_columns=list(last_row.columns),
        allow_legacy_missing_contract=False,
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
    last_row_values = last_row[resolved_feature_columns].to_numpy(dtype=np.float64, copy=False)
    if not np.isfinite(last_row_values).all():
        LOGGER.warning(
            "predict_symbol non_finite_runtime_features symbol=%s selected_model=%s cutoff_date=%s",
            symbol,
            selected_model,
            cutoff_date,
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
    try:
        prediction_output = model.predict_proba(last_row[resolved_feature_columns])
        raw_proba = _extract_positive_class_probability(
            prediction_output,
            symbol=symbol,
            selected_model=selected_model,
            model_path=model_path,
            target_mode=data_cfg.target_mode,
        )
        # ── Ternaire tabulaire (P2 2026-06-30) ──────────────────────
        # Les challengers LightGBM / CatBoost entraînés en ternaire
        # produisent 3 colonnes [short, flat, long] → on extrait les
        # 3 probas pour les persister dans model_predictions.
        proba_all = np.asarray(prediction_output, dtype=float)
        is_ternary_tab = (
            data_cfg.target_mode == "ternary"
            and proba_all.ndim == 2
            and proba_all.shape[1] >= 3
        )
        if is_ternary_tab:
            proba_short_val: float | None = float(proba_all[0, 0])
            proba_flat_val: float | None = float(proba_all[0, 1])
            proba_long_val: float | None = float(proba_all[0, 2])
        else:
            proba_short_val = None
            proba_flat_val = None
            proba_long_val = None
    except ArtifactIntegrityError:
        raise
    except Exception as exc:  # noqa: BLE001
        reason = f"tabular_model_incompatible:{selected_model}"
        LOGGER.error(
            "predict_symbol %s symbol=%s path=%s error=%s",
            reason,
            symbol,
            model_path,
            exc,
        )
        _record_artifact_issue(symbol, reason=reason, path=model_path)
        raise ArtifactIntegrityError(reason, path=model_path) from exc
    if not np.isfinite(raw_proba):
        LOGGER.warning(
            "predict_symbol non_finite_raw_proba symbol=%s selected_model=%s cutoff_date=%s",
            symbol,
            selected_model,
            cutoff_date,
        )
        return None
    calibrator = _load_optional_calibrator(calibrator_path, symbol=symbol, selected_model=selected_model)
    eps = 1e-6
    margin = np.array([
        np.log(np.clip(raw_proba, eps, 1 - eps) / np.clip(1 - raw_proba, eps, 1 - eps))
    ], dtype=np.float64)
    proba, calibration_method = _apply_optional_calibration(
        symbol=symbol,
        selected_model=selected_model,
        calibrator=calibrator,
        margin=margin,
        calibrator_path=calibrator_path,
        raw_proba=raw_proba,
    )
    if not np.isfinite(proba):
        LOGGER.warning(
            "predict_symbol non_finite_calibrated_proba symbol=%s selected_model=%s cutoff_date=%s",
            symbol,
            selected_model,
            cutoff_date,
        )
        return None
    threshold_value = decision_threshold if decision_threshold is not None else cfg_data.get("selected_decision_threshold", data_cfg.decision_threshold)
    effective_threshold = _numeric_threshold(threshold_value, float(data_cfg.decision_threshold or 0.5))
    pred_date = prediction_date or date.today()

    # ── Ternaire tabulaire : side + signal via policy partagée (Sprint Maître 0) ─
    if is_ternary_tab:
        if (
            calibrator is not None
            and getattr(calibrator, "method", None) == "temperature"
            and getattr(calibrator, "fitted", False)
        ):
            try:
                logits = np.log(np.clip(proba_all[:, :3], eps, 1.0))
                calibrated = calibrator.predict(logits)
                proba_short_val = float(calibrated[0, 0])
                proba_flat_val = float(calibrated[0, 1])
                proba_long_val = float(calibrated[0, 2])
                calibration_method = "temperature"
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "predict_symbol ternary_temperature_fallback symbol=%s selected_model=%s error=%s",
                    symbol,
                    selected_model,
                    exc,
                )
                calibration_method = "none"

        p_short = proba_short_val or 0.0
        p_flat = proba_flat_val or 0.0
        p_long = proba_long_val or 0.0
        try:
            # ── Sprint Maître 0 : décision via la policy partagée ─
            decision = decide_ternary_side(
                proba_short=p_short,
                proba_flat=p_flat,
                proba_long=p_long,
            )
            predicted_side_val: str | None = decision.side
            pred_class = 1 if decision.side == "long" else 0
            signal_label = decision.side
            proba = decision.p_side
            decision_reason = decision.reason
        except ValueError as exc:
            LOGGER.warning(
                "predict_symbol ternary_decision_invalid symbol=%s selected_model=%s error=%s",
                symbol, selected_model, exc,
            )
            return None
    else:
        pred_class = 1 if proba >= effective_threshold else 0
        signal_label = "long" if pred_class == 1 else "no_trade"
        predicted_side_val = None
        decision_reason = None

    # ── Sprint Maître 2 : disponibilité PIT ───────────────────────────
    pit_avail = _pit_build_availability(df, symbol=symbol, cutoff_date=cutoff_date)

    result = _build_prediction_result(
        symbol=symbol,
        prediction_date=pred_date,
        proba=proba,
        pred_class=pred_class,
        run_id=str(cfg_data.get("run_id", cfg_data.get("artifact_symbol", selected_model))),
        raw_proba=raw_proba,
        decision_threshold=effective_threshold,
        signal_label=signal_label,
        calibration_method=calibration_method,
        selected_model=selected_model,
        predicted_side=predicted_side_val,
        proba_long=proba_long_val,
        proba_flat=proba_flat_val,
        proba_short=proba_short_val,
        decision_reason=decision_reason,
        data_availability=pit_avail,
        data_quality=QualityState.PRESENT if pit_avail is not None else QualityState.MISSING_NO_SOURCE,
    )
    update_runtime_status(
        last_prediction_symbol=symbol,
        last_requested_model=selected_model,
        last_served_model=selected_model,
        last_decision_threshold=effective_threshold,
        last_calibration_method=calibration_method,
        last_prediction_date=pred_date.isoformat(),
    )
    if persist:
        _persist_predictions_best_effort(engine, result, symbol=symbol)
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
    batch_id: Optional[str] = None,
    as_of_date: Optional[date] = None,
    persist: bool = True,
    accelerator: str = "auto",
) -> Optional[pd.DataFrame]:
    """Charge le modèle et produit une prédiction pour un symbole.

    Returns:
        DataFrame avec colonnes: symbol, prediction_date, predicted_proba, predicted_class, run_id
        ou None si artefacts manquants.
    """
    ckpt_path, scaler_path, config_path, selected_run_id = _resolve_artifact_paths(
        symbol,
        artifacts_dir,
        engine,
        run_id,
        batch_id=batch_id,
    )

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

    # ── Sprint Maître 0 : blocage research_only ─────────────────────────
    if cfg_data.get("research_only") is True:
        LOGGER.warning(
            "predict_symbol blocked_research_only symbol=%s config=%s",
            symbol, config_path,
        )
        _record_artifact_issue(symbol, reason="research_only_blocked", path=config_path)
        return None

    fingerprint_reason = _check_feature_contract(cfg_data, symbol=symbol, config_path=config_path)
    if fingerprint_reason is not None:
        LOGGER.error("predict_symbol aborted symbol=%s reason=%s", symbol, fingerprint_reason)
        return None

    route = _resolve_selected_model_route(cfg_data, ckpt_path, scaler_path, config_path)
    manifest_path = _resolve_artifact_signature_manifest_path(cfg_data, config_path=config_path)
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
                _verify_route_signature_if_needed(
                    cfg_data=cfg_data,
                    route=route,
                    manifest_path=manifest_path,
                    symbol=symbol,
                )
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
                _verify_route_signature_if_needed(
                    cfg_data=cfg_data,
                    route=route,
                    manifest_path=manifest_path,
                    symbol=symbol,
                )
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
                    feature_columns=list(route.get("feature_columns")) if isinstance(route.get("feature_columns"), list) else [],
                    decision_threshold=_resolve_route_decision_threshold(route, cfg_data),
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

    _record_route_fallback_if_any(symbol, route)
    try:
        _verify_route_signature_if_needed(
            cfg_data=cfg_data,
            route=route,
            manifest_path=manifest_path,
            symbol=symbol,
        )
    except ArtifactIntegrityError:
        return None

    ckpt_path = _path_from_value(route.get("checkpoint_path"))
    scaler_path = _path_from_value(route.get("scaler_path"))
    if ckpt_path is None or scaler_path is None:
        LOGGER.warning("predict_symbol routed_artifacts_unresolved symbol=%s selected_model=%s", symbol, selected_architecture)
        _record_artifact_issue(symbol, reason=f"lstm_route_unresolved:{selected_architecture}", path=manifest_path)
        return None
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
    calibrator_path = _path_from_value(calibrator_path_raw) or config_path.with_name("calibrator.pkl")
    calibrator = _load_optional_calibrator(calibrator_path, symbol=symbol, selected_model=selected_architecture)

    cutoff_date = as_of_date or prediction_date
    _stacking = bool(
        cfg_data.get("global_model", {}).get("stacking_enabled", False)
    )
    df = _prepare_prediction_frame(
        symbol, data_cfg=data_cfg, engine=engine, cutoff_date=cutoff_date,
        include_global_stacking=_stacking,
    )
    if len(df) < data_cfg.sequence_length:
        LOGGER.warning("predict_symbol insufficient_sequences symbol=%s rows=%d required=%d", symbol, len(df), data_cfg.sequence_length)
        return None
    if not _has_matching_latest_feature_date(df, cutoff_date):
        LOGGER.warning(
            "predict_symbol stale_feature_row symbol=%s selected_model=%s cutoff_date=%s last_feature_date=%s",
            symbol,
            selected_architecture,
            cutoff_date,
            pd.Timestamp(df["date"].iloc[-1]).date() if "date" in df.columns and not df.empty else None,
        )
        return None

    contract_reason = validate_feature_contract(
        cfg_data.get("feature_contract"),
        include_sentiment=data_cfg.include_sentiment_features,
        feature_set=data_cfg.feature_set,
        include_cross_sectional=data_cfg.enable_cross_sectional_features,
        include_screener_scores=data_cfg.include_screener_scores,
        include_short_score=data_cfg.include_short_score_features,
        persisted_feature_columns=cfg_data.get("feature_columns"),
        persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
        scaler_feature_names=list(getattr(scaler, "feature_names", [])),
        route_feature_columns=route.get("feature_columns"),
        route_feature_fingerprint=route.get("feature_fingerprint"),
        runtime_feature_columns=list(df.columns),
        allow_legacy_missing_contract=False,
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
    if not np.isfinite(features).all():
        LOGGER.warning(
            "predict_symbol non_finite_runtime_features symbol=%s selected_model=%s cutoff_date=%s",
            symbol,
            selected_architecture,
            cutoff_date,
        )
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
        try:
            logits, _ = model(x)
            logits_tensor = torch.as_tensor(logits)
            if logits_tensor.ndim != 2 or logits_tensor.shape[0] < 1 or logits_tensor.shape[1] < 2:
                raise ValueError(f"invalid_logits_shape={tuple(logits_tensor.shape)}")
            num_classes = logits_tensor.shape[1]
            probs_all = torch.softmax(logits_tensor, dim=1)[0]  # [C]
            is_ternary = num_classes == 3 or data_cfg.target_mode == "ternary"
            if is_ternary and num_classes >= 3:
                # Ternaire : classe 0=short, 1=flat, 2=long (apres label shift)
                proba_long_val = probs_all[2].item()
                proba_flat_val = probs_all[1].item()
                proba_short_val = probs_all[0].item()
                raw_proba = proba_long_val  # pour compatibilite binaire
            else:
                # Binaire : colonne 1 = classe positive (long)
                raw_proba = probs_all[1].item()
                proba_long_val = None
                proba_flat_val = None
                proba_short_val = None
        except Exception as exc:  # noqa: BLE001
            reason = f"lstm_runtime_incompatible:{selected_architecture}"
            LOGGER.error("predict_symbol %s symbol=%s path=%s error=%s", reason, symbol, ckpt_path, exc)
            _record_artifact_issue(symbol, reason=reason, path=ckpt_path)
            return None
    if not np.isfinite(raw_proba):
        LOGGER.warning(
            "predict_symbol non_finite_raw_proba symbol=%s selected_model=%s cutoff_date=%s",
            symbol,
            selected_architecture,
            cutoff_date,
        )
        return None

    proba, calibration_method = _apply_optional_calibration(
        symbol=symbol,
        selected_model=selected_architecture,
        calibrator=calibrator,
        margin=margin_from_logits(logits_tensor.detach().cpu().numpy()),
        calibrator_path=calibrator_path,
        raw_proba=raw_proba,
    )
    if not np.isfinite(proba):
        LOGGER.warning(
            "predict_symbol non_finite_calibrated_proba symbol=%s selected_model=%s cutoff_date=%s",
            symbol,
            selected_architecture,
            cutoff_date,
        )
        return None

    # ── Temperature Scaling ternaire (2026-06-25) ────────────────
    # Si un TemperatureScaler est disponible, recalibrer TOUTES les
    # probas ternaires (pas seulement proba_long).
    calibrated_ternary_probs: dict[str, float | None] = {
        "proba_short": proba_short_val,
        "proba_flat": proba_flat_val,
        "proba_long": proba_long_val,
    }
    if (
        is_ternary
        and num_classes >= 3
        and calibrator is not None
        and getattr(calibrator, "method", None) == "temperature"
        and getattr(calibrator, "fitted", False)
    ):
        try:
            cal_probs = calibrator.predict(logits_tensor.detach().cpu().numpy())
            # cal_probs: [1, 3] → extraire les 3 probas
            calibrated_ternary_probs["proba_short"] = float(cal_probs[0, 0])
            calibrated_ternary_probs["proba_flat"] = float(cal_probs[0, 1])
            calibrated_ternary_probs["proba_long"] = float(cal_probs[0, 2])
            proba = calibrated_ternary_probs["proba_long"]
            calibration_method = "temperature"
            LOGGER.debug(
                "Temperature scaling applied symbol=%s T=%.3f short=%.3f flat=%.3f long=%.3f",
                symbol,
                getattr(calibrator, "temperature", 1.0),
                calibrated_ternary_probs["proba_short"],
                calibrated_ternary_probs["proba_flat"],
                calibrated_ternary_probs["proba_long"],
            )
        except Exception as _exc:
            LOGGER.warning("Temperature scaling failed symbol=%s: %s", symbol, _exc)

    pred_date = prediction_date or date.today()
    if is_ternary and num_classes >= 3:
        # Le chemin LSTM consomme la même policy que les backends tabulaires.
        cal_short = calibrated_ternary_probs.get("proba_short", 0.0) or 0.0
        cal_flat = calibrated_ternary_probs.get("proba_flat", 0.0) or 0.0
        cal_long = calibrated_ternary_probs.get("proba_long", 0.0) or 0.0
        try:
            ternary_decision = decide_ternary_side(
                proba_short=cal_short,
                proba_flat=cal_flat,
                proba_long=cal_long,
            )
        except ValueError as exc:
            LOGGER.warning(
                "predict_symbol ternary_decision_invalid symbol=%s selected_model=%s error=%s",
                symbol,
                selected_architecture,
                exc,
            )
            return None
        predicted_side_val = ternary_decision.side
        pred_class = 1 if predicted_side_val == "long" else 0
        signal_label = predicted_side_val
        proba = ternary_decision.p_side
        proba_long_val = cal_long
        proba_flat_val = cal_flat
        proba_short_val = cal_short
    else:
        pred_class = 1 if proba >= data_cfg.decision_threshold else 0
        signal_label = "long" if pred_class == 1 else "no_trade"
        predicted_side_val = None

    result = _build_prediction_result(
        symbol=symbol,
        prediction_date=pred_date,
        proba=proba,
        pred_class=pred_class,
        run_id=str(run_id),
        raw_proba=raw_proba,
        decision_threshold=float(data_cfg.decision_threshold),
        signal_label=signal_label,
        calibration_method=calibration_method,
        selected_model=selected_architecture,
        predicted_side=predicted_side_val,
        proba_long=proba_long_val,
        proba_flat=proba_flat_val,
        proba_short=proba_short_val,
    )
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
        _persist_predictions_best_effort(engine, result, symbol=symbol)
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


# ────────────────────────────────────────────────────────────────────
# Global Rank helpers (stacking à l'inférence)
# ────────────────────────────────────────────────────────────────────

def _try_compute_global_rank_for_prediction(
    artifacts_dir: Path,
    engine: Any,
    prediction_date: date | None,
) -> None:
    """Tente de pré-calculer le ``global_rank`` pour la date de prédiction.

    Si le modèle global est disponible dans ``artifacts_dir``, l'exécute
    sur l'univers du jour et stocke le résultat dans le cache module.
    Sinon, le fallback (0.5) sera utilisé par symbole.
    """
    global _global_rank_prediction_cache
    _cache_key = str(prediction_date) if prediction_date else "__today__"
    if _cache_key in _global_rank_prediction_cache:
        return  # déjà calculé

    # Vérifier que le modèle global existe
    _features_path = artifacts_dir / "_global_ranking_features.json"
    if not _features_path.exists():
        LOGGER.info("_try_compute_global_rank: no model found, will use fallback 0.5")
        _global_rank_prediction_cache[_cache_key] = None
        return

    try:
        from modelFactory.global_ranking import predict_global_rank
        from modelFactory.data_loader import load_universe_bars, load_tradable_universe_symbols
    except ImportError:
        _global_rank_prediction_cache[_cache_key] = None
        return

    try:
        universe_symbols = load_tradable_universe_symbols(engine, trade_date=prediction_date)
        if not universe_symbols:
            LOGGER.warning("_try_compute_global_rank: empty universe, skip")
            _global_rank_prediction_cache[_cache_key] = None
            return
        # Charger N jours d'historique (configurable, défaut 365)
        _lookback = 365
        try:
            import yaml as _yaml_gr
            with open("config.yaml", encoding="utf-8") as _fh_gr:
                _cfg_gr = _yaml_gr.safe_load(_fh_gr) or {}
            _lookback = int(
                (_cfg_gr.get("global_ranking") or {}).get("prediction_lookback_days", 365)
            )
        except Exception:
            pass
        from datetime import timedelta as _td
        _start_date = prediction_date - _td(days=_lookback) if prediction_date else None
        universe_df = load_universe_bars(
            engine, universe_symbols,
            end_date=prediction_date,
            start_date=_start_date,
        )
        if universe_df.empty:
            LOGGER.warning("_try_compute_global_rank: empty universe bars, skip")
            _global_rank_prediction_cache[_cache_key] = None
            return

        rank_df = predict_global_rank(universe_df, artifacts_dir)
        if rank_df is not None and not rank_df.empty:
            _global_rank_prediction_cache[_cache_key] = rank_df
            LOGGER.info(
                "_try_compute_global_rank: computed for %d symbols on %s",
                len(rank_df), _cache_key,
            )
        else:
            LOGGER.warning("_try_compute_global_rank: predict_global_rank returned None")
            _global_rank_prediction_cache[_cache_key] = None
    except Exception as exc:
        LOGGER.warning("_try_compute_global_rank: failed: %s", exc)
        _global_rank_prediction_cache[_cache_key] = None


def _warn_global_rank_fallbacks() -> None:
    """Log un avertissement si des symboles ont utilisé le fallback global_rank=0.5."""
    global _global_rank_fallback_symbols
    if _global_rank_fallback_symbols:
        _unique = sorted(set(_global_rank_fallback_symbols))
        LOGGER.warning(
            "⚠️ GLOBAL_RANK FALLBACK: %d symbol(s) used neutral global_rank=0.5 "
            "(global model unavailable or failed): %s",
            len(_unique),
            ", ".join(_unique[:20]) + ("..." if len(_unique) > 20 else ""),
        )
        _global_rank_fallback_symbols.clear()


def predict_batch(
    symbols: list[str],
    artifacts_dir: Path,
    engine: "Engine",  # type: ignore[name-defined]
    prediction_date: Optional[date] = None,
    batch_id: Optional[str] = None,
    as_of_date: Optional[date] = None,
    persist: bool = True,
    accelerator: str = "auto",
    max_workers: int = 1,
) -> pd.DataFrame:
    """Exécute les prédictions pour une liste de symboles.

    Parameters
    ----------
    max_workers : int
        Nombre de workers parallèles (ThreadPoolExecutor). 1 = séquentiel.
        Au-dessus de 1, les updates runtime par symbole sont désactivées
        (non thread-safe) et seul un résumé final est émis.
    """
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

    # ── Pré-calcul du global_rank pour stacking (si activé) ──
    _try_compute_global_rank_for_prediction(artifacts_dir, engine, prediction_date)

    if max_workers <= 1:
        # ── Chemin séquentiel (comportement historique) ──────────
        all_preds: list[pd.DataFrame] = []
        completed = 0
        skipped = 0
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
                batch_id=batch_id,
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
        _warn_global_rank_fallbacks()
        if all_preds:
            return pd.concat(all_preds, ignore_index=True)
        return pd.DataFrame(columns=["symbol", "prediction_date", "predicted_proba", "predicted_class", "run_id"])

    # ── Chemin parallèle (ThreadPoolExecutor) ─────────────────────
    from concurrent.futures import ThreadPoolExecutor, as_completed

    LOGGER.info("predict_batch parallel start symbols=%d workers=%d", total, max_workers)
    all_preds: list[pd.DataFrame] = []
    completed = 0
    skipped = 0

    def _predict_one(sym: str) -> tuple[str, pd.DataFrame | None]:
        """Wrapper thread-safe : chaque thread utilise sa propre connexion DB."""
        pred = predict_symbol(
            sym,
            artifacts_dir,
            engine,
            prediction_date,
            batch_id=batch_id,
            as_of_date=as_of_date,
            persist=persist,
            accelerator=accelerator,
        )
        return sym, pred

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_predict_one, sym): sym for sym in symbols}
        for future in as_completed(future_map):
            sym = future_map[future]
            try:
                _, pred = future.result()
                if pred is not None:
                    all_preds.append(pred)
                    completed += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("predict_batch worker failed symbol=%s error=%s", sym, exc)
                skipped += 1

    update_runtime_status(
        current_phase="predict_batch_completed",
        progress_current=completed + skipped,
        symbols_completed=completed,
        symbols_skipped=skipped,
        symbols_failed=0,
        progress_item=None,
        phase_detail=f"parallel workers={max_workers}",
    )
    LOGGER.info(
        "predict_batch parallel done symbols=%d completed=%d skipped=%d workers=%d",
        total, completed, skipped, max_workers,
    )
    _warn_global_rank_fallbacks()
    if all_preds:
        return pd.concat(all_preds, ignore_index=True)
    return pd.DataFrame(columns=["symbol", "prediction_date", "predicted_proba", "predicted_class", "run_id"])

