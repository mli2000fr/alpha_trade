"""selector/dip_filter.py — Filtre Persistent Rank DIP (Global Rank LONG).

Filtre LONG-only appliqué à la branche **Global Rank** (``global_rank_{H}``),
PAS à Oracle Extreme. Logique isolée (historique multi-jours PIT, paramètres
gelés, diagnostics) et appelée par ``modelFactory.predictor.cascade_select``.

Règle (validée research 2026-08-27, in-sample + OOS 2025/2026 H1) :
    global_rank_{H} >= rank_threshold  sur `persist_days` séances consécutives
    ET close[J] / close[J - persist_days] - 1 <= -dip_pct
    → entrée LONG directe (pas de reclaim).

Config : ``config.yaml → persistent_dip_filter_long``, avec clés **PROD** et
**BACKTEST** distinctes (pattern ``prod_*`` / ``backtest_*`` déjà utilisé par
``risk_management``).

Interface publique :
    load_dip_filter_config(execution_context)
    filter_day_candidates(ranks_day, engine, batch_id, trade_date, config)
    evaluate_dip_filter(symbol, as_of_date, rank_history, price_history, config)
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

# Clés de la config ``persistent_dip_filter_long`` (préfixe prod_/backtest_).
_KEYS = (
    "enabled",
    "rank_horizon",
    "rank_threshold",
    "persist_days",
    "dip_pct",
)

_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "rank_horizon": 20,      # 20 → colonne global_rank_20 ; None/vide → best_horizon
    "rank_threshold": 0.90,  # = TOP 10%
    "persist_days": 4,       # N
    "dip_pct": 0.02,         # X
}


def _load_yaml_config() -> dict[str, Any]:
    try:
        import yaml as _yaml
        with open("config.yaml", encoding="utf-8") as _fh:
            return (_yaml.safe_load(_fh) or {}).get("persistent_dip_filter_long") or {}
    except Exception as _exc:  # noqa: BLE001 — non bloquant
        LOGGER.warning("dip_filter: config.yaml illisible (%s) — défauts", _exc)
        return {}


def load_dip_filter_config(execution_context: str) -> dict[str, Any]:
    """Charge la config DIP pour un contexte d'exécution.

    Args:
        execution_context: "prod" | "backtest". Sélectionne les clés
            ``prod_*`` ou ``backtest_*`` ; sinon fallback sur les clés nues
            (rétro-compat) puis défauts.

    Returns:
        dict: enabled, rank_horizon, rank_threshold, persist_days, dip_pct.
    """
    raw = _load_yaml_config()
    prefix = f"{execution_context}_" if execution_context in ("prod", "backtest") else ""
    out: dict[str, Any] = {}
    for k in _KEYS:
        out[k] = raw.get(f"{prefix}{k}", raw.get(k, _DEFAULTS[k]))
    return out


def _rank_column(config: dict[str, Any], best_h: int | None = None) -> str:
    """Colonne de rang à utiliser (global_rank_{H})."""
    h = config.get("rank_horizon")
    if h in (None, "", 0):
        h = best_h
    if h in (None, "", 0):
        h = 20
    col = f"global_rank_{int(h)}"
    return col if col in ("global_rank_3", "global_rank_5", "global_rank_10", "global_rank_15", "global_rank_20") else "global_rank_20"


def load_rank_history_df(
    engine: Any,
    batch_id: str,
    trade_date: str,
    persist_days: int,
    rank_col: str,
) -> pd.DataFrame:
    """Historique des rangs sur la fenêtre [trade_date - N jours, trade_date].

    Returns:
        DataFrame [date, symbol, rank_col] trié par (symbol, date) — PIT.
    """
    from sqlalchemy import text as _text
    lb = (pd.Timestamp(trade_date) - pd.Timedelta(days=persist_days * 2 + 7)).date().isoformat()
    query = _text(
        f"SELECT date, symbol, {rank_col} FROM global_rank_history "
        f"WHERE date BETWEEN :lb AND :d AND batch_id = :bid ORDER BY symbol, date"
    )
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"lb": lb, "d": trade_date, "bid": batch_id})
    except Exception:
        LOGGER.exception("dip_filter: load_rank_history échoué %s / %s", trade_date, batch_id)
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.dropna(subset=[rank_col])


def load_price_history_df(
    engine: Any,
    symbols: list[str],
    trade_date: str,
    persist_days: int,
) -> pd.DataFrame:
    """Prix close sur la fenêtre nécessaire ([J-N, J]) pour les symboles donnés.

    Returns:
        DataFrame [date, symbol, close] trié par (symbol, date) — PIT.
    """
    from sqlalchemy import text as _text
    if not symbols:
        return pd.DataFrame()
    lb = (pd.Timestamp(trade_date) - pd.Timedelta(days=persist_days * 2 + 7)).date().isoformat()
    ph = ",".join(["%s"] * len(symbols))
    query = (
        "SELECT date, symbol, close FROM stock_bars_daily "
        f"WHERE symbol IN ({ph}) AND date BETWEEN %s AND %s "
        "ORDER BY symbol, date"
    )
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params=(*symbols, lb, trade_date))
    except Exception:
        LOGGER.exception("dip_filter: load_price_history échoué %s (%d symbols)", trade_date, len(symbols))
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    return df.dropna(subset=["close"])


def evaluate_dip_filter(
    symbol: str,
    as_of_date: str,
    rank_history: pd.DataFrame,
    price_history: pd.DataFrame,
    config: dict[str, Any],
    rank_col: str | None = None,
) -> bool:
    """Évalue le DIP pour un symbole à une date (logique pure, PIT).

    Args:
        symbol: Symbole (uppercase).
        as_of_date: Date cible (YYYY-MM-DD) — le DIP doit être détecté à J.
        rank_history: DataFrame [date, symbol, <rank_col>] sur la fenêtre
            (>= persist_days séances) pour CE symbole, trié par date croissante.
        price_history: DataFrame [date, symbol, close] sur la fenêtre
            (>= persist_days + 1 séances) pour CE symbole, trié par date croissante.
        config: dict de load_dip_filter_config().
        rank_col: colonne de rang à utiliser (ex. global_rank_20). Si None,
            résolue via _rank_column(config) — à fournir quand best_horizon
            diffère du défaut (cohérence avec filter_day_candidates).

    Returns:
        True si le symbole passe le DIP (persistance + baisse).
    """
    if not config.get("enabled"):
        return True
    n = int(config.get("persist_days", 4))
    threshold = float(config.get("rank_threshold", 0.90))
    dip_pct = float(config.get("dip_pct", 0.02))
    rank_col = rank_col or _rank_column(config)

    # ── Persistance : rank >= threshold sur les N dernières séances ──
    rh = rank_history[rank_history["symbol"].astype(str).str.upper() == str(symbol).upper()]
    if rh.empty or rank_col not in rh.columns:
        return False
    rh = rh.sort_values("date")
    last_ranks = rh[rank_col].dropna().tail(n)
    if len(last_ranks) < n:
        return False
    if not bool((last_ranks >= threshold).all()):
        return False

    # ── DIP : close[J] / close[J-N] - 1 <= -dip_pct ──
    ph = price_history[price_history["symbol"].astype(str).str.upper() == str(symbol).upper()]
    if ph.empty:
        return False
    ph = ph.sort_values("date")
    closes = ph["close"].dropna()
    if len(closes) < n + 1:
        return False
    j = float(closes.iloc[-1])
    j_n = float(closes.iloc[-n - 1])
    if j <= 0 or j_n <= 0:
        return False
    ret = j / j_n - 1.0
    return bool(ret <= -dip_pct)


def filter_day_candidates(
    ranks_day: pd.DataFrame,
    engine: Any,
    batch_id: str,
    trade_date: str,
    config: dict[str, Any],
    *,
    best_h: int | None = None,
) -> pd.DataFrame:
    """Filtre les rangs du jour : ne garde que les symboles passant le DIP.

    Args:
        ranks_day: DataFrame [symbol, <rank_col>, ...] — rangs du jour (cascade).
        engine, batch_id, trade_date: contexte DB.
        config: dict de load_dip_filter_config().
        best_h: horizon du batch (si rank_horizon vide).

    Returns:
        DataFrame filtré (symboles non-DIP retirés). Si config.enabled=False,
        retourne ranks_day inchangé.
    """
    if not config.get("enabled"):
        return ranks_day
    if ranks_day.empty:
        return ranks_day
    n = int(config.get("persist_days", 4))
    rank_col = _rank_column(config, best_h)

    symbols = [str(s) for s in ranks_day["symbol"].unique() if pd.notna(s)]
    if not symbols:
        return ranks_day

    # Charger historique rank (fenêtre) + prix (fenêtre) en une passe.
    rh = load_rank_history_df(engine, batch_id, trade_date, n, rank_col)
    ph = load_price_history_df(engine, symbols, trade_date, n)
    if rh.empty or ph.empty:
        LOGGER.warning("dip_filter: historique vide %s — aucun filtre appliqué", trade_date)
        return ranks_day

    # Pré-index (symbol, date) → valeur pour évaluation rapide.
    keep: list[str] = []
    rejected = 0
    for sym in symbols:
        if evaluate_dip_filter(sym, trade_date, rh, ph, config, rank_col=rank_col):
            keep.append(sym)
        else:
            rejected += 1
    LOGGER.info(
        "DIP_FILTER rule date=%s col=%s N=%d X=%.2f%% threshold=%.2f "
        "before=%d after=%d rejected=%d",
        trade_date, rank_col, n,
        float(config.get("dip_pct", 0.02)) * 100.0,
        float(config.get("rank_threshold", 0.90)),
        len(symbols), len(keep), rejected,
    )
    return ranks_day[ranks_day["symbol"].astype(str).isin(keep)].copy()
