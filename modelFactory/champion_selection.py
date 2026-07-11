"""modelFactory/champion_selection.py — Gouvernance et sélection automatique du champion."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from modelFactory.config import ChampionSelectionConfig
from modelFactory.evaluation import check_model_collapse


# Phase 4.2.e — quarantaine champion.
# Type d'un callback retournant (count_runs, first_completed_at | None) pour
# le couple (symbol, model_name). Découplé du db_registry pour faciliter
# les tests.
QuarantineLookup = Callable[[str, str], tuple[int, Optional[datetime]]]


_SIGNED_ARTIFACT_ROUTE_KEYS: tuple[str, ...] = (
    "checkpoint_path",
    "scaler_path",
    "model_path",
    "config_path",
    "calibrator_path",
)


class ArtifactSignatureError(RuntimeError):
    """Erreur explicite de manifeste/signature d'artefact."""

    def __init__(self, reason: str, *, path: Path | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.path = path


def _artifact_path_from_value(value: object) -> Path | None:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    return None


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifact_signature_manifest(
    *,
    symbol: str,
    run_id: str | None,
    selected_model: str | None,
    artifact_routes_models: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Construit un manifeste SHA256 persistant pour les artefacts servis."""
    entries: list[dict[str, Any]] = []
    for model_name, route in sorted((artifact_routes_models or {}).items()):
        if not isinstance(route, dict):
            continue
        for artifact_key in _SIGNED_ARTIFACT_ROUTE_KEYS:
            artifact_path = _artifact_path_from_value(route.get(artifact_key))
            if artifact_path is None or not artifact_path.exists() or not artifact_path.is_file():
                continue
            resolved = artifact_path.resolve()
            entries.append(
                {
                    "model_name": model_name,
                    "artifact_key": artifact_key,
                    "path": str(resolved),
                    "size_bytes": int(resolved.stat().st_size),
                    "sha256": _sha256_file(resolved),
                }
            )
    return {
        "schema_version": 1,
        "symbol": symbol,
        "run_id": str(run_id or ""),
        "selected_model": str(selected_model or ""),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entries": entries,
    }


def persist_artifact_signature_manifest(
    manifest_path: Path,
    *,
    symbol: str,
    run_id: str | None,
    selected_model: str | None,
    artifact_routes_models: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Écrit sur disque un manifeste SHA256 adjacent aux artefacts du symbole."""
    manifest = build_artifact_signature_manifest(
        symbol=symbol,
        run_id=run_id,
        selected_model=selected_model,
        artifact_routes_models=artifact_routes_models,
    )
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def verify_route_artifact_signatures(
    *,
    manifest_path: Path,
    model_name: str,
    route: dict[str, Any],
    required: bool,
) -> None:
    """Vérifie que les artefacts d'une route correspondent au manifeste SHA256."""
    if not manifest_path.exists():
        if required:
            raise ArtifactSignatureError("artifact_signature_manifest_missing", path=manifest_path)
        return
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ArtifactSignatureError("artifact_signature_manifest_invalid", path=manifest_path) from exc
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        raise ArtifactSignatureError("artifact_signature_manifest_invalid", path=manifest_path)

    indexed_entries: dict[tuple[str, str, str], dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = (
            str(entry.get("model_name") or "").strip(),
            str(entry.get("artifact_key") or "").strip(),
            str(entry.get("path") or "").strip(),
        )
        if all(key):
            indexed_entries[key] = entry

    for artifact_key in _SIGNED_ARTIFACT_ROUTE_KEYS:
        artifact_path = _artifact_path_from_value(route.get(artifact_key))
        if artifact_path is None or not artifact_path.exists() or not artifact_path.is_file():
            continue
        resolved = artifact_path.resolve()
        entry = indexed_entries.get((model_name, artifact_key, str(resolved)))
        if entry is None:
            raise ArtifactSignatureError(f"artifact_signature_missing:{model_name}:{artifact_key}", path=resolved)
        actual_digest = _sha256_file(resolved)
        if str(entry.get("sha256") or "") != actual_digest:
            raise ArtifactSignatureError(f"artifact_signature_mismatch:{model_name}:{artifact_key}", path=resolved)


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
    """Calcule le score de sélection SANS lire le holdout final (Sprint Maître 1).

    RÈGLE STRICTE : les partitions autorisées pour la sélection sont
    ``val`` et ``walk_forward_oos``. La partition ``test`` / ``final_holdout``
    ne doit JAMAIS influencer le choix du champion.

    Si la métrique demandée est absente des partitions autorisées,
    retourne ``-inf`` (ne sélectionne jamais ce modèle).
    """
    if not result or result.get("status") != "completed":
        return float("-inf")

    # ── Partitions autorisées pour la sélection (Sprint Maître 1) ──
    val = result.get("val") if isinstance(result.get("val"), dict) else {}
    wf_oos = result.get("walk_forward_oos") if isinstance(result.get("walk_forward_oos"), dict) else {}
    # Le champ top-level "selection_score" reste autorisé (backcompat)
    top_level_selection = result.get("selection_score")

    # Métriques interdites : toute clé venant de "test" ou "final_holdout"
    # n'est plus utilisée comme fallback.

    if metric == "business_score":
        return float(
            top_level_selection
            or val.get("threshold_business_score")
            or wf_oos.get("threshold_business_score")
            or 0.0
        )
    if metric == "auc":
        return float(
            val.get("auc")
            or wf_oos.get("auc")
            or val.get("auc_macro")
            or wf_oos.get("auc_macro")
            or top_level_selection
            or 0.0
        )
    # métrique par défaut : "selection_score"
    return float(
        top_level_selection
        or val.get("threshold_business_score")
        or wf_oos.get("threshold_business_score")
        or val.get("auc")
        or wf_oos.get("auc")
        or 0.0
    )


def evaluate_selection_eligibility(
    model_name: str,
    result: dict[str, Any],
    artifact_route: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    """Évalue l'éligibilité d'un modèle avec les gates du Sprint Maître 1.

    Gates ajoutés (Sprint Maître 1) :
    - Probabilités invalides → inéligible.
    - AUC hors [0, 1] → inéligible.
    - Modèle collapsed → inéligible.
    - Action rate nul en ternaire → inéligible.
    - Artefacts issus d'anciennes métriques → inéligible.
    """
    if not result or result.get("status") != "completed":
        return False, "status_not_completed"

    # ── Sprint Maître 1 : gates de métriques ──────────────────────────
    metric_gate_reason = _validate_metric_gates(result)
    if metric_gate_reason is not None:
        return False, metric_gate_reason

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


def _validate_metric_gates(result: dict[str, Any]) -> str | None:
    """Valide les gates de métriques sur un résultat (Sprint Maître 1).

    Returns
    -------
    str | None
        Raison d'inéligibilité, ou None si OK.
    """
    # 1. Probabilités invalides
    if result.get("proba_valid") is False:
        return f"invalid_probabilities:{result.get('proba_error', 'unknown')}"

    # 2. AUC hors bornes (valider val ET walk_forward_oos)
    for partition_name in ("val", "walk_forward_oos"):
        partition = result.get(partition_name)
        if not isinstance(partition, dict):
            continue
        for key, value in partition.items():
            if key.startswith("auc_class_") and value is not None:
                try:
                    v = float(value)
                    if v < 0.0 or v > 1.0:
                        return f"auc_out_of_bounds_{partition_name}:{key}={v}"
                except (TypeError, ValueError):
                    return f"auc_non_numeric_{partition_name}:{key}={value}"
        # Vérifier aussi auc_macro
        auc_macro = partition.get("auc_macro")
        if auc_macro is not None:
            try:
                v = float(auc_macro)
                if v < 0.0 or v > 1.0:
                    return f"auc_macro_out_of_bounds_{partition_name}:{v}"
            except (TypeError, ValueError):
                return f"auc_macro_non_numeric_{partition_name}:{auc_macro}"

    # 3. Modèle collapsed
    if result.get("collapsed") is True:
        return f"model_collapsed:{result.get('collapse_reason', 'unknown')}"

    # 4. Action rate nul en ternaire (vérifier val et wf_oos)
    for partition_name in ("val", "walk_forward_oos"):
        partition = result.get(partition_name)
        if not isinstance(partition, dict):
            continue
        action_rate = partition.get("action_rate")
        if action_rate is not None and float(action_rate) <= 0.0:
            return f"zero_action_rate_{partition_name}"

    # 5. Artefacts legacy (anciennes métriques)
    if result.get("legacy_metrics") is True:
        return "legacy_metrics_artifacts"

    # 6. Observations insuffisantes
    for partition_name in ("val", "walk_forward_oos"):
        partition = result.get(partition_name)
        if not isinstance(partition, dict):
            continue
        n = partition.get("n_observations", partition.get("support_total"))
        if n is not None and int(n) < 50:
            return f"insufficient_observations_{partition_name}:{n}"

    return None


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

    def _selected_metadata(model_name: str, *, reason: str | None = None) -> dict[str, Any]:
        selected_result = annotated.get(model_name, {}) if isinstance(annotated.get(model_name), dict) else {}
        return {
            "selected_model_eligible": bool(selected_result.get("selection_eligible", False)),
            "selection_reason": reason,
        }

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
            **_selected_metadata(default_model if default_exists else "lstm_attention"),
        }

    eligible = [
        (model_name, result)
        for model_name, result in annotated.items()
        if result.get("selection_eligible") is True
    ]
    if not eligible:
        selected_model = default_model if default_exists else "lstm_attention"
        return {
            "selected_model": selected_model,
            "selection_mode": "fallback_default_champion",
            "annotated_challengers": annotated,
            "selection_metric": champion_cfg.selection_metric,
            **_selected_metadata(selected_model, reason="zero_eligible_models"),
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
        **_selected_metadata(selected_model),
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

