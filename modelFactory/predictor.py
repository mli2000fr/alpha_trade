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
# Cache _per_symbol_features.json par artifacts_dir
_per_symbol_features_cache: dict[str, dict[str, Any]] = {}


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
    """Résout les artefacts depuis le registre DB, sinon via le dossier de campagne du symbole.

    P0-2 (2026-08-04) : si aucun artefact per-symbol n'est trouvé, tente le routage
    per-sector (symbol → secteur GICS → modèle sectoriel).
    """
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

    # ── P0-2 : fallback per-sector ──
    sector_run = _resolve_sector_run(engine, symbol, batch_id=batch_id)
    if sector_run is not None:
        ckpt_path = Path(sector_run["checkpoint_path"])
        scaler_path = Path(sector_run["scaler_path"])
        config_path = Path(sector_run["config_path"])
        if ckpt_path.exists() and config_path.exists():
            LOGGER.info(
                "predict_symbol sector_fallback symbol=%s sector=%s run_id=%s",
                symbol, sector_run.get("symbol"), sector_run.get("run_id"),
            )
            return ckpt_path, scaler_path, config_path, str(sector_run["run_id"])
        else:
            LOGGER.error(
                "predict_symbol sector_artifacts_missing symbol=%s sector=%s ckpt=%s config=%s",
                symbol, sector_run.get("symbol"),
                str(ckpt_path) if ckpt_path.exists() else f"MISSING:{ckpt_path}",
                str(config_path) if config_path.exists() else f"MISSING:{config_path}",
            )

    sym_dir = artifacts_dir / batch_id / symbol if batch_id is not None else artifacts_dir / symbol
    LOGGER.error(
        "predict_symbol no_model_found symbol=%s batch=%s — no per-symbol champion, "
        "no per-sector fallback, and no filesystem artifacts at %s",
        symbol, batch_id, sym_dir,
    )
    return sym_dir / "best.ckpt", sym_dir / "scaler.pkl", sym_dir / "config.json", run_id


def _resolve_sector_run(
    engine: "Engine",  # type: ignore[name-defined]
    symbol: str,
    batch_id: str | None = None,
) -> dict | None:
    """Résout le training run du secteur GICS pour un symbole donné.

    Retourne un dict avec les clés nécessaires au fallback tabulaire :
    ``run_id``, ``config_path``, ``checkpoint_path`` (→ model_path).

    P0-2 fix (2026-08-04) : utilise une requête directe qui n'exige pas
    checkpoint_path/scaler_path (absents des runs tabulaires sectoriels).
    """
    try:
        from modelFactory.cross_sectional import _load_sector_mapping, _map_to_gics_sector
        sector_map = _load_sector_mapping(engine)
        if not sector_map:
            return None
        db_sector = sector_map.get(symbol.upper())
        if db_sector is None:
            return None
        gics_sector = _map_to_gics_sector(db_sector)
        # Requête directe : ne pas exiger checkpoint_path/scaler_path
        from sqlalchemy import text
        if batch_id is not None:
            sql = text(
                "SELECT mtr.run_id, mtr.symbol, mtr.config_path, "
                "mg.model_path, mg.model_name "
                "FROM model_training_run mtr "
                "JOIN model_governance mg ON mg.run_id = mtr.run_id "
                "WHERE mtr.symbol = :sym AND mtr.batch_id = :bid "
                "AND mtr.status = 'completed' AND mg.is_selected_model = 1 "
                "ORDER BY mtr.finished_at DESC LIMIT 1"
            )
            params = {"sym": gics_sector, "bid": batch_id}
        else:
            sql = text(
                "SELECT mtr.run_id, mtr.symbol, mtr.config_path, "
                "mg.model_path, mg.model_name "
                "FROM model_training_run mtr "
                "JOIN model_governance mg ON mg.run_id = mtr.run_id "
                "WHERE mtr.symbol = :sym AND mtr.status = 'completed' "
                "AND mg.is_selected_model = 1 "
                "ORDER BY mtr.finished_at DESC LIMIT 1"
            )
            params = {"sym": gics_sector}
        with engine.connect() as conn:
            row = conn.execute(sql, params).mappings().first()
        if row is None:
            return None
        _model_path = row["model_path"] or ""
        # config.json est au niveau du dossier secteur, pas dans h20/lightgbm/
        # Ex: _sector_financials/h20/lightgbm/model.pkl → _sector_financials/config.json
        if row["config_path"]:
            _config_path = str(row["config_path"])
        elif _model_path:
            _model_dir = Path(_model_path).parent  # .../h20/lightgbm
            _sector_dir = _model_dir.parent.parent   # .../ (sector root, 3 levels up from model)
            _config_path = str(_sector_dir / "config.json")
        else:
            _config_path = ""
        return {
            "run_id": row["run_id"],
            "symbol": row["symbol"],
            "config_path": _config_path,
            "checkpoint_path": _model_path,
            "scaler_path": "",
            "model_name": row["model_name"],
        }
    except Exception:
        return None


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
            include_macro_vix=bool(data_cfg.get("include_macro_vix_features", False)),
            include_macro_vxn=bool(data_cfg.get("include_macro_vxn_features", False)),
            include_macro_vix3m=bool(data_cfg.get("include_macro_vix3m_features", False)),
            include_macro_move=bool(data_cfg.get("include_macro_move_features", False)),
            include_global_stacking=bool((cfg_data.get("global_model") or {}).get("stacking_enabled", False)),
            include_fundamentals=bool(data_cfg.get("include_fundamentals_features", False)),
            include_factors=bool(data_cfg.get("include_factors_features", False)),
            include_macro_regime=bool(data_cfg.get("include_macro_regime_features", False)),
            include_score_components=bool(data_cfg.get("include_score_components", False)),
            persisted_feature_columns=cfg_data.get("feature_columns"),
            persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
            allow_legacy_missing_contract=False,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("feature_contract_check_failed symbol=%s error=%s", symbol, exc)
        return f"feature_contract_check_failed:{exc}"
    if reason is not None:
        # P0-4 (2026-08-06) : les modèles entraînés avant le fix de
        # _build_feature_contract_for_columns ont un fingerprint calculé
        # avec des flags incomplets (include_fundamentals, include_factors,
        # include_macro_regime absents). Si SEUL le fingerprint diverge
        # (les colonnes matchent), on downgrade en warning au lieu d'abort.
        if reason.startswith("feature_contract_fingerprint_mismatch"):
            LOGGER.warning(
                "feature_contract_fingerprint_lenient symbol=%s reason=%s "
                "(columns ok, fingerprint mismatch accepted — training contract "
                "built with incomplete flags, fixed in P0-4)",
                symbol, reason,
            )
            return None
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
    """Vide le cache des données immuables réutilisées entre symboles.

    P2-5 fix (2026-08-04) : inclut _global_rank_prediction_cache et
    _per_symbol_features_cache qui n'étaient pas vidés.
    """
    global _global_rank_prediction_cache, _per_symbol_features_cache
    with _benchmark_frame_cache_lock:
        _benchmark_frame_cache.clear()
    with _cross_sectional_frame_cache_lock:
        _cross_sectional_frame_cache.clear()
    _global_rank_prediction_cache.clear()
    _per_symbol_features_cache.clear()


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


