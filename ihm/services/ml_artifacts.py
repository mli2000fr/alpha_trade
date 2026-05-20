"""ihm/services/ml_artifacts.py — Lecture des artefacts modelFactory pour l'IHM."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ihm.services.pipeline_runner import PROJECT_ROOT


DEFAULT_MODEL_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "models"


def get_model_artifacts_dir(artifacts_dir: Path | None = None) -> Path:
    return Path(artifacts_dir) if artifacts_dir is not None else DEFAULT_MODEL_ARTIFACTS_DIR


def _symbol_sort_key(symbol: str) -> tuple[bool, str]:
    return (symbol.startswith("__"), symbol)


def list_ml_artifact_symbols(artifacts_dir: Path | None = None) -> list[str]:
    root = get_model_artifacts_dir(artifacts_dir)
    if not root.exists() or not root.is_dir():
        return []
    symbols: list[str] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if (child / "config.json").exists() or (child / "metrics.json").exists():
            symbols.append(child.name)
    return sorted(symbols, key=_symbol_sort_key)


def _read_json_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"Fichier absent : `{path.name}`"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        return None, f"JSON invalide dans `{path.name}` : {exc}"
    except Exception as exc:  # pragma: no cover
        return None, f"Lecture impossible de `{path.name}` : {exc}"
    if not isinstance(data, dict):
        return None, f"Le manifeste `{path.name}` doit contenir un objet JSON en racine."
    return data, None


def _coerce_path(value: Any) -> Path | None:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    return None


def _path_exists(value: Any) -> bool:
    path = _coerce_path(value)
    return bool(path is not None and path.exists())


def _build_selector_universe_filter_summary(config_data: dict[str, Any]) -> dict[str, Any]:
    data_cfg = config_data.get("data") if isinstance(config_data.get("data"), dict) else {}
    signal_modes = data_cfg.get("selector_universe_signal_modes")
    normalized_modes = [
        str(value).strip().lower()
        for value in (signal_modes if isinstance(signal_modes, list | tuple) else [])
        if str(value).strip()
    ]
    return {
        "include_selector_context_features": bool(data_cfg.get("include_selector_context_features", False)),
        "selector_universe_signal_modes": normalized_modes,
        "selector_universe_max_candidate_rank": data_cfg.get("selector_universe_max_candidate_rank"),
        "selector_universe_exclude_earnings_blackout": bool(
            data_cfg.get("selector_universe_exclude_earnings_blackout", False)
        ),
    }


def _route_health(model_name: str, route: dict[str, Any]) -> tuple[str, list[str], dict[str, bool]]:
    expected_keys = {
        "lstm_attention": ("checkpoint_path", "scaler_path", "config_path"),
        "global_model": ("model_path", "config_path"),
        "lightgbm": ("model_path", "config_path"),
        "catboost": ("model_path", "config_path"),
    }.get(model_name, ("config_path",))
    existence: dict[str, bool] = {}
    errors: list[str] = []
    for key in expected_keys:
        path = _coerce_path(route.get(key))
        exists = bool(path is not None and path.exists())
        existence[key] = exists
        if not exists:
            errors.append(f"{model_name}:{key}_missing")
    if errors:
        return "missing_paths", errors, existence
    return "healthy", [], existence


def _build_routes_dataframe(config_data: dict[str, Any]) -> pd.DataFrame:
    routing = config_data.get("artifact_routes") or {}
    models = routing.get("models") or {}
    rows: list[dict[str, Any]] = []
    for model_name, route in models.items():
        if not isinstance(route, dict):
            continue
        route_health, route_errors, existence = _route_health(str(model_name), route)
        rows.append(
            {
                "model_name": model_name,
                "status": route.get("status"),
                "route_health": route_health,
                "route_errors": ", ".join(route_errors),
                "inference_backend": route.get("inference_backend"),
                "artifact_symbol": route.get("artifact_symbol"),
                "checkpoint_path": route.get("checkpoint_path"),
                "checkpoint_exists": existence.get("checkpoint_path"),
                "scaler_path": route.get("scaler_path"),
                "scaler_exists": existence.get("scaler_path"),
                "model_path": route.get("model_path"),
                "model_exists": existence.get("model_path"),
                "config_path": route.get("config_path"),
                "config_exists": existence.get("config_path"),
                "calibrator_path": route.get("calibrator_path"),
                "calibrator_exists": _path_exists(route.get("calibrator_path")) if route.get("calibrator_path") else False,
                "selected_decision_threshold": route.get("selected_decision_threshold"),
                "feature_columns": ", ".join(route.get("feature_columns") or []) if isinstance(route.get("feature_columns"), list) else route.get("feature_columns"),
            }
        )
    return pd.DataFrame(rows)


def _build_ranking_dataframe(metrics_data: dict[str, Any]) -> pd.DataFrame:
    challengers = metrics_data.get("challengers") or {}
    ranking = challengers.get("ranking") or []
    if not isinstance(ranking, list):
        return pd.DataFrame()
    normalized = [row for row in ranking if isinstance(row, dict)]
    return pd.DataFrame(normalized)


def load_ml_artifact_report(symbol: str, artifacts_dir: Path | None = None) -> dict[str, Any]:
    root = get_model_artifacts_dir(artifacts_dir)
    symbol_dir = root / symbol
    config_path = symbol_dir / "config.json"
    metrics_path = symbol_dir / "metrics.json"

    errors: list[str] = []
    if not symbol_dir.exists() or not symbol_dir.is_dir():
        return {
            "symbol": symbol,
            "symbol_dir": symbol_dir,
            "config_path": config_path,
            "metrics_path": metrics_path,
            "config": {},
            "metrics": {},
            "errors": [f"Dossier symbole absent : `{symbol_dir}`"],
            "selected_model": None,
            "selection_mode": None,
            "run_id": None,
            "selected_decision_threshold": None,
            "champion": {},
            "health_status": "invalid",
            "selected_route_health": "missing_symbol_dir",
            "selected_route_errors": [f"missing_symbol_dir:{symbol}"],
            "routes_df": pd.DataFrame(),
            "ranking_df": pd.DataFrame(),
        }

    config_data, config_error = _read_json_file(config_path)
    if config_error:
        errors.append(config_error)
    metrics_data, metrics_error = _read_json_file(metrics_path)
    if metrics_error:
        errors.append(metrics_error)
    config_health = "healthy" if config_error is None else "invalid"
    metrics_health = "healthy" if metrics_error is None else "invalid"

    config_data = config_data or {}
    metrics_data = metrics_data or {}
    champion = metrics_data.get("champion") if isinstance(metrics_data.get("champion"), dict) else {}

    selected_model = (
        (config_data.get("artifact_routes") or {}).get("selected_model")
        or config_data.get("architecture_selected")
        or champion.get("model_name")
    )
    selected_decision_threshold = config_data.get("selected_decision_threshold")
    if selected_decision_threshold is None and isinstance(config_data.get("data"), dict):
        selected_decision_threshold = config_data["data"].get("decision_threshold")

    routes_df = _build_routes_dataframe(config_data)
    selected_route_errors: list[str] = []
    selected_route_health = "missing_selected_route"
    if selected_model and not routes_df.empty and "model_name" in routes_df.columns:
        selected_rows = routes_df[routes_df["model_name"].astype(str) == str(selected_model)]
        if not selected_rows.empty:
            selected_route = selected_rows.iloc[0]
            selected_route_health = str(selected_route.get("route_health") or "unknown")
            raw_errors = str(selected_route.get("route_errors") or "").strip()
            selected_route_errors = [part.strip() for part in raw_errors.split(",") if part.strip()]
    if errors:
        health_status = "invalid"
    elif selected_route_health == "healthy":
        health_status = "healthy"
    elif selected_model:
        health_status = "degraded"
    else:
        health_status = "invalid"
    if config_health == "invalid":
        manifest_health = "invalid"
    elif metrics_health == "invalid":
        manifest_health = "degraded"
    else:
        manifest_health = "healthy"
    degraded_reasons = [str(item) for item in [*errors, *selected_route_errors] if str(item).strip()]
    selector_universe_filter = _build_selector_universe_filter_summary(config_data)

    return {
        "symbol": symbol,
        "symbol_dir": symbol_dir,
        "config_path": config_path,
        "metrics_path": metrics_path,
        "config": config_data,
        "metrics": metrics_data,
        "errors": errors,
        "selected_model": selected_model,
        "selection_mode": config_data.get("selection_mode") or champion.get("selection_mode"),
        "run_id": config_data.get("run_id"),
        "selected_decision_threshold": selected_decision_threshold,
        "champion": champion,
        "health_status": health_status,
        "manifest_health": manifest_health,
        "config_health": config_health,
        "metrics_health": metrics_health,
        "selected_route_health": selected_route_health,
        "selected_route_errors": selected_route_errors,
        "degraded_reasons": degraded_reasons,
        "selector_universe_filter": selector_universe_filter,
        "routes_df": routes_df,
        "ranking_df": _build_ranking_dataframe(metrics_data),
    }

