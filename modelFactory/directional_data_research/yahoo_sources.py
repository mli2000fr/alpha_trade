"""modelFactory/directional_data_research/yahoo_sources.py — Téléchargement Yahoo PIT avec cache.

Source : ``yfinance 1.4.1``, objet ``Ticker.upgrades_downgrades`` (actions
analystes datées : upgrades/downgrades/initiations + variations de target price).

VERDICT POC (cf. artifacts/directional_data_research/free_sources_audit.md) :
c'est la SEULE source gratuite réellement PIT pour le backtest (index ``GradeDate``
= timestamp de publication, 2012 → 2026, 411-974 lignes/symbole vérifiées). Les
autres objets yfinance (``earnings_estimate``, ``revenue_estimate``,
``analyst_price_targets``, ``recommendations``) ne sont que des snapshots actuels
→ NON utilisés pour ce backtest.

Discipline :
- RECHERCHE UNIQUEMENT — jamais intégré en production.
- Cache par symbole : ``data/raw/yahoo/{SYMBOL}_upgrades_downgrades.parquet``.
- 1 requête réseau par symbole au premier passage ; échec → fichier vide (pour ne
  pas re-télécharger en boucle).
- Rate-limit doux (``time.sleep``) pour ne pas se faire bloquer par Yahoo.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

CACHE_DIR = Path("data/raw/yahoo")

# Échelle de rating Yahoo/firmes → note numérique (pour rating_delta).
_RATING: dict[str, int] = {
    "strong buy": 5, "conviction buy": 5, "best idea": 5, "buy": 4,
    "overweight": 4, "outperform": 4, "market outperform": 4, "market out perform": 4,
    "moderate buy": 4, "add": 4, "accumulate": 4, "positive": 4, "top pick": 4,
    "sector outperform": 4, "hold": 3, "neutral": 3, "market perform": 3,
    "equal-weight": 3, "equal weight": 3, "sector perform": 3, "in-line": 3,
    "in line": 3, "peer perform": 3, "sector weight": 3, "market weight": 3,
    "underperform": 2, "under weight": 2, "underweight": 2, "reduce": 2,
    "sell": 2, "negative": 2, "market underperform": 2, "sector underperform": 2,
    "strong sell": 1, "strong underperform": 1, "heavy sell": 1,
}


def _grade_num(g: Any) -> float:
    if g is None:
        return float("nan")
    return float(_RATING.get(str(g).strip().lower(), float("nan")))


def normalize_ud(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise un DataFrame ``upgrades_downgrades`` (par symbole).

    Sortie : index reset, ``published_at`` (datetime), ``action``, ``to_num``,
    ``from_num``, ``rating_delta`` (= to_num − from_num, NaN si inconnu),
    ``pt_delta`` (= currentPriceTarget − priorPriceTarget, NaN si prior ≤ 0).
    """
    if df is None or df.empty:
        return pd.DataFrame(
            columns=["published_at", "action", "to_num", "from_num", "rating_delta", "pt_delta"]
        )
    out = df.reset_index()
    # L'index s'appelle GradeDate (ou une colonne dérivée).
    date_col = "GradeDate" if "GradeDate" in out.columns else out.columns[0]
    out["published_at"] = pd.to_datetime(out[date_col], errors="coerce")
    out["action"] = out.get("Action", pd.Series(index=out.index, dtype=object)).astype(str).str.strip().str.lower()
    out["to_num"] = out.get("ToGrade", pd.Series(index=out.index, dtype=object)).map(_grade_num)
    out["from_num"] = out.get("FromGrade", pd.Series(index=out.index, dtype=object)).map(_grade_num)
    out["rating_delta"] = out["to_num"] - out["from_num"]
    out["pt_delta"] = np.nan
    if "currentPriceTarget" in out.columns and "priorPriceTarget" in out.columns:
        cur = pd.to_numeric(out["currentPriceTarget"], errors="coerce")
        pri = pd.to_numeric(out["priorPriceTarget"], errors="coerce")
        out["pt_delta"] = np.where(pri > 0, cur - pri, np.nan)
    keep = ["published_at", "action", "to_num", "from_num", "rating_delta", "pt_delta", "Firm"]
    out = out[[c for c in keep if c in out.columns]].copy()
    out["published_at"] = pd.to_datetime(out["published_at"], errors="coerce")
    return out.dropna(subset=["published_at"]).sort_values("published_at").reset_index(drop=True)


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}_upgrades_downgrades.parquet"


def download_upgrades_downgrades(symbol: str, *, force: bool = False, sleep_s: float = 0.4) -> pd.DataFrame:
    """Télécharge (ou relit du cache) les upgrades/downgrades d'un symbole."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(symbol)
    if path.exists() and not force:
        try:
            return pd.read_parquet(path)
        except Exception as e:  # cache corrompu → re-télécharge
            LOGGER.warning("cache %s illisible (%s) → re-téléchargement", path, e)
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        raw = t.upgrades_downgrades
        if isinstance(raw, tuple):
            raw = raw[0]
        df = normalize_ud(raw)
        df.to_parquet(path, index=False)
        LOGGER.info("%s : %d événements → %s", symbol, len(df), path)
        return df
    except Exception as e:
        LOGGER.warning("%s : échec (%s) → cache vide", symbol, type(e).__name__)
        pd.DataFrame().to_parquet(path, index=False)
        return pd.DataFrame(columns=["published_at", "action", "to_num", "from_num",
                                     "rating_delta", "pt_delta", "Firm"])
    finally:
        time.sleep(sleep_s)


def download_many(symbols: list[str], *, force: bool = False, sleep_s: float = 0.4,
                  log_every: int = 25) -> dict[str, pd.DataFrame]:
    """Télécharge plusieurs symboles avec cache et progression."""
    out: dict[str, pd.DataFrame] = {}
    for i, sym in enumerate(symbols, start=1):
        out[sym] = download_upgrades_downgrades(sym, force=force, sleep_s=sleep_s)
        if i % log_every == 0 or i == len(symbols):
            LOGGER.info("téléchargement %d/%d", i, len(symbols))
    return out


def load_all(symbols: list[str]) -> dict[str, pd.DataFrame]:
    """Recharge depuis le cache uniquement (pas de réseau)."""
    out: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        p = _cache_path(sym)
        if p.exists():
            out[sym] = pd.read_parquet(p)
        else:
            out[sym] = pd.DataFrame()
    return out