def _load_data_cfg_from_payload(
    cfg_data: dict,
    *,
    ps_features: dict[str, Any] | None = None,
) -> DataConfig:
    """Reconstruit DataConfig depuis le config.json du modèle.

    Priorité : ``cfg_data["data"]`` d'abord (config du modèle cible),
    puis ``ps_features`` (``_per_symbol_features.json``) en fallback
    pour les clés absentes du config.json.

    Cela garantit qu'un config per-sector (qui a son propre ``data``
    complet) n'est pas écrasé par les flags per-symbol du batch.
    """
    _primary = cfg_data.get("data", {})
    _fallback = ps_features if ps_features else {}
    return DataConfig(
        sequence_length=_primary["sequence_length"],
        forecast_horizon=_primary["forecast_horizon"],
        include_sentiment_features=_primary.get("include_sentiment_features", _fallback.get("include_sentiment", False)),
        include_screener_scores=_primary.get("include_screener_scores", _fallback.get("include_screener_scores", False)),
        include_short_score_features=_primary.get("include_short_score_features", _fallback.get("include_short_score", False)),
        include_macro_vix_features=_primary.get("include_macro_vix_features", _fallback.get("include_macro_vix", False)),
        include_macro_vxn_features=_primary.get("include_macro_vxn_features", _fallback.get("include_macro_vxn", False)),
        include_macro_vix3m_features=_primary.get("include_macro_vix3m_features", _fallback.get("include_macro_vix3m", False)),
        include_macro_move_features=_primary.get("include_macro_move_features", _fallback.get("include_macro_move", False)),
        include_fundamentals_features=_primary.get("include_fundamentals_features", _fallback.get("include_fundamentals", False)),
        include_factors_features=_primary.get("include_factors_features", _fallback.get("include_factors", False)),
        include_macro_regime_features=_primary.get("include_macro_regime_features", _fallback.get("include_macro_regime", False)),
        include_score_components=_primary.get("include_score_components", _fallback.get("include_score_components", False)),
        enable_cross_sectional_features=_primary.get("enable_cross_sectional_features", _fallback.get("enable_cross_sectional", False)),
        cross_sectional_min_universe=_primary.get("cross_sectional_min_universe", 20),
        feature_set=_primary.get("feature_set", _fallback.get("feature_set", "v1")),
        benchmark_symbol=_primary.get("benchmark_symbol", "SPY"),
        target_mode=_primary.get("target_mode", "binary"),
        target_up_threshold=_primary.get("target_up_threshold", 0.0),
        target_down_threshold=_primary.get("target_down_threshold", 0.0),
        decision_threshold=_primary.get("decision_threshold", cfg_data.get("selected_decision_threshold", 0.5)),
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
            include_fundamentals=data_cfg.include_fundamentals_features,
            include_factors=data_cfg.include_factors_features,
            include_macro_regime=data_cfg.include_macro_regime_features,
            include_score_components=data_cfg.include_score_components,
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
            include_score_components=data_cfg.include_score_components,
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
    ps_features: dict[str, Any] | None = None,
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
        ps_features=ps_features,
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
    ps_features: dict[str, Any] | None = None,
) -> Optional[pd.DataFrame]:
    if not model_path.exists():
        reason = f"tabular_model_missing:{selected_model}"
        LOGGER.error("predict_symbol %s symbol=%s path=%s", reason, symbol, model_path)
        _record_artifact_issue(symbol, reason=reason, path=model_path)
        raise ArtifactIntegrityError(reason, path=model_path)
    data_cfg = _load_data_cfg_from_payload(cfg_data, ps_features=ps_features)
    _stacking = bool(
        (ps_features or {}).get("global_stacking_enabled")
        or cfg_data.get("global_model", {}).get("stacking_enabled", False)
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
        include_fundamentals=data_cfg.include_fundamentals_features,
        include_factors=data_cfg.include_factors_features,
        include_macro_regime=data_cfg.include_macro_regime_features,
        include_score_components=data_cfg.include_score_components,
    ))
    if df.empty or len(df) == 0:
        return None
    # ── P0-3 fix (2026-08-04) : reconstruire pd.Categorical pour "symbol" ──
    _symbol_cats = cfg_data.get("symbol_categories")
    if "symbol" in resolved_feature_columns and "symbol" not in df.columns:
        df["symbol"] = symbol
    if _symbol_cats and "symbol" in df.columns:
        # Inclure le symbole courant s'il n'est pas dans les catégories d'entraînement
        _all_cats = list(dict.fromkeys(list(_symbol_cats) + [symbol]))
        df["symbol"] = pd.Categorical(df["symbol"], categories=_all_cats)
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
        include_macro_vix=data_cfg.include_macro_vix_features,
        include_macro_vxn=data_cfg.include_macro_vxn_features,
        include_macro_vix3m=data_cfg.include_macro_vix3m_features,
        include_macro_move=data_cfg.include_macro_move_features,
        include_global_stacking=bool((cfg_data.get("global_model") or {}).get("stacking_enabled", False)),
        include_fundamentals=data_cfg.include_fundamentals_features,
        include_factors=data_cfg.include_factors_features,
        include_macro_regime=data_cfg.include_macro_regime_features,
        include_score_components=data_cfg.include_score_components,
        persisted_feature_columns=cfg_data.get("feature_columns"),
        persisted_feature_fingerprint=cfg_data.get("feature_fingerprint"),
        route_feature_columns=resolved_feature_columns,
        route_feature_fingerprint=route_feature_fingerprint,
        runtime_feature_columns=list(last_row.columns),
        allow_legacy_missing_contract=False,
    )
    if contract_reason is not None:
        # P0-4 (2026-08-06) : fingerprint mismatch accepté si colonnes OK
        # (contrat entraîné avec flags incomplets dans _build_feature_contract_for_columns)
        if str(contract_reason).startswith("feature_contract_fingerprint_mismatch"):
            LOGGER.warning(
                "predict_symbol feature_contract_fingerprint_lenient symbol=%s selected_model=%s reason=%s",
                symbol, selected_model, contract_reason,
            )
        else:
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
        _record_artifact_issue(symbol, reason=f"missing_columns:{','.join(missing_columns[:5])}", path=config_path)
        return None
    _numeric_cols = [c for c in resolved_feature_columns if c != "symbol"]
    last_row_values = last_row[_numeric_cols].to_numpy(dtype=np.float64, copy=False)
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
        is_tab_regression = data_cfg.target_mode == "regression"
        if is_tab_regression:
            # ── Regression : score continu ──────────────────────────
            prediction_output = model.predict(last_row[resolved_feature_columns])
            raw_proba = float(np.asarray(prediction_output, dtype=float).reshape(-1)[0])
            proba_short_val = None
            proba_flat_val = None
            proba_long_val = None
            is_ternary_tab = False
        else:
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
    elif is_tab_regression:
        # ── Regression : décision basée sur le signe ─────────────────
        if raw_proba > 0:
            pred_class = 1
            signal_label = "long"
            predicted_side_val = "long"
        elif raw_proba < 0:
            pred_class = 0
            signal_label = "short"
            predicted_side_val = "short"
        else:
            pred_class = 0
            signal_label = "no_trade"
            predicted_side_val = None
        decision_reason = None
        proba = raw_proba  # score continu
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
    # ── Charger _per_symbol_features.json (cache par batch, lecture unique) ──
    _ps_features = load_per_symbol_features(artifacts_dir)

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
                    ps_features=_ps_features,
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
                    ps_features=_ps_features,
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

    data_cfg = _load_data_cfg_from_payload(cfg_data, ps_features=_ps_features)
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
        (_ps_features or {}).get("global_stacking_enabled")
        or cfg_data.get("global_model", {}).get("stacking_enabled", False)
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
            num_classes = logits_tensor.shape[1]
            is_regression = num_classes == 1 or data_cfg.target_mode == "regression"
            if logits_tensor.ndim != 2 or logits_tensor.shape[0] < 1 or (not is_regression and logits_tensor.shape[1] < 2):
                raise ValueError(f"invalid_logits_shape={tuple(logits_tensor.shape)}")
            if is_regression:
                # ── Regression : score continu ────────────────────────
                raw_proba = float(logits_tensor[0, 0].item())
                proba_long_val = None
                proba_flat_val = None
                proba_short_val = None
                is_ternary = False
            else:
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
    if is_regression:
        # ── Regression : décision basée sur le signe ─────────────────
        if raw_proba > 0:
            pred_class = 1
            signal_label = "long"
            predicted_side_val = "long"
        elif raw_proba < 0:
            pred_class = 0
            signal_label = "short"
            predicted_side_val = "short"
        else:
            pred_class = 0
            signal_label = "no_trade"
            predicted_side_val = None
        proba = raw_proba  # score continu
    elif is_ternary and num_classes >= 3:
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
# Cascade config loader (Étape 1 — cascade_ml.md)
# ────────────────────────────────────────────────────────────────────

