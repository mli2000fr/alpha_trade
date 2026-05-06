"""Helpers transverses pour les payloads ``run_summary``.

Tous les modules qui produisent un ``run_summary`` (CLI, IHM, services) doivent
faire passer leur dictionnaire par :func:`attach_schema_version` afin de
garantir un champ ``schema_version`` versionné et des marqueurs IEX optionnels
homogènes.

Phase 1 du refactor (`prompt/refactor/plan.md`).
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Iterable, Mapping, MutableMapping

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
LIVE_PROGRESS_KEYS: tuple[str, ...] = (
    "progress_live",
    "progress_current",
    "progress_total",
    "progress_ratio",
    "progress_label",
    "progress_phase",
    "progress_unit",
    "progress_item",
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


def attach_live_progress(
    summary: Mapping[str, Any] | MutableMapping[str, Any] | None,
    *,
    current: int,
    total: int,
    label: str,
    phase: str | None = None,
    unit: str | None = None,
    item: str | None = None,
) -> dict[str, Any]:
    """Retourne un ``run_summary`` enrichi d'un état de progression live explicite."""
    payload = attach_schema_version(summary)
    normalized_total = max(int(total), 0)
    normalized_current = min(max(int(current), 0), normalized_total) if normalized_total > 0 else max(int(current), 0)
    payload["progress_live"] = True
    payload["progress_current"] = normalized_current
    payload["progress_total"] = normalized_total
    if normalized_total > 0:
        payload["progress_ratio"] = round(min(max(normalized_current / normalized_total, 0.0), 1.0), 4)
    payload["progress_label"] = str(label).strip()
    if phase:
        payload["progress_phase"] = str(phase).strip()
    if unit:
        payload["progress_unit"] = str(unit).strip()
    if item:
        payload["progress_item"] = str(item).strip()
    return payload


# ---------------------------------------------------------------------------
# Sprint S2 (A-017, A-023) — télémétrie ``data_source`` mixte.
# ---------------------------------------------------------------------------

#: Ratio minimal par défaut de la source dominante. Sous ce seuil, le check
#: :func:`build_data_source_mix_check` retourne ``status="warning"``.
DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO: float = 0.95


def aggregate_data_source_mix(
    counts: Mapping[str, Any] | Iterable[tuple[str, Any]] | None,
) -> dict[str, Any]:
    """Agrège un mapping ``{data_source: rows}`` en payload normalisé.

    Retourne ``{"counts": {...}, "ratios": {...}, "rows_total": N,
    "dominant_source": str | None, "dominant_ratio": float}`` — toutes
    les valeurs sont JSON-sérialisables. Les sources NULL/vides sont
    fusionnées sous la clé ``"unknown"``.
    """
    bag: Counter[str] = Counter()
    if counts is None:
        items: Iterable[tuple[str, Any]] = ()
    elif isinstance(counts, Mapping):
        items = counts.items()
    else:
        items = counts
    for src, value in items:
        try:
            n = int(value or 0)
        except (TypeError, ValueError):
            n = 0
        if n <= 0:
            continue
        key = (str(src).strip() if src is not None else "") or "unknown"
        bag[key] += n
    rows_total = int(sum(bag.values()))
    ratios: dict[str, float] = {}
    if rows_total > 0:
        ratios = {k: round(v / rows_total, 6) for k, v in bag.items()}
    if bag:
        dominant_source, dominant_count = bag.most_common(1)[0]
        dominant_ratio = round(dominant_count / rows_total, 6) if rows_total else 0.0
    else:
        dominant_source = None
        dominant_ratio = 0.0
    return {
        "counts": dict(bag),
        "ratios": ratios,
        "rows_total": rows_total,
        "dominant_source": dominant_source,
        "dominant_ratio": dominant_ratio,
    }


def build_data_source_mix_check(
    counts: Mapping[str, Any] | Iterable[tuple[str, Any]] | None,
    *,
    min_dominant_ratio: float = DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO,
) -> dict[str, Any]:
    """Construit la clé ``data_source_mix_check`` du run_summary.

    Statut :
    - ``"empty"``   si aucune ligne lue.
    - ``"warning"`` si ``dominant_ratio < min_dominant_ratio``.
    - ``"ok"``      sinon.
    """
    mix = aggregate_data_source_mix(counts)
    threshold = float(min_dominant_ratio)
    if mix["rows_total"] == 0:
        status = "empty"
    elif mix["dominant_ratio"] < threshold:
        status = "warning"
    else:
        status = "ok"
    return {
        "status": status,
        "min_dominant_ratio": threshold,
        **mix,
    }
