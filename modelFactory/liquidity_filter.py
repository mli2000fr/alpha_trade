"""modelFactory/liquidity_filter.py — Filtrage de l'univers par liquidité.

Supprime les symboles à faible volume / market cap avant l'entraînement
pour réduire le bruit dans les signaux ML.

Deux familles de filtres indépendantes :
1. Range High-Low quotidien ((high-low)/low*100) — proxy de volatilité intraday
   (100% de couverture via stock_bars_daily).
2. Spread bid-ask réel (spread_bps) — coût d'exécution mesuré
   (couverture partielle via stock_quote_snapshots, fallback configurable).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)

# ── Seuils de liquidité (paramétrables) ──
DEFAULT_MIN_AVG_VOLUME_20D = 500_000    # 500k shares/jour
DEFAULT_MIN_MARKET_CAP = 500_000_000     # 500M$
DEFAULT_MAX_MARKET_CAP = 0               # 0 = pas de limite, >0 exclut mega caps
DEFAULT_MAX_AVG_HIGH_LOW_RANGE_PCT = 5.0  # 5% max d'amplitude High-Low quotidienne moyenne
DEFAULT_MIN_DAILY_DOLLAR_VOLUME = 0       # 0 = pas de filtre, >0 = volume quotidien min en $
DEFAULT_MIN_PRICE = 0.0                   # 0 = pas de filtre, >0 = prix minimum (dernier close)

# ── Filtre spread bid-ask réel (stock_quote_snapshots) ──
DEFAULT_MAX_SPREAD_BPS = 40.0             # 40 bps = 0.40% de spread bid-ask max
# 0 = désactive le filtre spread. Cohérent avec STRICT_SWING_CASH_FILTERS.max_spread_bps.
DEFAULT_SPREAD_FALLBACK_MODE: Literal["pass", "reject", "warn_only"] = "pass"
# - "pass"      : si spread_bps absent → on laisse passer (best-effort)
# - "reject"    : si spread_bps absent → on rejette (strict, réduit l'univers)
# - "warn_only" : comme "pass" mais log un warning si >5% des symboles sans quote
DEFAULT_SPREAD_MAX_QUOTE_AGE_DAYS = 5     # âge max d'une quote pour être considérée fraîche

_LIQUIDITY_QUERY = """
WITH symbol_bars AS (
    SELECT
        symbol,
        AVG(CASE WHEN date >= :lookback_start THEN volume ELSE NULL END) AS avg_volume_20d,
        AVG(CASE WHEN date >= :lookback_start THEN close * volume ELSE NULL END) AS avg_dollar_volume_20d,
        AVG(CASE WHEN date >= :lookback_start AND low > 0 THEN (high - low) / low * 100 ELSE NULL END) AS avg_high_low_range_pct,
        MAX(CASE WHEN date >= :lookback_start THEN close * volume ELSE NULL END) AS max_dollar_volume,
        COUNT(CASE WHEN date >= :lookback_start THEN 1 ELSE NULL END) AS nb_days
    FROM stock_bars_daily
    WHERE symbol IN :symbols_placeholder
      AND date <= :end_date
    GROUP BY symbol
),
last_close AS (
    SELECT symbol, close AS last_close
    FROM (
        SELECT symbol, close,
               ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY date DESC) AS rn
        FROM stock_bars_daily
        WHERE symbol IN :symbols_placeholder2
          AND date <= :end_date
    ) ranked
    WHERE rn = 1
)
SELECT
    sb.symbol,
    sb.avg_volume_20d,
    sb.avg_dollar_volume_20d,
    sb.avg_high_low_range_pct,
    sb.nb_days,
    lc.last_close,
    CASE
        WHEN sb.avg_volume_20d IS NULL OR sb.avg_volume_20d < :min_volume THEN 'volume_insuffisant'
        WHEN :min_daily_dvol > 0 AND (sb.avg_dollar_volume_20d IS NULL OR sb.avg_dollar_volume_20d < :min_daily_dvol) THEN 'dollar_volume_quotidien_insuffisant'
        WHEN sb.avg_dollar_volume_20d IS NULL OR sb.avg_dollar_volume_20d < :min_dollar_volume THEN 'market_cap_insuffisant'
        WHEN :max_dollar_volume > 0 AND (sb.avg_dollar_volume_20d IS NULL OR sb.avg_dollar_volume_20d > :max_dollar_volume) THEN 'dollar_volume_eleve'
        WHEN :min_price > 0 AND (lc.last_close IS NULL OR lc.last_close < :min_price) THEN 'prix_insuffisant'
        WHEN sb.avg_high_low_range_pct IS NULL OR sb.avg_high_low_range_pct > :max_high_low_range THEN 'range_eleve'
        WHEN sb.nb_days IS NULL OR sb.nb_days < :min_days THEN 'historique_insuffisant'
        ELSE 'ok'
    END AS reason