def load_cascade_config() -> dict[str, Any]:
    """Charge la configuration cascade depuis config.yaml.

    Returns:
        dict avec clés ``top_pct`` (float, défaut 0.20),
        ``min_prob_classification`` (float, défaut 0.55) et
        ``min_prob_regression`` (float, défaut 0.10).
    """
    _defaults: dict[str, Any] = {
        "top_pct": 0.20,
        "min_prob_classification": 0.55,
        "min_prob_regression": 0.10,
    }
    try:
        import yaml as _yaml
        with open("config.yaml", encoding="utf-8") as _fh:
            _raw = _yaml.safe_load(_fh) or {}
        _section = _raw.get("cascade") or {}
        # Backward compat: if old "min_prob" key exists, use it for both
        _legacy = _section.get("min_prob")
        return {
            "top_pct": float(_section.get("top_pct", _defaults["top_pct"])),
            "min_prob_classification": float(
                _section.get("min_prob_classification", _legacy or _defaults["min_prob_classification"])
            ),
            "min_prob_regression": float(
                _section.get("min_prob_regression", _legacy or _defaults["min_prob_regression"])
            ),
        }
    except Exception:
        return _defaults


# ── Per-symbol features (parité entraînement/prédiction) ──

def load_per_symbol_features(artifacts_dir: Path) -> dict[str, Any]:
    """Charge les features per-symbol depuis ``_per_symbol_features.json``.

    Ce fichier est sauvegardé par ``run_training_batch()`` à la fin de
    chaque campagne d'entraînement.  Il capture l'ensemble exact des
    features et flags utilisés pour tous les symboles du batch.

    Returns:
        dict avec ``feature_columns``, ``feature_set``, ``include_*``,
        ``enable_cross_sectional``, ``global_stacking_enabled``.
        Retourne un dict vide si le fichier n'existe pas (batch ancien).
    """
    _cache_key = str(artifacts_dir.resolve())
    _cached = _per_symbol_features_cache.get(_cache_key)
    if _cached is not None:
        return _cached

    _path = artifacts_dir / "_per_symbol_features.json"
    if not _path.exists():
        LOGGER.info("load_per_symbol_features: %s not found (legacy batch)", _path)
        _per_symbol_features_cache[_cache_key] = {}
        return {}

    try:
        _payload = json.loads(_path.read_text(encoding="utf-8"))
        if not isinstance(_payload, dict):
            _per_symbol_features_cache[_cache_key] = {}
            return {}
        _per_symbol_features_cache[_cache_key] = _payload
        LOGGER.info(
            "load_per_symbol_features: loaded %d features, feature_set=%s, stacking=%s",
            len(_payload.get("feature_columns", [])),
            _payload.get("feature_set"),
            _payload.get("global_stacking_enabled"),
        )
        return _payload
    except Exception:
        LOGGER.warning("load_per_symbol_features: failed to parse %s", _path)
        _per_symbol_features_cache[_cache_key] = {}
        return {}


