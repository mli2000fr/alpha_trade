"""Contrat partagé d'éligibilité des champions directionnels.

Les artefacts antérieurs à l'introduction de ``selected_model_eligible`` restent
lisibles : seule une valeur explicitement fausse rend une branche inservable.
Les nouveaux entraînements écrivent toujours ce champ explicitement.
"""
from __future__ import annotations

from typing import Any, Mapping


def _explicit_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def selected_model_is_eligible(config: Mapping[str, Any] | None) -> bool:
    """Évalue un ``config.json`` avec compatibilité des anciens artefacts."""
    payload = config if isinstance(config, Mapping) else {}
    explicit = _explicit_bool(payload.get("selected_model_eligible"))
    return True if explicit is None else explicit


def training_result_is_servable(metrics: Mapping[str, Any] | None) -> bool:
    """Évalue l'éligibilité enregistrée dans les métriques d'un TrainResult."""
    payload = metrics if isinstance(metrics, Mapping) else {}
    explicit = _explicit_bool(payload.get("selected_model_eligible"))
    if explicit is not None:
        return explicit
    champion = payload.get("champion")
    if isinstance(champion, Mapping):
        explicit = _explicit_bool(champion.get("selected_model_eligible"))
        if explicit is not None:
            return explicit
    return True
