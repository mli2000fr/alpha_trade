"""Sprint S2 (A-017, A-023) — santé/homogénéité des sources de barres.

Au démarrage du screener et du selector on requête la table
``stock_bars_daily`` pour vérifier que la fenêtre récente provient bien
majoritairement d'une seule source (``data_source``). Sous le seuil
``min_dominant_ratio`` (95 % par défaut) un WARNING est loggé et le
``run_summary`` est enrichi de la clé ``data_source_mix_check``.

Le module est défensif : toute exception SQL est convertie en payload
``status="unavailable"`` afin de ne jamais bloquer le pipeline.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from core.run_summary import (
    DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO,
    build_data_source_mix_check,
)

LOGGER = logging.getLogger(__name__)

DEFAULT_RECENT_DAYS: int = 30


def _resolve_threshold_from_config(default: float) -> float:
    try:
        from common.config_loader import load_config

        cfg = load_config() or {}
        section = cfg.get("market_data") or {}
        value = section.get("data_source_min_dominant_ratio", default)
        return float(value)
    except Exception:
        return float(default)


def fetch_data_source_counts(
    engine: Engine,
    *,
    recent_days: int = DEFAULT_RECENT_DAYS,
) -> dict[str, int]:
    """Retourne ``{data_source: row_count}`` sur la fenêtre récente.

    Les lignes ``data_source`` NULL sont normalisées sous ``"unknown"``.
    """
    stmt = text(
        """
        SELECT COALESCE(NULLIF(TRIM(data_source), ''), 'unknown') AS source,
               COUNT(*) AS rows_n
        FROM stock_bars_daily
        WHERE `date` >= (CURRENT_DATE - INTERVAL :recent_days DAY)
        GROUP BY source
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(stmt, {"recent_days": int(recent_days)}).fetchall()
    return {str(src): int(n or 0) for src, n in rows}


def check_data_source_homogeneity(
    engine: Engine,
    *,
    min_dominant_ratio: float | None = None,
    recent_days: int = DEFAULT_RECENT_DAYS,
    log_warning: bool = True,
) -> dict[str, Any]:
    """Calcule ``data_source_mix_check`` à partir des barres récentes.

    Tolère l'absence de connexion / table : retourne alors
    ``{"status": "unavailable", ...}``.
    """
    threshold = (
        float(min_dominant_ratio)
        if min_dominant_ratio is not None
        else _resolve_threshold_from_config(DEFAULT_DATA_SOURCE_MIN_DOMINANT_RATIO)
    )
    try:
        counts = fetch_data_source_counts(engine, recent_days=recent_days)
    except Exception as exc:
        LOGGER.warning(
            "check_data_source_homogeneity indisponible (%s) — pipeline continue.",
            exc,
        )
        return {
            "status": "unavailable",
            "min_dominant_ratio": threshold,
            "counts": {},
            "ratios": {},
            "rows_total": 0,
            "dominant_source": None,
            "dominant_ratio": 0.0,
            "error": str(exc),
        }

    payload = build_data_source_mix_check(counts, min_dominant_ratio=threshold)
    payload["recent_days"] = int(recent_days)
    if log_warning and payload["status"] == "warning":
        LOGGER.warning(
            "Mix data_source non homogene | dominant=%s ratio=%.2f%% < seuil=%.2f%% "
            "| counts=%s (fenetre %sj) — Sprint S2 A-023",
            payload.get("dominant_source"),
            float(payload.get("dominant_ratio", 0.0)) * 100.0,
            threshold * 100.0,
            payload.get("counts"),
            recent_days,
        )
    elif payload["status"] == "empty":
        LOGGER.warning(
            "Aucune barre stock_bars_daily sur la fenetre %sj — check data_source ignore.",
            recent_days,
        )
    return payload


__all__ = [
    "DEFAULT_RECENT_DAYS",
    "check_data_source_homogeneity",
    "fetch_data_source_counts",
]