def upsert_global_ranks(
    batch_id: str,
    trade_date: str,
    ranks: list[dict[str, Any]],
    engine: Any | None = None,
) -> int:
    """Insère ou écrase les rangs globaux dans ``global_rank_history``.

    Args:
        batch_id: Identifiant du batch de modèles utilisé.
        trade_date: Date de trading (YYYY-MM-DD).
        ranks: Liste de dicts ``{symbol, global_rank_3, global_rank_5, global_rank_10}``.
        engine: SQLAlchemy engine. Si None, utilise ``get_engine()``.

    Returns:
        Nombre de lignes insérées/écrasées.
    """
    if not ranks:
        return 0
    if engine is None:
        try:
            from ihm.services.db import get_engine as _get_engine
            engine = _get_engine()
        except Exception:
            LOGGER.warning("upsert_global_ranks: no engine available")
            return 0
    if engine is None:
        return 0

    from sqlalchemy import text as _text

    _rank_cols = ["global_rank_3", "global_rank_5", "global_rank_10", "global_rank_15", "global_rank_20"]
    # Filtrer aux colonnes qui existent réellement dans la table
    _available_ranks: list[str] = []
    try:
        with engine.connect() as conn:
            _table_cols = conn.execute(
                _text("SELECT column_name FROM information_schema.columns WHERE table_name = 'global_rank_history'")
            ).fetchall()
            _existing = {row[0] for row in _table_cols}
            for _rc in _rank_cols:
                if _rc in _existing:
                    _available_ranks.append(_rc)
    except Exception:
        _available_ranks = ["global_rank_3", "global_rank_5", "global_rank_10"]  # fallback

    # Construire la requête SQL dynamiquement
    _insert_cols = ["symbol", "date"] + _available_ranks + ["batch_id"]
    _insert_placeholders = ", ".join(f":{c}" for c in _insert_cols)
    _update_clauses = ", ".join(
        f"{c} = VALUES({c})" for c in _available_ranks
    )
    _sql = _text(
        f"INSERT INTO alpha_trade.global_rank_history "
        f"({', '.join(_insert_cols)}) "
        f"VALUES ({_insert_placeholders}) "
        f"ON DUPLICATE KEY UPDATE "
        f"{_update_clauses}, "
        f"created_at = CURRENT_TIMESTAMP"
    )

    total = 0
    try:
        with engine.begin() as conn:
            for row in ranks:
                _params: dict[str, Any] = {
                    "symbol": str(row["symbol"]),
                    "date": trade_date,
                    "batch_id": batch_id,
                }
                for _rc in _available_ranks:
                    _params[_rc] = float(row.get(_rc)) if row.get(_rc) is not None else None
                conn.execute(_sql, _params)
                total += 1
    except Exception:
        LOGGER.exception("upsert_global_ranks: DB error for %s rows on %s", len(ranks), trade_date)
    return total


