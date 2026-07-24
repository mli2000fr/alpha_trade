"""modelFactory/liquidity_filter.py — Filtrage de l'univers par liquidité.

Supprime les symboles à faible volume / market cap avant l'entraînement
pour réduire le bruit dans les signaux ML.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)

# ── Seuils de liquidité (paramétrables) ──
DEFAULT_MIN_AVG_VOLUME_20D = 500_000    # 500k shares/jour
DEFAULT_MIN_MARKET_CAP = 500_000_000     # 500M$
DEFAULT_MAX_AVG_SPREAD_PCT = 0.5         # 0.5%

_LIQUIDITY_QUERY = """
WITH symbol_bars AS (
    SELECT
        symbol,
        AVG(volume) FILTER (WHERE date >= :lookback_start) AS avg_volume_20d,
        AVG(close * volume) FILTER (WHERE date >= :lookback_start) AS avg_dollar_volume_20d,
        AVG(CASE WHEN low > 0 THEN (high - low) / low * 100 ELSE NULL END)
            FILTER (WHERE date >= :lookback_start) AS avg_spread_pct,
        MAX(close * volume) FILTER (WHERE date >= :lookback_start) AS max_dollar_volume,
        COUNT(*) FILTER (WHERE date >= :lookback_start) AS nb_days
    FROM stock_bars_daily
    WHERE symbol = ANY(:symbols)
      AND date <= :end_date
    GROUP BY symbol
)
SELECT
    symbol,
    avg_volume_20d,
    avg_dollar_volume_20d,
    avg_spread_pct,
    nb_days,
    CASE
        WHEN avg_volume_20d IS NULL OR avg_volume_20d < :min_volume THEN 'volume_insuffisant'
        WHEN avg_dollar_volume_20d IS NULL OR avg_dollar_volume_20d < :min_dollar_volume THEN 'dollar_volume_insuffisant'
        WHEN avg_spread_pct IS NULL OR avg_spread_pct > :max_spread THEN 'spread_eleve'
        WHEN nb_days IS NULL OR nb_days < :min_days THEN 'historique_insuffisant'
        ELSE 'ok'
    END AS reason
FROM symbol_bars
WHERE avg_volume_20d < :min_volume
   OR avg_dollar_volume_20d < :min_dollar_volume
   OR avg_spread_pct > :max_spread
   OR nb_days < :min_days
ORDER BY avg_volume_20d ASC NULLS LAST
"""


def filter_symbols_by_liquidity(
    engine: Engine,
    symbols: list[str],
    *,
    end_date: date | None = None,
    min_avg_volume_20d: int = DEFAULT_MIN_AVG_VOLUME_20D,
    min_market_cap: float = DEFAULT_MIN_MARKET_CAP,
    max_avg_spread_pct: float = DEFAULT_MAX_AVG_SPREAD_PCT,
    min_days: int = 10,
) -> tuple[list[str], dict[str, Any]]:
    """Filtre les symboles selon des critères de liquidité.

    Parameters
    ----------
    engine : Engine
        Connexion SQLAlchemy.
    symbols : list[str]
        Liste des symboles à filtrer.
    end_date : date | None
        Date de fin pour le calcul des moyennes (défaut : aujourd'hui).
    min_avg_volume_20d : int
        Volume quotidien moyen minimum sur 20 jours.
    min_market_cap : float
        Market cap minimum estimé (via prix × volume).
        On utilise le dollar volume comme proxy.
    max_avg_spread_pct : float
        Spread journalier moyen maximum (en %).
    min_days : int
        Nombre minimum de jours de données requis.

    Returns
    -------
    tuple[list[str], dict]
        - Liste des symboles filtrés (ceux à EXCLURE)
        - Dictionnaire de diagnostic avec les détails par symbole
    """
    if not symbols:
        return [], {"filtered_count": 0, "details": {}}

    lookback_start = (end_date or date.today()) - timedelta(days=60)

    params = {
        "symbols": symbols,
        "lookback_start": lookback_start,
        "end_date": end_date or date.today(),
        "min_volume": min_avg_volume_20d,
        "min_dollar_volume": min_market_cap / 20,  # proxy: cap ~20j de dollar volume
        "max_spread": max_avg_spread_pct,
        "min_days": min_days,
    }

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(_LIQUIDITY_QUERY), params).fetchall()
    except Exception as exc:
        LOGGER.warning(
            "liquidity_filter: query failed, skipping filter: %s", exc,
        )
        return [], {"filtered_count": 0, "details": {}, "error": str(exc)}

    if not rows:
        LOGGER.info("liquidity_filter: all %d symbols pass liquidity check", len(symbols))
        return [], {"filtered_count": 0, "details": {}}

    filtered: dict[str, str] = {}
    for row in rows:
        sym = str(row.symbol)
        reason = str(row.reason)
        filtered[sym] = reason

    excluded = list(filtered.keys())
    LOGGER.info(
        "liquidity_filter: %d/%d symbols filtered (min_vol=%d min_dvol=%.0f max_spread=%.1f%%)",
        len(excluded), len(symbols),
        min_avg_volume_20d, min_market_cap, max_avg_spread_pct,
    )

    # Log détaillé en DEBUG
    if LOGGER.isEnabledFor(logging.DEBUG):
        for sym, reason in sorted(filtered.items()):
            LOGGER.debug("liquidity_filter: %s → %s", sym, reason)

    return excluded, {
        "filtered_count": len(excluded),
        "kept_count": len(symbols) - len(excluded),
        "total_requested": len(symbols),
        "thresholds": {
            "min_avg_volume_20d": min_avg_volume_20d,
            "min_market_cap_proxy": min_market_cap,
            "max_avg_spread_pct": max_avg_spread_pct,
            "min_days": min_days,
            "lookback_start": lookback_start.isoformat(),
        },
        "details": filtered,
    }
