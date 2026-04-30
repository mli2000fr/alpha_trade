"""modelFactory/champion_selection.py — Gouvernance et sélection automatique du champion."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

from modelFactory.config import ChampionSelectionConfig


# Phase 4.2.e — quarantaine champion.
# Type d'un callback retournant (count_runs, first_completed_at | None) pour
# le couple (symbol, model_name). Découplé du db_registry pour faciliter
# les tests.
QuarantineLookup = Callable[[str, str], tuple[int, Optional[datetime]]]


def is_under_quarantine(
    model_name: str,
    symbol: str,
    *,
    min_runs: int,
    min_days: int,
    lookup: QuarantineLookup,
    now: Optional[datetime] = None,
) -> tuple[bool, str]:
    """Retourne ``(quarantined, reason)`` pour un (symbole, modèle).

    - ``min_runs == 0 and min_days == 0`` → jamais en quarantaine.
    - Sinon : sous quarantaine si **moins** de `min_runs` runs OU si la
      première complétion remonte à moins de `min_days` jours.
    """
    if min_runs <= 0 and min_days <= 0:
        return False, ""
    try:
        runs_count, first_completed_at = lookup(symbol, model_name)
    except Exception as exc:  # noqa: BLE001 - best-effort, registry indisponible
        return False, f"quarantine_lookup_failed:{exc}"
    if min_runs > 0 and runs_count < min_runs:
        return True, f"runs<{min_runs} (current={runs_count})"
    if min_days > 0:
        if first_completed_at is None:
            return True, f"days<{min_days} (no first_completed_at)"
        ref = now or datetime.now(timezone.utc)
        # Normaliser tz pour comparer
        if first_completed_at.tzinfo is None:
            first_completed_at = first_completed_at.replace(tzinfo=timezone.utc)
        elapsed = ref - first_completed_at
        if elapsed < timedelta(days=min_days):
            elapsed_days = elapsed.total_seconds() / 86400.0
            return True, f"days<{min_days} (elapsed={elapsed_days:.1f}d)"
    return False, ""


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
    *,
    quarantine_lookup: QuarantineLookup | None = None,
    symbol: str | None = None,
) -> dict[str, Any]:
    annotated = annotate_challengers(challengers, artifact_routes_models)
    default_model = champion_cfg.default_champion
    default_exists = default_model in annotated

    # Phase 4.2.e — annoter quarantaine sur tous les challengers complétés.
    quarantine_active = (
        (champion_cfg.min_runs > 0 or champion_cfg.min_days > 0)
        and quarantine_lookup is not None
        and symbol is not None
    )
    if quarantine_active:
        for model_name, result in annotated.items():
            if result.get("status") != "completed":
                continue
            quarantined, reason = is_under_quarantine(
                model_name,
                symbol,  # type: ignore[arg-type]
                min_runs=champion_cfg.min_runs,
                min_days=champion_cfg.min_days,
                lookup=quarantine_lookup,  # type: ignore[arg-type]
            )
            result["quarantined"] = bool(quarantined)
            if quarantined:
                result["quarantine_reason"] = reason
                # désactive l'éligibilité pour la sélection auto
                result["selection_eligible"] = False
                if not result.get("eligibility_reason"):
                    result["eligibility_reason"] = f"quarantine:{reason}"

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