def predict_global_rank_history(
    start_date: str,
    end_date: str,
    batch_id: str,
    *,
    artifacts_dir: Path | None = None,
    engine: Any | None = None,
) -> dict[str, int]:
    """Prédit les rangs globaux pour une période et les persiste en DB.

    Pour chaque jour de bourse entre ``start_date`` et ``end_date`` :
    1. Charge les barres de l'univers tradable
    2. Appelle ``predict_global_rank()`` (depuis global_ranking.py)
    3. Upsert les résultats dans ``global_rank_history``

    Le ``batch_id`` doit être déterminé par l'appelant selon le contexte :
    - **Backtest** → ``config.yaml`` → ``batch_diagnostics.backtest_batch_id``
    - **Live**     → ``config.yaml`` → ``batch_diagnostics.live_batch_id``

    Args:
        start_date: Date début (YYYY-MM-DD).
        end_date: Date fin inclusive (YYYY-MM-DD).
        batch_id: Identifiant du batch de modèles à utiliser.
        artifacts_dir: Répertoire des artefacts du batch. Si None, déduit
                       depuis ``get_model_artifacts_dir() / batch_id``.
        engine: SQLAlchemy engine. Si None, utilise ``get_engine()``.

    Returns:
        Dict ``{date_str: nb_symbols_upserted}``.
    """
    from datetime import timedelta as _td

    if artifacts_dir is None:
        from ihm.services.ml_artifacts import get_model_artifacts_dir as _get_dir
        artifacts_dir = _get_dir() / batch_id

    if engine is None:
        try:
            from ihm.services.db import get_engine as _get_engine
            engine = _get_engine()
        except Exception:
            LOGGER.warning("predict_global_rank_history: no engine available")
            return {}

    if engine is None:
        return {}

    # ── Imports lourds ──
    from modelFactory.global_ranking import predict_global_rank
    from modelFactory.data_loader import load_universe_bars
    from modelFactory.db_registry import load_tradable_universe_symbols

    _start = pd.Timestamp(start_date)
    _end = pd.Timestamp(end_date)

    # Récupérer toutes les dates de bourse dans la période
    try:
        from sqlalchemy import text as _text
        with engine.connect() as conn:
            _dates_rows = conn.execute(
                _text(
                    "SELECT DISTINCT date FROM alpha_trade.stock_bars_daily "
                    "WHERE date BETWEEN :s AND :e ORDER BY date"
                ),
                {"s": str(_start.date()), "e": str(_end.date())},
            ).fetchall()
        trading_dates = [str(row[0]) for row in _dates_rows]
    except Exception:
        # Fallback : générer tous les jours et filtrer (lent)
        _all_dates = pd.date_range(_start, _end, freq="B")
        trading_dates = [d.strftime("%Y-%m-%d") for d in _all_dates]

    if not trading_dates:
        LOGGER.warning("predict_global_rank_history: no trading dates in [%s, %s]", start_date, end_date)
        return {}

    from modelFactory.global_ranking import predict_global_rank
    from modelFactory.data_loader import load_universe_bars
    from modelFactory.db_registry import load_tradable_universe_symbols

    results: dict[str, int] = {}
    _lookback_days = 365

    for trade_date_str in trading_dates:
        _trade_date = pd.Timestamp(trade_date_str).date()
        _start_lookback = _trade_date - _td(days=_lookback_days)

        try:
            # Charger l'univers du jour
            universe_symbols = load_tradable_universe_symbols(engine, trade_date=_trade_date)
            if not universe_symbols:
                LOGGER.warning("predict_global_rank_history: empty universe on %s", trade_date_str)
                results[trade_date_str] = 0
                continue

            universe_df = load_universe_bars(
                engine, universe_symbols,
                end_date=_trade_date,
                start_date=_start_lookback,
            )
            if universe_df.empty:
                LOGGER.warning("predict_global_rank_history: empty bars on %s", trade_date_str)
                results[trade_date_str] = 0
                continue

            # Prédire les rangs
            rank_df = predict_global_rank(universe_df, artifacts_dir, engine=engine)
            if rank_df is None or rank_df.empty:
                LOGGER.warning("predict_global_rank_history: predict_global_rank returned None on %s", trade_date_str)
                results[trade_date_str] = 0
                continue

            # Upsert
            ranks_list = rank_df.to_dict(orient="records")
            nb = upsert_global_ranks(batch_id, trade_date_str, ranks_list, engine=engine)
            results[trade_date_str] = nb
            LOGGER.info(
                "predict_global_rank_history: %s — %d symbols upserted",
                trade_date_str, nb,
            )

        except Exception:
            LOGGER.exception("predict_global_rank_history: failed for %s", trade_date_str)
            results[trade_date_str] = -1

    _total = sum(v for v in results.values() if v > 0)
    LOGGER.info(
        "predict_global_rank_history: DONE — %d dates, %d total rows upserted",
        len(results), _total,
    )
    return results


# ────────────────────────────────────────────────────────────────────
# Per-Symbol Cross-Sectional IC (2026-07-29)
# ────────────────────────────────────────────────────────────────────

