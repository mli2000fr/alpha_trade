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


def _build_routes_dataframe(config_data: dict[str, Any]) -> pd.DataFrame:
    routing = config_data.get("artifact_routes") or {}
    models = routing.get("models") or {}
    rows: list[dict[str, Any]] = []
    for model_name, route in models.items():
        if not isinstance(route, dict):
            continue
        rows.append(
            {
                "model_name": model_name,
                "status": route.get("status"),
                "inference_backend": route.get("inference_backend"),
                "artifact_symbol": route.get("artifact_symbol"),
                "checkpoint_path": route.get("checkpoint_path"),
                "scaler_path": route.get("scaler_path"),
                "model_path": route.get("model_path"),
                "config_path": route.get("config_path"),
                "calibrator_path": route.get("calibrator_path"),
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
            "routes_df": pd.DataFrame(),
            "ranking_df": pd.DataFrame(),
        }

    config_data, config_error = _read_json_file(config_path)
    if config_error:
        errors.append(config_error)
    metrics_data, metrics_error = _read_json_file(metrics_path)
    if metrics_error:
        errors.append(metrics_error)

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
        "routes_df": _build_routes_dataframe(config_data),
        "ranking_df": _build_ranking_dataframe(metrics_data),
    }

