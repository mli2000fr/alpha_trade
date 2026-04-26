"""Helpers transverses pour les payloads ``run_summary``.

Tous les modules qui produisent un ``run_summary`` (CLI, IHM, services) doivent
faire passer leur dictionnaire par :func:`attach_schema_version` afin de
garantir un champ ``schema_version`` versionné et des marqueurs IEX optionnels
homogènes.

Phase 1 du refactor (`prompt/refactor/plan.md`).
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

#: Version courante du schéma ``run_summary`` (à incrémenter à chaque
#: modification incompatible du payload).
RUN_SUMMARY_SCHEMA_VERSION: int = 1

#: Clés "biais IEX" propagées à travers les ``run_summary`` quand elles sont
#: pertinentes (instrumentées dans ``dataIntegrityEngine`` puis transmises
#: aux étapes consommatrices).
IEX_BIAS_KEYS: tuple[str, ...] = (
    "symbols_zero_volume_30d",
    "stale_quote_pct",
    "stale_market_cap_pct",
)


def attach_schema_version(
    summary: Mapping[str, Any] | MutableMapping[str, Any] | None,
    *,
    version: int = RUN_SUMMARY_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Retourne une copie du ``summary`` enrichie de ``schema_version``.

    - Préserve le ``schema_version`` existant s'il est déjà fourni.
    - Idempotent : peut être appelé plusieurs fois sans effet de bord.
    """
    payload: dict[str, Any] = dict(summary or {})
    payload.setdefault("schema_version", int(version))
    return payload


def merge_iex_bias_counters(
    summary: MutableMapping[str, Any],
    counters: Mapping[str, Any] | None,
) -> None:
    """Fusionne les compteurs IEX (clé/valeur) dans ``summary`` *in-place*.

    Seules les clés listées dans :data:`IEX_BIAS_KEYS` sont propagées,
    pour éviter d'introduire silencieusement des champs non documentés.
    """
    if not counters:
        return
    for key in IEX_BIAS_KEYS:
        if key in counters and counters[key] is not None:
            summary[key] = counters[key]