FROM symbol_bars sb
LEFT JOIN last_close lc ON lc.symbol = sb.symbol
WHERE sb.avg_volume_20d < :min_volume
   OR (:min_daily_dvol > 0 AND sb.avg_dollar_volume_20d < :min_daily_dvol)
   OR sb.avg_dollar_volume_20d < :min_dollar_volume
   OR (:max_dollar_volume > 0 AND sb.avg_dollar_volume_20d > :max_dollar_volume)
   OR (:min_price > 0 AND (lc.last_close IS NULL OR lc.last_close < :min_price))
   OR sb.avg_high_low_range_pct > :max_high_low_range
   OR sb.nb_days < :min_days
ORDER BY CASE WHEN avg_volume_20d IS NULL THEN 1 ELSE 0 END, avg_volume_20d ASC
"""


def filter_symbols_by_liquidity(
    engine: Engine,
    symbols: list[str],
    *,
    end_date: date | None = None,
    min_avg_volume_20d: int = DEFAULT_MIN_AVG_VOLUME_20D,
    min_market_cap: float = DEFAULT_MIN_MARKET_CAP,
    max_market_cap: float = DEFAULT_MAX_MARKET_CAP,
    max_avg_high_low_range_pct: float = DEFAULT_MAX_AVG_HIGH_LOW_RANGE_PCT,
    min_daily_dollar_volume: float = DEFAULT_MIN_DAILY_DOLLAR_VOLUME,
    min_price: float = DEFAULT_MIN_PRICE,
    min_days: int = 10,
    # ── Filtre spread bid-ask réel ──
    max_spread_bps: float = DEFAULT_MAX_SPREAD_BPS,
    spread_fallback_mode: str = DEFAULT_SPREAD_FALLBACK_MODE,
    spread_max_quote_age_days: int = DEFAULT_SPREAD_MAX_QUOTE_AGE_DAYS,
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
    max_avg_high_low_range_pct : float
        Amplitude High-Low quotidienne moyenne maximale (en %).
        Basé sur (high-low)/low*100 — PAS le spread bid-ask.
    min_days : int
        Nombre minimum de jours de données requis.
    max_spread_bps : float
        Spread bid-ask max en points de base (0 = désactive).
        Basé sur stock_quote_snapshots.spread_bps (données réelles).
        Ex: 40 = 0.40%. Cohérent avec STRICT_SWING_CASH_FILTERS.
    spread_fallback_mode : str
        Comportement si spread_bps absent pour un symbole :
        - "pass" : laisse passer (best-effort)
        - "reject" : rejette le symbole (strict)
        - "warn_only" : comme "pass" + warning si couverture < 95%
    spread_max_quote_age_days : int
        Âge max d'une quote pour être considérée valide.

    Returns
    -------
    tuple[list[str], dict]
        - Liste des symboles filtrés (ceux à EXCLURE)
        - Dictionnaire de diagnostic avec les détails par symbole
    """
    if not symbols:
        return [], {"filtered_count": 0, "details": {}}

    lookback_start = (end_date or date.today()) - timedelta(days=60)

    # Construire les placeholders IN dynamiquement (MySQL ne supporte pas ANY(:array))
    sym_placeholders = ", ".join(f":sym_{i}" for i in range(len(symbols)))
    query = _LIQUIDITY_QUERY.replace(":symbols_placeholder2", f"({sym_placeholders})")
    query = query.replace(":symbols_placeholder", f"({sym_placeholders})")

    params: dict[str, Any] = {
        f"sym_{i}": s for i, s in enumerate(symbols)
    }
    params.update({
        "lookback_start": lookback_start,
        "end_date": end_date or date.today(),
        "min_volume": min_avg_volume_20d,
        "min_dollar_volume": min_market_cap / 20,  # proxy: cap ~20j de dollar volume
        "max_dollar_volume": max_market_cap / 20 if max_market_cap > 0 else 0,
        "max_high_low_range": max_avg_high_low_range_pct,
        "min_daily_dvol": min_daily_dollar_volume,
        "min_price": min_price,
        "min_days": min_days,
    })

    try:
        with engine.connect() as conn:
            rows = conn.execute(text(query), params).fetchall()
    except Exception as exc:
        LOGGER.warning(
            "liquidity_filter: query failed, skipping filter: %s", exc,
        )
        return [], {"filtered_count": 0, "details": {}, "error": str(exc)}

    filtered: dict[str, str] = {}

    if not rows:
        LOGGER.info("liquidity_filter: all %d symbols pass range/volume check", len(symbols))
    else:
        for row in rows:
            sym = str(row.symbol)
            reason = str(row.reason)
            filtered[sym] = reason

        # Log des 5 premiers filtrés pour diagnostic
        _sample = rows[:5]
        _parts: list[str] = []
        for r in _sample:
            _vol = f"{r.avg_volume_20d:.0f}" if r.avg_volume_20d is not None else "NULL"
            _dvol = f"{r.avg_dollar_volume_20d:.0f}" if r.avg_dollar_volume_20d is not None else "NULL"
            _range = f"{r.avg_high_low_range_pct:.2f}%" if r.avg_high_low_range_pct is not None else "NULL"
            _days = r.nb_days if r.nb_days is not None else "NULL"
            _parts.append(f"{r.symbol}(vol={_vol}, dvol={_dvol}, range={_range}, days={_days})→{r.reason}")
        LOGGER.info("liquidity_filter: sample filtered: %s", ", ".join(_parts))
        LOGGER.info(
            "liquidity_filter: %d/%d symbols filtered (min_vol=%d min_dvol=%.0f min_daily_dvol=%.0f max_dvol=%.0f min_price=%.0f max_range=%.1f%%)",
            len(filtered), len(symbols),
            min_avg_volume_20d, min_market_cap, min_daily_dollar_volume, max_market_cap, min_price,
            max_avg_high_low_range_pct,
        )

        # Log détaillé en DEBUG
        if LOGGER.isEnabledFor(logging.DEBUG):
            for sym, reason in sorted(filtered.items()):
                LOGGER.debug("liquidity_filter: %s → %s", sym, reason)

    # ── Filtre spread bid-ask réel (stock_quote_snapshots) ──────────────
    spread_stats: dict[str, Any] = {"enabled": False}
    if max_spread_bps > 0:
        spread_stats = _apply_spread_filter(
            engine,
            symbols,
            filtered,
            end_date=end_date or date.today(),
            max_spread_bps=max_spread_bps,
            fallback_mode=spread_fallback_mode,
            max_quote_age_days=spread_max_quote_age_days,
        )
        # Fusionner les exclus du spread dans filtered
        for sym, reason in spread_stats.get("newly_filtered", {}).items():
            if sym not in filtered:
                filtered[sym] = reason

    excluded = list(filtered.keys())

    return excluded, {
        "filtered_count": len(excluded),
        "kept_count": len(symbols) - len(excluded),
        "total_requested": len(symbols),
        "thresholds": {
            "min_avg_volume_20d": min_avg_volume_20d,
            "min_market_cap_proxy": min_market_cap,
            "max_avg_high_low_range_pct": max_avg_high_low_range_pct,
            "min_days": min_days,
            "lookback_start": lookback_start.isoformat(),
            "max_spread_bps": max_spread_bps,
            "spread_fallback_mode": spread_fallback_mode,
            "spread_max_quote_age_days": spread_max_quote_age_days,
        },
        "spread_diagnostics": spread_stats,
        "details": filtered,
    }