def compute_per_symbol_cross_sectional_ic(
    engine: "Engine",
    batch_id: str,
    *,
    horizon: int = 5,
    min_symbols_per_date: int = 10,
) -> dict[str, Any]:
    """Calcule l'IC cross-sectionnel du modèle per-symbol.

    Requiert que le batch ait :
    1. Des prédictions per-symbol dans la table de prédictions
    2. Un global_rank_df avec future_return_{horizon} dans la DB

    Le résultat est loggé avec le préfixe ``per_symbol_ic`` pour
    être facilement recherchable dans les logs.

    Args:
        engine: SQLAlchemy engine.
        batch_id: ID du batch d'entraînement.
        horizon: Horizon de forward return (défaut: 5, comme H5).
        min_symbols_per_date: Seuil minimum de symboles par date.

    Returns:
        dict avec ic_mean, ic_std, n_dates.
    """
    from modelFactory.global_ranking import compute_cross_sectional_ic
    from sqlalchemy import text as _text

    LOGGER.info("per_symbol_ic compute start batch_id=%s horizon=%d", batch_id, horizon)

    # Charger les prédictions per-symbol depuis la DB (via run_id → batch_id)
    _pred_sql = _text("""
        SELECT mp.symbol, mp.prediction_date AS date, mp.predicted_proba AS proba_long
        FROM alpha_trade.model_predictions mp
        JOIN alpha_trade.model_training_run mtr ON mtr.run_id = mp.run_id
        WHERE mtr.batch_id = :batch_id
    """)
    try:
        pred_df = pd.read_sql(_pred_sql, engine, params={"batch_id": batch_id})
    except Exception as exc:
        LOGGER.warning("per_symbol_ic failed to load predictions: %s", exc)
        return {"ic_mean": None, "error": str(exc)}

    if pred_df.empty:
        LOGGER.warning("per_symbol_ic no predictions for batch_id=%s", batch_id)
        return {"ic_mean": None, "n_dates": 0}

    pred_df["date"] = pd.to_datetime(pred_df["date"])

    # Charger les forward returns depuis la DB (calculés via _spy_series)
    _fw_sql = _text("""
        SELECT symbol, date,
               close AS spot,
               LEAD(close, :h) OVER (PARTITION BY symbol ORDER BY date) AS fwd_close
        FROM alpha_trade.stock_bars_daily
        WHERE date BETWEEN
            (SELECT MIN(mp.prediction_date) FROM alpha_trade.model_predictions mp
             JOIN alpha_trade.model_training_run mtr ON mtr.run_id = mp.run_id
             WHERE mtr.batch_id = :batch_id)
            AND
            (SELECT MAX(mp.prediction_date) FROM alpha_trade.model_predictions mp
             JOIN alpha_trade.model_training_run mtr ON mtr.run_id = mp.run_id
             WHERE mtr.batch_id = :batch_id)
    """)
    try:
        bars_df = pd.read_sql(_fw_sql, engine, params={"batch_id": batch_id, "h": horizon})
    except Exception as exc:
        LOGGER.warning("per_symbol_ic failed to load bars: %s", exc)
        return {"ic_mean": None, "error": str(exc)}

    if bars_df.empty:
        LOGGER.warning("per_symbol_ic no bar data for batch_id=%s", batch_id)
        return {"ic_mean": None, "n_dates": 0}

    bars_df["future_return"] = bars_df["fwd_close"] / bars_df["spot"] - 1.0
    bars_df = bars_df.dropna(subset=["future_return"])
    bars_df["date"] = pd.to_datetime(bars_df["date"])

    # Merger prédictions et forward returns
    merged = pred_df.merge(bars_df[["symbol", "date", "future_return"]], on=["symbol", "date"], how="inner")

    # Vol scaling (même que Global Ranking H5+)
    merged["rolling_volatility_20"] = 0.01  # fallback
    _vol = (
        bars_df.groupby("symbol")["spot"]
        .rolling(20).std()
        .reset_index(level=0, drop=True)
    )
    bars_df["_vol20"] = _vol
    bars_df["_vol20"] = bars_df["_vol20"].fillna(bars_df["_vol20"].median()).clip(lower=0.001)
    merged = merged.merge(
        bars_df[["symbol", "date", "_vol20"]],
        on=["symbol", "date"], how="left",
    )
    merged["rolling_volatility_20"] = merged["_vol20"].fillna(0.01)

    # Calculer l'IC cross-sectionnel
    _result = compute_cross_sectional_ic(
        merged,
        score_col="proba_long",
        return_col="future_return",
        vol_col="rolling_volatility_20",
        min_symbols_per_date=min_symbols_per_date,
    )

    _ic_mean = _result.get("ic_mean")
    LOGGER.info(
        "per_symbol_ic DONE batch_id=%s horizon=%d ic_mean=%.4f ic_std=%.4f n_dates=%d",
        batch_id, horizon,
        _ic_mean if _ic_mean is not None else float("nan"),
        _result.get("ic_std", float("nan")),
        _result.get("n_dates", 0),
    )
    return _result


# ────────────────────────────────────────────────────────────────────
# Cascade ML (Étape 4 — cascade_ml.md)
# ────────────────────────────────────────────────────────────────────

from dataclasses import dataclass as _dataclass


@_dataclass
class CascadePrediction:
    """Prédiction per-symbol utilisée par le filtre cascade."""
    symbol: str
    long_prob: float
    short_prob: float
    flat_prob: float = 0.0
    side: str = "flat"  # "long", "short", "flat"


def load_global_ranks_from_db(
    trade_date: str,
    batch_id: str,
    *,
    engine: Any | None = None,
) -> pd.DataFrame:
    """Charge les rangs globaux depuis ``global_rank_history`` pour une date.

    Args:
        trade_date: Date de trading (YYYY-MM-DD).
        batch_id: Identifiant du batch.
        engine: SQLAlchemy engine. Si None, utilise ``get_engine()``.

    Returns:
        DataFrame [symbol, global_rank_3, global_rank_5, global_rank_10]
        ou DataFrame vide si aucune donnée.
    """
    if engine is None:
        try:
            from ihm.services.db import get_engine as _get_engine
            engine = _get_engine()
        except Exception:
            LOGGER.warning("load_global_ranks_from_db: no engine available")
            return pd.DataFrame()

    if engine is None:
        return pd.DataFrame()

    from sqlalchemy import text as _text

    # ── P0-5 : interroger tous les horizons disponibles ──
    _rank_cols = ["global_rank_3", "global_rank_5", "global_rank_10", "global_rank_15", "global_rank_20"]
    # Ne garder que les colonnes qui existent réellement
    _available = ["symbol"]
    try:
        with engine.connect() as conn:
            _table_cols = conn.execute(
                _text("SELECT column_name FROM information_schema.columns WHERE table_name = 'global_rank_history'")
            ).fetchall()
            _existing = {row[0] for row in _table_cols}
            for _rc in _rank_cols:
                if _rc in _existing:
                    _available.append(_rc)
    except Exception:
        _available.extend(_rank_cols)  # fallback: try all

    _query = f"SELECT {', '.join(_available)} FROM global_rank_history WHERE date = :d AND batch_id = :bid"

    try:
        with engine.connect() as conn:
            rows = conn.execute(_text(_query), {"d": trade_date, "bid": batch_id}).fetchall()
    except Exception:
        LOGGER.exception("load_global_ranks_from_db: query failed for %s / %s", trade_date, batch_id)
        return pd.DataFrame()

    if not rows:
        LOGGER.warning("load_global_ranks_from_db: no ranks for %s / %s", trade_date, batch_id)
        return pd.DataFrame()

    # Construire le DataFrame dynamiquement depuis les colonnes disponibles
    _cols = _available  # liste déterminée plus haut (ex: [symbol, global_rank_3, ...])
    _data = []
    for r in rows:
        _data.append(tuple(r))
    return pd.DataFrame(_data, columns=_cols)


