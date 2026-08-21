"""E21-v2 — Régime SPY SMA50/SMA200 (PIT) → trailing par-signal.

Définition pré-spécifiée (validée utilisateur 2026-08-21) — PAS ajustée sur les résultats :

    BULL       : close > SMA200 AND close > SMA50   → trailing 2.5×ATR (risk-based)
    REBOUND    : close <= SMA200 AND close > SMA50  → trailing 2.5×ATR
    CORRECTION : close > SMA200 AND close <= SMA50  → trailing 7 %
    SLIDE      : close <= SMA200 AND close <= SMA50 → trailing 7 %

SMA200 = régime structurel, SMA50 = état tactique. STRICTEMENT PIT :
calculé sur les clôtures SPY disponibles à la clôture du jour de décision D
(entrée D+1). Le régime est GELÉ à l'entrée — aucune mise à jour pendant la
position (le lifecycle choisi à l'entrée court jusqu'à la sortie).

Politiques (4 expériences, breaker PROD gelé) :
    C0 = 7 % partout
    C1 = ATR partout
    C2 = BULL/REBOUND ATR ; CORRECTION/SLIDE 7 %   (hypothèse)
    C3 = BULL/REBOUND 7 % ; CORRECTION/SLIDE ATR    (placebo inverse)
"""
from __future__ import annotations

from datetime import date

import pandas as pd

POLICIES = ("c0", "c1", "c2", "c3")

# (trailing_stop_pct, risk_based) — risk_based=True => trailing 2.5×ATR (distance du stop initial).
_ATR = (None, True)
_PCT7 = (0.07, False)


def compute_regime(spy_close: pd.Series) -> pd.Series:
    """Série {date: régime str | NA}, PIT (asof sur les closes disponibles)."""
    close = spy_close.sort_index()
    close.index = pd.to_datetime(close.index).normalize()
    close = close[~close.index.duplicated(keep="last")].dropna()
    sma50 = close.rolling(50, min_periods=50).mean()
    sma200 = close.rolling(200, min_periods=200).mean()
    up200 = close > sma200
    up50 = close > sma50
    regime = pd.Series("SLIDE", index=close.index, dtype=object)
    regime[up200 & up50] = "BULL"
    regime[(~up200) & up50] = "REBOUND"
    regime[up200 & (~up50)] = "CORRECTION"
    # (~up200) & (~up50) = SLIDE (défaut)
    regime[sma200.isna()] = pd.NA  # historique insuffisant -> inconnu
    return regime


def trailing_for_regime(regime: str | None, policy: str) -> tuple[float | None, bool]:
    """(trailing_stop_pct, risk_based) pour un régime + politique."""
    policy = str(policy).strip().lower()
    if policy == "c0":
        return _PCT7
    if policy == "c1":
        return _ATR
    if policy == "c2":
        return _ATR if regime in ("BULL", "REBOUND") else _PCT7
    if policy == "c3":
        return _PCT7 if regime in ("BULL", "REBOUND") else _ATR
    raise ValueError(f"politique de régime inconnue: {policy}")


def build_regime_trailing_map(spy_close: pd.Series, policy: str) -> dict[date, tuple[float | None, bool]]:
    """Map {decision_date: (trailing_stop_pct, risk_based)} — régime PIT à la date."""
    regime = compute_regime(spy_close)
    out: dict[date, tuple[float | None, bool]] = {}
    for ts, r in regime.items():
        if r is None or pd.isna(r):
            continue
        out[pd.Timestamp(ts).date()] = trailing_for_regime(str(r), policy)
    return out


def regime_distribution(dates: pd.Series, spy_close: pd.Series) -> pd.Series:
    """Distribution des dates (signaux) entre les 4 régimes (PIT)."""
    regime = compute_regime(spy_close)
    dts = pd.to_datetime(pd.Series(dates)).dt.normalize()
    mapped = dts.map(lambda d: regime.get(d) if pd.notna(d) else pd.NA)
    return mapped.value_counts(dropna=False)
