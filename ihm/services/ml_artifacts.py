"""ihm/services/ml_artifacts.py — Lecture des artefacts modelFactory pour l'IHM."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ihm.services.pipeline_runner import PROJECT_ROOT


DEFAULT_MODEL_ARTIFACTS_DIR = PROJECT_ROOT / "artifacts" / "models"

WF_MIN_SIDE_SUPPORT = 15
WF_MIN_VALID_FOLDS = 3
WF_PASS_F1 = 0.35
WF_STABLE_MEDIAN_F1 = 0.40
WF_STABLE_MIN_F1 = 0.20
WF_STABLE_PASS_RATE = 0.60


def get_model_artifacts_dir(artifacts_dir: Path | None = None) -> Path:
    return Path(artifacts_dir) if artifacts_dir is not None else DEFAULT_MODEL_ARTIFACTS_DIR


def _symbol_sort_key(symbol: str) -> tuple[bool, str]:
    return (symbol.startswith("__"), symbol)


def list_ml_artifact_batches(artifacts_dir: Path | None = None) -> list[str]:
    """Return artifact campaign directories that contain at least one symbol."""
    root = get_model_artifacts_dir(artifacts_dir)
    if not root.exists() or not root.is_dir():
        return []
    batches: list[str] = []
    for child in root.iterdir():
        if not child.is_dir():
            continue
        if any(
            grandchild.is_dir()
            and ((grandchild / "config.json").exists() or (grandchild / "metrics.json").exists())
            for grandchild in child.iterdir()
        ):
            batches.append(child.name)
    return sorted(batches, reverse=True)


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


def _build_governance_thresholds_summary(config_data: dict[str, Any], metrics_data: dict[str, Any]) -> dict[str, Any]:
    config_thresholds = config_data.get("threshold_optimization") if isinstance(config_data.get("threshold_optimization"), dict) else {}
    metrics_thresholds = metrics_data.get("threshold_optimization") if isinstance(metrics_data.get("threshold_optimization"), dict) else {}
    constraints = metrics_thresholds.get("constraints") if isinstance(metrics_thresholds.get("constraints"), dict) else {}
    selected_metrics = metrics_thresholds.get("selected_metrics") if isinstance(metrics_thresholds.get("selected_metrics"), dict) else {}
    selected_decision_threshold = config_data.get("selected_decision_threshold")
    if selected_decision_threshold is None:
        selected_decision_threshold = metrics_thresholds.get("selected_threshold")
    return {
        "enabled": bool(config_thresholds.get("enabled", False) or metrics_thresholds.get("enabled", False)),
        "selection_status": metrics_thresholds.get("selection_status"),
        "selected_threshold": selected_decision_threshold,
        "selected_business_score": metrics_thresholds.get("selected_business_score"),
        "min_action_rate": constraints.get("min_action_rate", config_thresholds.get("min_action_rate")),
        "max_action_rate": constraints.get("max_action_rate", config_thresholds.get("max_action_rate")),
        "min_precision_long": constraints.get("min_precision_long", config_thresholds.get("min_precision_long")),
        "selected_action_rate": selected_metrics.get("coverage_at_threshold"),
        "selected_precision_long": selected_metrics.get("precision_long"),
        "selected_model_eligible": bool(config_data.get("selected_model_eligible", False)),
        "selection_mode": config_data.get("selection_mode"),
        "selection_reason": config_data.get("selection_reason"),
    }


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if pd.notna(parsed) else None


def _selected_walk_forward_payload(
    config_data: dict[str, Any],
    metrics_data: dict[str, Any],
    selected_model: str | None,
) -> tuple[dict[str, Any], int | None, str]:
    """Résout le WF du champion servi, puis de son horizon sélectionné."""
    raw_horizon = config_data.get("selected_forecast_horizon")
    try:
        horizon = int(raw_horizon) if raw_horizon is not None else None
    except (TypeError, ValueError):
        horizon = None

    model = str(selected_model or "").strip().lower()
    baseline_key = {"lightgbm": "baseline_lightgbm", "catboost": "baseline_catboost"}.get(model)
    if baseline_key:
        baseline = metrics_data.get(baseline_key)
        if isinstance(baseline, dict):
            horizons = baseline.get("horizons")
            if isinstance(horizons, dict) and horizon is not None:
                horizon_payload = horizons.get(f"h{horizon}") or horizons.get(str(horizon))
                if isinstance(horizon_payload, dict) and isinstance(horizon_payload.get("walk_forward"), dict):
                    return horizon_payload["walk_forward"], horizon, f"{baseline_key}.horizons.h{horizon}.walk_forward"
            if isinstance(baseline.get("walk_forward"), dict):
                return baseline["walk_forward"], horizon, f"{baseline_key}.walk_forward"

    payload = metrics_data.get("walk_forward")
    if isinstance(payload, dict):
        return payload, horizon, "walk_forward"
    return {}, horizon, ""


def _estimated_side_support(split: dict[str, Any], side: str) -> int | None:
    explicit = _finite_float(split.get(f"support_{side}"))
    if explicit is not None:
        return max(0, int(round(explicit)))
    pct = _finite_float(split.get(f"true_{side}_pct"))
    samples = _finite_float(split.get("n_samples"))
    if samples is None:
        samples = _finite_float(split.get("test_rows"))
    if pct is None or samples is None:
        return None
    return max(0, int(round(samples * pct / 100.0)))


def _side_stability(folds: list[dict[str, Any]], side: str) -> dict[str, Any]:
    valid = [row for row in folds if row[f"{side}_valid"]]
    values = [float(row[f"f1_{side}"]) for row in valid]
    supports = [row[f"support_{side}"] for row in valid if row[f"support_{side}"] is not None]
    passing = sum(value >= WF_PASS_F1 for value in values)
    pass_rate = passing / len(values) if values else 0.0
    median = float(pd.Series(values).median()) if values else None
    minimum = min(values) if values else None
    stable = (
        len(values) >= WF_MIN_VALID_FOLDS
        and median is not None and median >= WF_STABLE_MEDIAN_F1
        and minimum is not None and minimum >= WF_STABLE_MIN_F1
        and pass_rate >= WF_STABLE_PASS_RATE
    )
    if len(values) < WF_MIN_VALID_FOLDS:
        status = "insufficient_folds"
        status_label = "⚪ Folds insuffisants"
    elif stable:
        status = "stable"
        status_label = "✅ Stable"
    else:
        status = "fragile"
        status_label = "⚠️ Fragile"
    return {
        "side": side.upper(),
        "status": status,
        "status_label": status_label,
        "valid_folds": len(values),
        "passing_folds": passing,
        "pass_rate": pass_rate,
        "f1_mean": float(pd.Series(values).mean()) if values else None,
        "f1_median": median,
        "f1_min": minimum,
        "f1_std": float(pd.Series(values).std(ddof=0)) if values else None,
        "support_total": int(sum(supports)) if supports else None,
    }


def build_champion_walk_forward_stability(
    config_data: dict[str, Any],
    metrics_data: dict[str, Any],
    selected_model: str | None,
) -> dict[str, Any]:
    """Construit le diagnostic de stabilité WF du champion/horizon effectivement servi."""
    payload, horizon, source = _selected_walk_forward_payload(config_data, metrics_data, selected_model)
    raw_splits = payload.get("splits") if isinstance(payload, dict) else None
    splits = [split for split in raw_splits if isinstance(split, dict)] if isinstance(raw_splits, list) else []
    fold_rows: list[dict[str, Any]] = []
    for split in splits:
        row: dict[str, Any] = {
            "fold": split.get("split_index"),
            "test_start": split.get("test_start_date"),
            "test_end": split.get("test_end_date"),
            "test_rows": int(split.get("test_rows")) if _finite_float(split.get("test_rows")) is not None else None,
            "n_samples": int(split.get("n_samples")) if _finite_float(split.get("n_samples")) is not None else None,
            "f1_macro": _finite_float(split.get("f1_macro")),
            "f1_long": _finite_float(split.get("f1_long")),
            "f1_short": _finite_float(split.get("f1_short")),
            "f1_flat": _finite_float(split.get("f1_flat")),
            "precision_long": _finite_float(split.get("precision_long")),
            "recall_long": _finite_float(split.get("recall_long")),
            "precision_short": _finite_float(split.get("precision_short")),
            "recall_short": _finite_float(split.get("recall_short")),
        }
        for side in ("long", "short"):
            support = _estimated_side_support(split, side)
            row[f"support_{side}"] = support
            row[f"{side}_valid"] = row[f"f1_{side}"] is not None and support is not None and support >= WF_MIN_SIDE_SUPPORT
        fold_rows.append(row)

    long_summary = _side_stability(fold_rows, "long")
    short_summary = _side_stability(fold_rows, "short")
    summary_rows = [long_summary, short_summary]
    if long_summary["status"] == "stable" and short_summary["status"] == "stable":
        overall_status = "long_short_stable"
        overall_label = "✅ LONG + SHORT stables"
    elif long_summary["status"] == "stable":
        overall_status = "long_only_stable"
        overall_label = "🟢 LONG stable uniquement"
    elif short_summary["status"] == "stable":
        overall_status = "short_only_stable"
        overall_label = "🔴 SHORT stable uniquement"
    elif not fold_rows:
        overall_status = "unavailable"
        overall_label = "⚪ Détail des folds indisponible"
    else:
        overall_status = "not_stable"
        overall_label = "⛔ Stabilité directionnelle non démontrée"

    return {
        "available": bool(fold_rows),
        "selected_model": selected_model,
        "selected_horizon": horizon,
        "source": source,
        "reported_n_splits": payload.get("n_splits") if isinstance(payload, dict) else None,
        "evaluated_folds": len(fold_rows),
        "overall_status": overall_status,
        "overall_label": overall_label,
        "long": long_summary,
        "short": short_summary,
        "summary_df": pd.DataFrame(summary_rows),
        "folds_df": pd.DataFrame(fold_rows),
        "thresholds": {
            "min_side_support": WF_MIN_SIDE_SUPPORT,
            "min_valid_folds": WF_MIN_VALID_FOLDS,
            "passing_f1": WF_PASS_F1,
            "stable_median_f1": WF_STABLE_MEDIAN_F1,
            "stable_min_f1": WF_STABLE_MIN_F1,
            "stable_pass_rate": WF_STABLE_PASS_RATE,
        },
    }


def _load_optional_artifact_json(path: Path) -> dict[str, Any]:
    data, _error = _read_json_file(path)
    return data or {}


def load_ml_artifact_report(symbol: str, artifacts_dir: Path | None = None) -> dict[str, Any]:
    root = get_model_artifacts_dir(artifacts_dir)
    symbol_dir = root / symbol
    config_path = symbol_dir / "config.json"
    metrics_path = symbol_dir / "metrics.json"
    attribution_summary_path = symbol_dir / "attribution_summary.json"

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
            "walk_forward_stability": build_champion_walk_forward_stability({}, {}, None),
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
    governance_thresholds = _build_governance_thresholds_summary(config_data, metrics_data)
    attribution_summary = _load_optional_artifact_json(attribution_summary_path) if attribution_summary_path.exists() else {}
    attribution_results_df = pd.DataFrame(attribution_summary.get("results") or []) if attribution_summary else pd.DataFrame()
    regime_rows = [
        {"regime": regime, **row}
        for regime, rows in (attribution_summary.get("regime_results") or {}).items()
        if isinstance(rows, list)
        for row in rows
        if isinstance(row, dict)
    ]
    attribution_regimes_df = pd.DataFrame(regime_rows)
    walk_forward_stability = build_champion_walk_forward_stability(
        config_data, metrics_data, selected_model
    )

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
        "governance_thresholds": governance_thresholds,
        "attribution_summary_path": attribution_summary_path,
        "attribution_summary": attribution_summary,
        "attribution_results_df": attribution_results_df,
        "attribution_regimes_df": attribution_regimes_df,
        "routes_df": routes_df,
        "ranking_df": _build_ranking_dataframe(metrics_data),
        "walk_forward_stability": walk_forward_stability,
    }