def _load_best_horizon_for_batch(batch_id: str, *, engine: Any | None = None) -> int | None:
    """Lit le meilleur horizon depuis le metadata du batch.

    Returns:
        H (int) ou None si indisponible.
    """
    if engine is None:
        return None
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT metadata_json FROM model_training_batch WHERE batch_id = :bid"),
                {"bid": batch_id},
            ).fetchone()
        if row and row[0]:
            import json as _json
            _meta = _json.loads(str(row[0]))
            _gr = _meta.get("global_ranking", {}) if isinstance(_meta, dict) else {}
            _best = _gr.get("best_horizon")
            if _best is not None:
                return int(_best)
    except Exception:
        pass
    return None


def cascade_select(
    trade_date: str,
    batch_id: str,
    per_symbol_preds: dict[str, CascadePrediction],
    *,
    top_pct: float | None = None,
    min_prob: float | None = None,
    engine: Any | None = None,
) -> list[tuple[str, str, float]]:
    """Filtre cascade : Global Rank → Per-Symbol → trades ordonnancés.

    Pour chaque symbole ayant un rang global ET une prédiction per-symbol :
    1. Filtre top/bottom N% selon ``global_rank_20`` (H20, meilleur horizon)
    2. Vérifie que la proba per-symbol > ``min_prob``
    3. Score multiplicatif : ``rank × prob``
    4. Trie par score décroissant

    Args:
        trade_date: Date de trading (YYYY-MM-DD).
        batch_id: Identifiant du batch Global Model.
        per_symbol_preds: Dict {symbol: CascadePrediction}.
        top_pct: Seuil top/bottom (défaut: config.yaml → cascade.top_pct).
        min_prob: Proba minimale per-symbol (défaut: config.yaml → cascade.min_prob).
        engine: SQLAlchemy engine.

    Returns:
        Liste de tuples ``(side, symbol, score)`` triée par score décroissant.
    """
    # ── Charger la config cascade ──
    _cfg = load_cascade_config()
    _top_pct = top_pct if top_pct is not None else float(_cfg["top_pct"])
    _min_prob = min_prob if min_prob is not None else float(_cfg.get("min_prob_regression", 0.10))

    # ── Charger les rangs globaux depuis la DB ──
    ranks_df = load_global_ranks_from_db(trade_date, batch_id, engine=engine)
    if ranks_df.empty:
        LOGGER.warning("cascade_select: no global ranks for %s / %s", trade_date, batch_id)
        return []

    # ── Déterminer le meilleur horizon ──
    # 1. Lire best_horizon depuis le metadata du batch (calculé à l'entraînement)
    # 2. Si indisponible, fallback H20 → H15 → H10 → H5 → H3
    _best_h = _load_best_horizon_for_batch(batch_id, engine=engine)
    _rank_col = None
    _fallback_cols = ["global_rank_20", "global_rank_15", "global_rank_10", "global_rank_5", "global_rank_3"]
    _priority_cols = [f"global_rank_{_best_h}"] + [c for c in _fallback_cols if c != f"global_rank_{_best_h}"] if _best_h else _fallback_cols
    for _col in _priority_cols:
        if _col in ranks_df.columns and ranks_df[_col].notna().any():
            _rank_col = _col
            LOGGER.info("cascade_select: using horizon %s (best=%s)", _col, f"H{_best_h}" if _best_h else "auto")
            break
    if _rank_col is None:
        LOGGER.warning("cascade_select: no rank column found in %s", list(ranks_df.columns))
        return []

    candidates: list[tuple[str, str, float]] = []

    for _, row in ranks_df.iterrows():
        symbol = str(row["symbol"])
        rank = float(row[_rank_col]) if pd.notna(row[_rank_col]) else None

        if rank is None:
            continue

        # Filtre top/bottom N%
        is_top = rank > (1.0 - _top_pct)
        is_bottom = rank < _top_pct

        if not (is_top or is_bottom):
            continue

        # Prédiction per-symbol
        pred = per_symbol_preds.get(symbol)
        if pred is None:
            continue

        if is_top and pred.long_prob > _min_prob:
            rank_dir = rank  # déjà proche de 1.0
            score = rank_dir * pred.long_prob
            candidates.append(("LONG", symbol, score))

        elif is_bottom and pred.short_prob > _min_prob:
            rank_dir = 1.0 - rank  # inverse : 0.05 → 0.95
            score = rank_dir * pred.short_prob
            candidates.append(("SHORT", symbol, score))

    # Tri par score décroissant
    candidates.sort(key=lambda x: x[2], reverse=True)

    LOGGER.info(
        "cascade_select: %s / %s — %d candidates (top_pct=%.2f, min_prob=%.2f)",
        trade_date, batch_id, len(candidates), _top_pct, _min_prob,
    )
    return candidates


