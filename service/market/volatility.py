"""Helpers ATR(14) réutilisables live + watcher + tests.

Le module supporte trois sources :

1. Une série OHLC pré-fournie (test, backtest)
2. Le cache EODHD (best-effort, hors latence critique)
3. Aucune source -> ``None`` (le caller bascule sur le fallback fixe)
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Sequence

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OHLCBar:
    high: float
    low: float
    close: float


def compute_atr_from_bars(bars: Sequence[OHLCBar], period: int = 14) -> float | None:
    """ATR(period) Wilder à partir de barres OHLC ordonnées par date croissante."""
    if not bars or len(bars) < period + 1:
        return None
    trs: list[float] = []
    prev_close = bars[0].close
    for bar in bars[1:]:
        tr = max(
            bar.high - bar.low,
            abs(bar.high - prev_close),
            abs(bar.low - prev_close),
        )
        trs.append(tr)
        prev_close = bar.close
    if len(trs) < period:
        return None
    # Initial ATR = SMA des `period` premiers TR
    atr = sum(trs[:period]) / period
    # Wilder smoothing pour les TR suivants
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    if atr <= 0:
        return None
    return float(atr)


def compute_atr_from_eodhd_cache(symbol: str, *, period: int = 14, lookback_days: int = 60) -> float | None:
    """Tente de calculer l'ATR depuis le cache EODHD local.

    Best-effort : retourne ``None`` si le cache n'est pas disponible. N'impacte
    jamais le chemin critique (toute exception est avalée + log debug).
    """
    try:
        from service.eodhd import bulk_eod  # type: ignore
        from datetime import date as _date, timedelta as _td

        end = _date.today()
        start = end - _td(days=lookback_days)
        df = bulk_eod.load_symbol_history(symbol, start, end)  # type: ignore[attr-defined]
        if df is None or df.empty:
            return None
        bars = [
            OHLCBar(high=float(r["high"]), low=float(r["low"]), close=float(r["close"]))
            for _, r in df.iterrows()
        ]
        return compute_atr_from_bars(bars, period=period)
    except Exception as exc:
        LOGGER.debug("compute_atr_from_eodhd_cache(%s) -> fallback (%s)", symbol, exc)
        return None


__all__ = ["OHLCBar", "compute_atr_from_bars", "compute_atr_from_eodhd_cache"]