# ── Helper : filtre spread bid-ask réel ─────────────────────────────────────

_SPREAD_QUERY = """
SELECT q.symbol, q.spread_bps, q.quote_date
FROM stock_quote_snapshots q
INNER JOIN (
    SELECT symbol, MAX(quote_date) AS max_date
    FROM stock_quote_snapshots
    WHERE symbol IN :symbols_placeholder
      AND quote_date BETWEEN :min_quote_date AND :end_date
    GROUP BY symbol
) latest ON q.symbol = latest.symbol AND q.quote_date = latest.max_date
"""


def _apply_spread_filter(
    engine: Engine,
    symbols: list[str],
    already_filtered: dict[str, str],
    *,
    end_date: date,
    max_spread_bps: float,
    fallback_mode: str,
    max_quote_age_days: int,
) -> dict[str, Any]:
    """Applique le filtre spread bid-ask réel (stock_quote_snapshots.spread_bps).

    Returns
    -------
    dict avec :
    - enabled: bool
    - total_checked: int
    - spread_available: int   (symboles avec une quote fraîche)
    - spread_missing: int     (symboles sans quote ou quote trop vieille)
    - spread_ok: int          (spread ≤ seuil)
    - spread_high: int        (spread > seuil)
    - newly_filtered: dict    (symboles ajoutés aux exclus)
    - coverage_pct: float
    """
    if max_spread_bps <= 0:
        return {"enabled": False}

    sym_placeholders = ", ".join(f":sym_{i}" for i in range(len(symbols)))
    query = _SPREAD_QUERY.replace(":symbols_placeholder", f"({sym_placeholders})")

    min_quote_date = end_date - timedelta(days=max(max_quote_age_days, 0))
    params: dict[str, Any] = {
        f"sym_{i}": s for i, s in enumerate(symbols)
    }
    params["end_date"] = end_date
    params["min_quote_date"] = min_quote_date

    newly_filtered: dict[str, str] = {}
    spread_available = 0
    spread_missing = 0
    spread_ok = 0
    spread_high = 0

    try:
        with engine.connect() as conn:
            quote_rows = conn.execute(text(query), params).fetchall()
    except Exception as exc:
        LOGGER.warning(
            "liquidity_filter: spread query failed, skipping spread filter: %s", exc,
        )
        return {"enabled": True, "error": str(exc), "newly_filtered": {}}

    # Indexer les spreads par symbole
    spread_by_symbol: dict[str, float | None] = {s: None for s in symbols}
    for row in quote_rows:
        spread_by_symbol[str(row.symbol)] = (
            float(row.spread_bps) if row.spread_bps is not None else None
        )

    for sym in symbols:
        # Ne pas ré-évaluer les symboles déjà filtrés par un autre critère
        if sym in already_filtered:
            continue

        spread_val = spread_by_symbol.get(sym)

        if spread_val is None:
            spread_missing += 1
            if fallback_mode == "reject":
                newly_filtered[sym] = "spread_inconnu"
            # "pass" et "warn_only" : on laisse passer
            continue

        spread_available += 1
        if spread_val > max_spread_bps:
            spread_high += 1
            newly_filtered[sym] = "spread_eleve"
        else:
            spread_ok += 1

    total_checked = len(symbols) - len(already_filtered)
    coverage_pct = (spread_available / total_checked * 100.0) if total_checked > 0 else 100.0

    # Log synthétique
    LOGGER.info(
        "liquidity_filter: spread bid-ask | checked=%d available=%d missing=%d "
        "ok=%d high=%d newly_filtered=%d mode=%s max=%d bps coverage=%.1f%%",
        total_checked, spread_available, spread_missing,
        spread_ok, spread_high, len(newly_filtered),
        fallback_mode, int(max_spread_bps), coverage_pct,
    )

    # Mode warn_only : alerter si couverture insuffisante
    if fallback_mode == "warn_only" and coverage_pct < 95.0 and total_checked > 0:
        LOGGER.warning(
            "liquidity_filter: spread bid-ask coverage faible (%.1f%% < 95%%). "
            "%d symboles sur %d sans quote fraîche. "
            "Vérifiez sync_latest_quotes ou passez en fallback_mode='reject'.",
            coverage_pct, spread_missing, total_checked,
        )

    # Log détaillé des 5 premiers spread_eleve
    if spread_high > 0:
        _high_samples = [
            f"{s}({spread_by_symbol.get(s, '?'):.0f} bps)"
            for s in list(newly_filtered.keys())[:5]
            if newly_filtered.get(s) == "spread_eleve"
        ]
        if _high_samples:
            LOGGER.info(
                "liquidity_filter: spread_eleve sample (max=%d bps): %s",
                int(max_spread_bps), ", ".join(_high_samples),
            )

    return {
        "enabled": True,
        "total_checked": total_checked,
        "spread_available": spread_available,
        "spread_missing": spread_missing,
        "spread_ok": spread_ok,
        "spread_high": spread_high,
        "newly_filtered": newly_filtered,
        "coverage_pct": round(coverage_pct, 1),
        "max_spread_bps": max_spread_bps,
        "fallback_mode": fallback_mode,
    }