def apply_cascade_to_predictions(
    preds_df: pd.DataFrame,
    batch_id: str,
    *,
    top_pct: float | None = None,
    min_prob: float | None = None,
    engine: Any | None = None,
) -> pd.DataFrame:
    """Filtre les prédictions per-symbol via la cascade Global Rank.

    Pour chaque date de trading dans ``preds_df`` :
    1. Charge les rangs globaux depuis ``global_rank_history``
    2. Convertit les prédictions en ``CascadePrediction``
    3. Appelle ``cascade_select()``
    4. Ne garde que les symboles retenus par la cascade

    Les symboles non retenus voient leur ``predicted_side`` forcé à
    ``"flat"`` et leurs probas mises à 0 — ils sont ainsi exclus du
    backtest sans casser le contrat de ``replay_signals()``.

    Args:
        preds_df: DataFrame au format ``load_predictions()`` avec colonnes
                  ``symbol, trade_date, predicted_side, proba_long, proba_short``.
        batch_id: Identifiant du batch Global Model.
        top_pct: Seuil top/bottom (défaut: config.yaml).
        min_prob: Proba minimale (défaut: config.yaml).
        engine: SQLAlchemy engine.

    Returns:
        DataFrame filtré (mêmes colonnes, lignes non-cascade → flat).
    """
    if preds_df.empty:
        return preds_df

    _date_col = "trade_date" if "trade_date" in preds_df.columns else "prediction_date"
    if _date_col not in preds_df.columns:
        LOGGER.warning("apply_cascade_to_predictions: no date column found")
        return preds_df

    _required_cols = {"symbol", "predicted_side", "proba_long", "proba_short"}
    _missing = _required_cols - set(preds_df.columns)
    if _missing:
        LOGGER.warning("apply_cascade_to_predictions: missing columns %s", _missing)
        return preds_df

    result = preds_df.copy()
    # Initialiser la colonne cascade_score
    result["cascade_score"] = 0.0

    # ── P0-5 (2026-08-06) : détecter le mode (regression vs classification) ──
    _has_ternary = (
        "proba_long" in result.columns
        and result["proba_long"].notna().any()
    )
    _cfg = load_cascade_config()
    _top_pct = top_pct if top_pct is not None else float(_cfg["top_pct"])
    if min_prob is not None:
        _min_prob = float(min_prob)
    elif _has_ternary:
        _min_prob = float(_cfg["min_prob_classification"])
    else:
        _min_prob = float(_cfg["min_prob_regression"])
    LOGGER.info(
        "apply_cascade_to_predictions: mode=%s min_prob=%.2f top_pct=%.2f",
        "classification" if _has_ternary else "regression", _min_prob, _top_pct,
    )

    _dates = sorted(result[_date_col].dropna().unique())
    _total_passed = 0
    _total_processed = 0

    for _d in _dates:
        _date_str = str(_d)[:10]
        _mask = result[_date_col].astype(str).str[:10] == _date_str
        _day_preds = result.loc[_mask]
        if _day_preds.empty:
            continue

        # Construire le dict CascadePrediction
        _pred_dict: dict[str, CascadePrediction] = {}
        for _, _row in _day_preds.iterrows():
            _sym = str(_row["symbol"])
            _side = str(_row.get("predicted_side") or "flat")
            _proba = float(_row.get("predicted_proba") or 0.0)
            _long = float(_row.get("proba_long") or 0.0)
            _short = float(_row.get("proba_short") or 0.0)
            _flat = float(_row.get("proba_flat") or 0.0)
            # P0-5 (2026-08-06) : en mode regression, proba_long/short sont NULL.
            # Utiliser |predicted_proba| comme force du signal selon le signe.
            if _long == 0.0 and _short == 0.0 and _side != "flat":
                if _side == "long":
                    _long = abs(_proba)
                elif _side == "short":
                    _short = abs(_proba)
            _pred_dict[_sym] = CascadePrediction(
                symbol=_sym,
                long_prob=_long,
                short_prob=_short,
                flat_prob=_flat,
                side=_side,
            )

        # Appliquer la cascade
        _candidates = cascade_select(
            _date_str, batch_id, _pred_dict,
            top_pct=_top_pct, min_prob=_min_prob,
            engine=engine,
        )

        # Symbols retenus par la cascade
        _passed_symbols = {_sym for _, _sym, _ in _candidates}
        _score_map = {_sym: _score for _, _sym, _score in _candidates}

        # P0-5 (2026-08-06) : en mode regression, proba_long/short sont NULL.
        # Après cascade, on les peuple depuis |predicted_proba| pour que
        # replay_signals() puisse les utiliser (il exige notna()).
        for _sym in _passed_symbols:
            _cp = _pred_dict.get(_sym)
            if _cp is None:
                continue
            _pm = _mask & (result["symbol"].astype(str) == _sym)
            if "proba_long" in result.columns and _cp.long_prob > 0:
                result.loc[_pm, "proba_long"] = _cp.long_prob
            if "proba_short" in result.columns and _cp.short_prob > 0:
                result.loc[_pm, "proba_short"] = _cp.short_prob

        # Forcer flat pour les non-retenus
        _flat_mask = _mask & (~result["symbol"].astype(str).isin(_passed_symbols))
        if _flat_mask.any():
            result.loc[_flat_mask, "predicted_side"] = "flat"
            result.loc[_flat_mask, "proba_long"] = 0.0
            result.loc[_flat_mask, "proba_short"] = 0.0
            if "proba_flat" in result.columns:
                result.loc[_flat_mask, "proba_flat"] = 1.0

        # Stocker le score cascade pour les retenus
        for _sym, _score in _score_map.items():
            _score_mask = _mask & (result["symbol"].astype(str) == _sym)
            result.loc[_score_mask, "cascade_score"] = _score

        _total_passed += len(_candidates)
        _total_processed += len(_day_preds)

    LOGGER.info(
        "apply_cascade_to_predictions: %d/%d predictions passed cascade "
        "(batch=%s, dates=%d)",
        _total_passed, _total_processed, batch_id, len(_dates),
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

        rank_df = predict_global_rank(universe_df, artifacts_dir, engine=engine)
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

