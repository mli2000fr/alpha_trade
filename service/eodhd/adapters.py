"""Adaptateurs EODHD -> schémas DB Alpha Trade.

Plan §5.4. Trois responsabilités :

1. **Reconstruction split-only** :
   les barres EODHD sont fournies en ``open/high/low/close`` *brutes*
   (non ajustées) + ``adjusted_close`` *split + dividendes*. Le projet stocke
   des barres ``data_adjustment='split'`` (split-only). On reconstruit donc
   l'OHLCV split-only à partir des splits historiques.

2. **Mapping vers ``stock_bars_daily``** : ``to_stock_bars_daily_row``.

3. **Mapping vers ``stock_bars`` (timeframe='1D')** : ``to_stock_bars_row``.

Le delta close vs adjusted_close est utilisable comme **fallback splits**
quand l'endpoint ``/splits/`` n'est pas accessible (cf. phase1_findings.md
Option B). La fonction :func:`infer_splits_from_adjusted_close` couvre ce cas.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Iterable

LOGGER = logging.getLogger(__name__)

#: Convention de timestamp pour ``stock_bars.timestamp`` (DATETIME naïf NY).
#: Alpaca normalise les barres 1D à l'open RTH (09:30 America/New_York) -- cf.
#: ``import_alpaca_bar._normalize_bar_timestamp``. EODHD écrit avec la **même**
#: convention pour éviter les doublons sur la clé unique
#: ``(symbol, timeframe, timestamp)`` lorsqu'on coexiste avec des barres Alpaca.
US_RTH_OPEN_HOUR_NY = 9
US_RTH_OPEN_MINUTE_NY = 30
# Conservés pour rétrocompat tests éventuels.
US_CLOSE_UTC_HOUR = US_RTH_OPEN_HOUR_NY
US_CLOSE_UTC_MINUTE = US_RTH_OPEN_MINUTE_NY

#: data_source / data_adjustment écrits par l'adapter (cf. plan §4.2).
DATA_SOURCE_EODHD = "eodhd_eod"
DATA_ADJUSTMENT_SPLIT = "split"


# ---------------------------------------------------------------------------
# Splits
# ---------------------------------------------------------------------------


def parse_split_ratio(value: Any) -> float:
    """Parse ``"10/1"`` -> ``10.0``. Lève :class:`ValueError` si invalide.

    Tolère aussi un float déjà parsé.
    """
    if value is None:
        raise ValueError("split ratio None")
    if isinstance(value, (int, float)):
        ratio = float(value)
        if ratio <= 0:
            raise ValueError(f"split ratio invalide: {value!r}")
        return ratio
    text = str(value).strip()
    if not text:
        raise ValueError("split ratio vide")
    if "/" in text:
        num, _, denom = text.partition("/")
        try:
            n = float(num)
            d = float(denom)
        except ValueError as exc:
            raise ValueError(f"split ratio invalide: {value!r}") from exc
        if d == 0:
            raise ValueError(f"split ratio division par 0: {value!r}")
        return n / d
    try:
        ratio = float(text)
    except ValueError as exc:
        raise ValueError(f"split ratio invalide: {value!r}") from exc
    if ratio <= 0:
        raise ValueError(f"split ratio invalide: {value!r}")
    return ratio


def cumulative_split_factor(splits: Iterable[dict], target_date: str) -> float:
    """Facteur cumulé des splits **strictement postérieurs** à ``target_date``.

    Convention split-only Alpha Trade : pour ramener une barre ancienne au
    prix courant ajusté des splits, on divise les prix par ce facteur et on
    multiplie le volume.

    >>> cumulative_split_factor([{"date": "2024-06-10", "split": "10/1"}], "2024-06-09")
    10.0
    >>> cumulative_split_factor([{"date": "2024-06-10", "split": "10/1"}], "2024-06-10")
    1.0
    """
    factor = 1.0
    for entry in splits or []:
        d = entry.get("date") or entry.get("split_date")
        if not d:
            continue
        if str(d) > str(target_date):
            try:
                factor *= parse_split_ratio(entry.get("split") or entry.get("ratio"))
            except ValueError as exc:
                LOGGER.warning("[eodhd] split invalide ignoré: %s (%s)", entry, exc)
    return factor


def infer_splits_from_adjusted_close(eod_history: list[dict], *, threshold: float = 0.05) -> list[dict]:
    """Déduit les splits à partir du delta ``close`` vs ``adjusted_close``.

    Stratégie de secours quand l'endpoint ``/splits/`` n'est pas accessible
    (plan basique EODHD, cf. phase1_findings.md Option B).

    On scanne l'historique du plus ancien au plus récent ; un split est détecté
    quand le ratio ``adjusted_close[d] / adjusted_close[d-1]`` diverge fortement
    du ratio ``close[d] / close[d-1]``.

    Limitation : ne distingue pas split vs gros dividende exceptionnel — à
    n'utiliser qu'en fallback.

    Retourne une liste ``[{"date": "YYYY-MM-DD", "split": "N/1"}, ...]``
    triée par date ascendante.
    """
    if not eod_history:
        return []
    # tri ascendant par date
    rows = sorted(
        (r for r in eod_history if r.get("date") and r.get("close") and r.get("adjusted_close")),
        key=lambda r: str(r["date"]),
    )
    splits: list[dict] = []
    for prev, curr in zip(rows, rows[1:]):
        try:
            close_ratio = float(curr["close"]) / float(prev["close"])
            adj_ratio = float(curr["adjusted_close"]) / float(prev["adjusted_close"])
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if adj_ratio == 0:
            continue
        ratio = close_ratio / adj_ratio
        # un split N:1 -> close_ratio /= N, adj_ratio inchangé -> ratio ~ 1/N
        if ratio < (1 - threshold):
            n = round(1.0 / ratio)
            if n >= 2:
                splits.append({"date": str(curr["date"]), "split": f"{n}/1"})
    return splits


# ---------------------------------------------------------------------------
# Reconstruction split-only OHLCV
# ---------------------------------------------------------------------------


def eodhd_to_split_only(raw_bars: list[dict], splits: list[dict]) -> list[dict]:
    """Reconstruit des barres OHLCV split-only à partir d'EODHD.

    Entrée : barres EODHD natives ``{"date","open","high","low","close",
    "adjusted_close","volume"}``.
    Sortie : barres ``{"date","open","high","low","close","volume",
    "adjusted_close","split_factor"}`` où prix divisés et volume multiplié
    par le ``cumulative_split_factor`` des splits postérieurs.

    L'``adjusted_close`` (split + dividendes) est conservé tel quel pour
    information / cross-check downstream.
    """
    out: list[dict] = []
    for bar in raw_bars or []:
        date = bar.get("date")
        if not date:
            continue
        try:
            o = float(bar["open"])
            h = float(bar["high"])
            low = float(bar["low"])
            c = float(bar["close"])
            v = float(bar.get("volume") or 0)
        except (KeyError, TypeError, ValueError):
            LOGGER.warning("[eodhd] bar incomplet ignoré: %s", bar)
            continue
        factor = cumulative_split_factor(splits, str(date))
        if factor <= 0:
            factor = 1.0
        out.append(
            {
                "date": str(date),
                "open": o / factor,
                "high": h / factor,
                "low": low / factor,
                "close": c / factor,
                "volume": int(round(v * factor)),
                "adjusted_close": float(bar.get("adjusted_close", c)) ,
                "split_factor": factor,
            }
        )
    return out


# ---------------------------------------------------------------------------
# Mappage DB
# ---------------------------------------------------------------------------


def _date_to_rth_open_string(date_iso: str) -> str:
    """``YYYY-MM-DD`` -> ``"YYYY-MM-DD 09:30:00"`` (chaîne naïve NY).

    Aligné avec ``import_alpaca_bar._normalize_bar_timestamp`` qui stringifie
    les barres 1D Alpaca à l'open RTH NY pour la colonne ``stock_bars.timestamp``.
    """
    parts = str(date_iso).split("-")
    if len(parts) != 3:
        raise ValueError(f"date invalide: {date_iso!r}")
    year, month, day = (int(p) for p in parts)
    return f"{year:04d}-{month:02d}-{day:02d} {US_RTH_OPEN_HOUR_NY:02d}:{US_RTH_OPEN_MINUTE_NY:02d}:00"


def _date_to_close_timestamp(date_iso: str) -> datetime:
    """Variante UTC tz-aware (rarement utilisée en DB — rétrocompat tests)."""
    parts = str(date_iso).split("-")
    if len(parts) != 3:
        raise ValueError(f"date invalide: {date_iso!r}")
    year, month, day = (int(p) for p in parts)
    return datetime(
        year, month, day, US_RTH_OPEN_HOUR_NY, US_RTH_OPEN_MINUTE_NY, tzinfo=timezone.utc
    )


def _typical_price_proxy(high: float, low: float, close: float) -> float:
    """Proxy VWAP daily de repli : ``(high + low + close) / 3``."""
    return (high + low + close) / 3.0


def to_stock_bars_daily_row(bar: dict, symbol: str) -> dict:
    """Mappe une barre split-only vers le schéma ``stock_bars_daily``.

    Champs cibles : ``symbol, date, open, high, low, close, volume, adj_close,
    vwap, daily_return, is_filled, data_adjustment, data_source``.
    ``adj_close`` = ``close`` (split-only) ; ``adjusted_close`` EODHD
    (split+div) est ignoré ici car le projet ne stocke que du split-only.

    ``vwap`` : EODHD ne fournit pas de VWAP volume-pondéré sur l'endpoint
    ``/eod`` (ni sur ``/eod-bulk-last-day``). On stocke à la place le
    *typical price* daily ``(high + low + close) / 3``, proxy standard en
    equity research, afin de garder la feature ``close_to_vwap`` exploitable
    dans ``modelFactory`` côté EODHD. La colonne ``data_source='eodhd_eod'``
    permet de distinguer ce proxy d'un VWAP intraday réel.
    """
    high = float(bar["high"])
    low = float(bar["low"])
    close = float(bar["close"])
    typical_price = _typical_price_proxy(high, low, close)
    return {
        "symbol": symbol.strip().upper(),
        "date": str(bar["date"]),
        "open": float(bar["open"]),
        "high": high,
        "low": low,
        "close": close,
        "volume": int(bar.get("volume") or 0),
        "adj_close": close,
        "vwap": typical_price,
        "daily_return": None,
        "is_filled": 0,
        "data_adjustment": DATA_ADJUSTMENT_SPLIT,
        "data_source": DATA_SOURCE_EODHD,
    }


def to_stock_bars_row(bar: dict, symbol: str, timeframe: str = "1D") -> dict:
    """Mappe une barre split-only vers le schéma ``stock_bars``.

    Convention : ``timestamp`` = chaîne naïve ``YYYY-MM-DD 09:30:00`` (open RTH NY),
    alignée avec ``import_alpaca_bar`` pour timeframe='1D'. Évite tout doublon
    sur la clé unique ``(symbol, timeframe, timestamp)`` quand on coexiste
    avec des barres Alpaca historiques.
    ``trade_count`` n'est pas disponible sur EODHD -> ``0``.
    ``vwa_price`` reçoit le même proxy ``typical price`` que
    ``stock_bars_daily.vwap`` pour garder la cohérence entre les deux tables.
    """
    high = float(bar["high"])
    low = float(bar["low"])
    close = float(bar["close"])
    return {
        "symbol": symbol.strip().upper(),
        "timestamp": _date_to_rth_open_string(bar["date"]),
        "timeframe": timeframe,
        "open_price": float(bar["open"]),
        "high_price": high,
        "low_price": low,
        "close_price": close,
        "volume": int(bar.get("volume") or 0),
        "trade_count": 0,
        "vwa_price": _typical_price_proxy(high, low, close),
        "data_adjustment": DATA_ADJUSTMENT_SPLIT,
        "data_source": DATA_SOURCE_EODHD,
    }


__all__ = [
    "DATA_ADJUSTMENT_SPLIT",
    "DATA_SOURCE_EODHD",
    "US_CLOSE_UTC_HOUR",
    "US_CLOSE_UTC_MINUTE",
    "US_RTH_OPEN_HOUR_NY",
    "US_RTH_OPEN_MINUTE_NY",
    "cumulative_split_factor",
    "eodhd_to_split_only",
    "infer_splits_from_adjusted_close",
    "parse_split_ratio",
    "to_stock_bars_daily_row",
    "to_stock_bars_row",
]

