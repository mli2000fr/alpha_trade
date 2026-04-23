"""modelFactory/champion_selection.py — Gouvernance et sélection automatique du champion."""
from __future__ import annotations

from typing import Any

from modelFactory.config import ChampionSelectionConfig


def selection_score_from_result(result: dict[str, Any], metric: str = "selection_score") -> float:
    if not result or result.get("status") != "completed":
        return float("-inf")
    if metric == "business_score":
        return float(
            result.get("selection_score")
            or result.get("test", {}).get("threshold_business_score")
            or result.get("val", {}).get("threshold_business_score")
            or result.get("test", {}).get("auc")
            or 0.0
        )
    if metric == "auc":
        return float(
            result.get("test", {}).get("auc")
            or result.get("val", {}).get("auc")
            or result.get("selection_score")
            or 0.0
        )
    return float(
        result.get("selection_score")
        or result.get("test", {}).get("threshold_business_score")
        or result.get("test", {}).get("auc")
        or result.get("val", {}).get("threshold_business_score")
        or result.get("val", {}).get("auc")
        or 0.0
    )


def evaluate_selection_eligibility(
    model_name: str,
    result: dict[str, Any],
    artifact_route: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    if not result or result.get("status") != "completed":
        return False, "status_not_completed"
    route = artifact_route or {}
    backend = route.get("inference_backend")
    if model_name == "lstm_attention":
        if backend != "lstm_attention":
            return False, "inference_backend_missing"
        if not route.get("checkpoint_path") or not route.get("scaler_path"):
            return False, "artifact_path_missing"
        return True, None
    if model_name == "global_model":
        if backend != "global_tabular":
            return False, "inference_backend_missing"
        if not route.get("config_path") or not route.get("model_path"):
            return False, "artifact_path_missing"
        return True, None
    if model_name == "lightgbm":
        if backend != "lightgbm_tabular":
            return False, "inference_backend_missing"
        if not route.get("config_path") or not route.get("model_path"):
            return False, "artifact_path_missing"
        return True, None
    if model_name == "catboost":
        if backend != "catboost_tabular":
            return False, "inference_backend_missing"
        if not route.get("config_path") or not route.get("model_path"):
            return False, "artifact_path_missing"
        return True, None
    return False, "inference_not_supported"


def annotate_challengers(
    challengers: dict[str, dict[str, Any]],
    artifact_routes_models: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    annotated: dict[str, dict[str, Any]] = {}
    for model_name, result in challengers.items():
        route = artifact_routes_models.get(model_name, {})
        eligible, reason = evaluate_selection_eligibility(model_name, result, route)
        annotated[model_name] = {
            **result,
            "selection_eligible": eligible,
            "eligibility_reason": reason,
        }
    return annotated


def select_champion(
    challengers: dict[str, dict[str, Any]],
    artifact_routes_models: dict[str, dict[str, Any]],
    champion_cfg: ChampionSelectionConfig,
) -> dict[str, Any]:
    annotated = annotate_challengers(challengers, artifact_routes_models)
    default_model = champion_cfg.default_champion
    default_exists = default_model in annotated

    if not champion_cfg.enabled or not champion_cfg.allow_auto_selection:
        return {
            "selected_model": default_model if default_exists else "lstm_attention",
            "selection_mode": "default_champion",
            "annotated_challengers": annotated,
            "selection_metric": champion_cfg.selection_metric,
        }

    eligible = [
        (model_name, result)
        for model_name, result in annotated.items()
        if result.get("selection_eligible") is True
    ]
    if not eligible:
        return {
            "selected_model": default_model if default_exists else "lstm_attention",
            "selection_mode": "fallback_default_champion",
            "annotated_challengers": annotated,
            "selection_metric": champion_cfg.selection_metric,
        }

    selected_model, selected_result = max(
        eligible,
        key=lambda item: (
            selection_score_from_result(item[1], champion_cfg.selection_metric),
            1 if item[0] == default_model else 0,
        ),
    )
    return {
        "selected_model": selected_model,
        "selection_mode": "auto_selected_champion",
        "selection_metric": champion_cfg.selection_metric,
        "selection_score": selection_score_from_result(selected_result, champion_cfg.selection_metric),
        "annotated_challengers": annotated,
    }


def build_challenger_ranking(
    challengers: dict[str, dict[str, Any]],
    artifact_routes_models: dict[str, dict[str, Any]],
    champion_name: str,
    *,
    selection_mode: str,
    champion_cfg: ChampionSelectionConfig,
) -> list[dict[str, Any]]:
    annotated = annotate_challengers(challengers, artifact_routes_models)
    sortable = sorted(
        annotated.items(),
        key=lambda item: selection_score_from_result(item[1], champion_cfg.selection_metric),
        reverse=True,
    )
    ranking: list[dict[str, Any]] = []
    for idx, (model_name, result) in enumerate(sortable, start=1):
        status = result.get("status", "unknown")
        if model_name == champion_name and status == "completed":
            status = "selected_auto_champion" if selection_mode == "auto_selected_champion" else "selected_default_champion"
        ranking.append(
            {
                "rank": idx,
                "model_name": model_name,
                "selection_score": None if selection_score_from_result(result, champion_cfg.selection_metric) == float("-inf") else selection_score_from_result(result, champion_cfg.selection_metric),
                "status": status,
                "reason": result.get("reason"),
                "selection_eligible": result.get("selection_eligible", False),
                "eligibility_reason": result.get("eligibility_reason"),
            }
        )
    return ranking

