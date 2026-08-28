"""selector/dip_filter.py — Filtre Persistent Rank DIP (Global Rank LONG).

Filtre LONG-only appliqué à la branche **Global Rank** (``global_rank_{H}``),
PAS à Oracle Extreme. Logique isolée (historique multi-jours PIT, paramètres
gelés, diagnostics) et appelée par ``modelFactory.predictor.cascade_select``.

Règle (validée research 2026-08-27, in-sample + OOS 2025/2026 H1) :
    global_rank_{H} >= rank_threshold  sur `persist_days` séances consécutives
    ET condition prix close[J]/close[J-N]-1 selon le SIGNE de `dip_pct` :
        dip_pct >= 0  →  ret <= -dip_pct  (baisse >= dip_pct, DIP classique)
        dip_pct <  0  →  ret >= -dip_pct  (hausse >= |dip_pct|, anti-DIP/breakout)
    → entrée LONG.

Entrée — deux modes via ``reclaim_ratio`` (clé ``reclaim_ratio``) :
    - vide / None / 0  → entrée directe à J+1 (D0, comportement gelé) ;
    - > 0 (ex. 1.0 = retour au prix pré-DIP, 0.99 = 99% de ce prix) →
      entrée au premier T (J < T <= J + reclaim_max_wait) où
      close[T] >= reclaim_ratio * close[J-N] ET global_rank >= rank_threshold
      à T (confirmation de rebond avant entrée, research optionnelle).

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
    "reclaim_ratio",
    "reclaim_max_wait",
)

_DEFAULTS: dict[str, Any] = {
    "enabled": False,
    "rank_horizon": 20,      # 20 → colonne global_rank_20 ; None/vide → best_horizon
    "rank_threshold": 0.90,  # = TOP 10%
    "persist_days": 4,       # N
    "dip_pct": 0.02,         # X — signe : >=0 = baisse >= X (DIP) ; <0 = hausse >= |X| (anti-DIP)
    # Reclaim (confirmation de rebond avant entrée) — OPTION research, défaut OFF.
    #   reclaim_ratio = None/0  → entrée directe (D0, comportement gelé).
    #   reclaim_ratio = r (>0)  → attendre close[T] >= r * prix pré-DIP (close[J-N])
    #                             avec global_rank >= rank_threshold à T, T dans (J, J+max_wait].
    #                             1.0 = retour au prix d'origine ; 0.99 = 99% de ce prix ; etc.
    "reclaim_ratio": None,
    "reclaim_max_wait": 10,
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


def _dip_pass(ret: float, dip_pct: float) -> bool:
    """Condition prix du filtre selon le signe de ``dip_pct``.

    - ``dip_pct >= 0`` : ret <= -dip_pct  (baisse >= dip_pct, DIP classique).
    - ``dip_pct < 0``  : ret >= -dip_pct  (hausse >= |dip_pct|, anti-DIP/breakout).
    """
    threshold = -float(dip_pct)
    return ret <= threshold if float(dip_pct) >= 0 else ret >= threshold


def load_rank_history_df(
    engine: Any,
    batch_id: str,
    trade_date: str,
    persist_days: int,
    rank_col: str,
    *,
    extra_days: int = 0,
) -> pd.DataFrame:
    """Historique des rangs sur la fenêtre [trade_date - N jours, trade_date].

    Args:
        extra_days: séances supplémentaires de lookback (reclaim : scan des
            jours J antérieurs). 0 par défaut (fenêtre D0 inchangée).

    Returns:
        DataFrame [date, symbol, rank_col] trié par (symbol, date) — PIT.
    """
    from sqlalchemy import text as _text
    lb = (pd.Timestamp(trade_date) - pd.Timedelta(days=(persist_days + extra_days) * 2 + 7)).date().isoformat()
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


def load_oracle_rank_history_df(
    engine: Any,
    batch_id: str,
    trade_date: str,
    persist_days: int,
    *,
    extra_days: int = 0,
) -> pd.DataFrame:
    """Historique « rang » Oracle : percentile intra-date de ``proba_extreme``.

    Source : ``oracle_extreme_predictions`` (filtre batch strict). On convertit
    ``proba_extreme`` en percentile cross-sectionnel intra-date (PIT, par jour) —
    même normalisation que la cascade oracle/extreme_gate — pour que le seuil
    ``rank_threshold`` (ex. 0.90 = TOP 10%) ait du sens.

    Retourne ``[date, symbol, oracle_rank_pct]`` trié par (symbol, date) — PIT.
    """
    from sqlalchemy import text as _text
    lb = (pd.Timestamp(trade_date) - pd.Timedelta(days=(persist_days + extra_days) * 2 + 7)).date().isoformat()
    query = _text(
        "SELECT prediction_date, symbol, proba_extreme FROM oracle_extreme_predictions "
        "WHERE prediction_date BETWEEN :lb AND :d AND batch_id = :bid "
        "ORDER BY symbol, prediction_date"
    )
    try:
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"lb": lb, "d": trade_date, "bid": batch_id})
    except Exception:
        LOGGER.exception("dip_filter: load_oracle_rank_history échoué %s / %s", trade_date, batch_id)
        return pd.DataFrame()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["prediction_date"], errors="coerce").dt.normalize()
    df["symbol"] = df["symbol"].astype(str).str.upper()
    # Percentile intra-date (PIT) — même convention que cascade_select oracle/extreme_gate.
    df["oracle_rank_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    return df[["date", "symbol", "oracle_rank_pct"]].dropna(subset=["oracle_rank_pct"])


def load_price_history_df(
    engine: Any,
    symbols: list[str],
    trade_date: str,
    persist_days: int,
    *,
    extra_days: int = 0,
) -> pd.DataFrame:
    """Prix close sur la fenêtre nécessaire ([J-N, J]) pour les symboles donnés.

    Args:
        extra_days: séances supplémentaires de lookback (reclaim : scan des
            jours J antérieurs). 0 par défaut (fenêtre D0 inchangée).

    Returns:
        DataFrame [date, symbol, close] trié par (symbol, date) — PIT.
    """
    from sqlalchemy import text as _text
    if not symbols:
        return pd.DataFrame()
    lb = (pd.Timestamp(trade_date) - pd.Timedelta(days=(persist_days + extra_days) * 2 + 7)).date().isoformat()
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
        as_of_date: Date cible (YYYY-MM-DD) — date à laquelle on cherche une
            entrée (J pour D0 direct, T pour le reclaim).
        rank_history: DataFrame [date, symbol, <rank_col>] sur la fenêtre
            (>= persist_days + reclaim_max_wait séances) pour CE symbole.
        price_history: DataFrame [date, symbol, close] sur la même fenêtre
            pour CE symbole.
        config: dict de load_dip_filter_config().
        rank_col: colonne de rang à utiliser (ex. global_rank_20). Si None,
            résolue via _rank_column(config) — à fournir quand best_horizon
            diffère du défaut (cohérence avec filter_day_candidates).

    Returns:
        True si le symbole est éligible à l'entrée à as_of_date.

        Sans reclaim (``reclaim_ratio`` vide/None/0) : condition prix à J =
        as_of_date (persistance N séances + baisse >= dip_pct si dip_pct ≥ 0,
        ou hausse >= |dip_pct| si dip_pct < 0) → entrée directe J+1.

        Avec reclaim (``reclaim_ratio`` > 0) : entrée au premier T où
        ``close[T] >= reclaim_ratio * close[J-N]`` pour un DIP antérieur J
        situé dans les `reclaim_max_wait` séances précédentes, avec
        ``global_rank >= rank_threshold`` à T. ``1.0`` = retour au prix
        pré-DIP, ``0.99`` = 99% de ce prix, etc.
        NOTE : fonction sans état (une éligibilité évaluée par jour, cohérent
        avec D0) — le re-déclenchement les jours suivants est absorbé en aval
        par le position management (pas de double entrée).
    """
    if not config.get("enabled"):
        return True
    n = int(config.get("persist_days", 4))
    threshold = float(config.get("rank_threshold", 0.90))
    dip_pct = float(config.get("dip_pct", 0.02))
    rank_col = rank_col or _rank_column(config)
    reclaim_ratio = config.get("reclaim_ratio")

    # ── Séries PIT du symbole (bornées à as_of_date) ──
    _sym = str(symbol).upper()
    rh = rank_history[rank_history["symbol"].astype(str).str.upper() == _sym]
    ph = price_history[price_history["symbol"].astype(str).str.upper() == _sym]
    if rank_col not in rh.columns or "close" not in ph.columns:
        return False
    if as_of_date:
        _cut = pd.Timestamp(as_of_date)
        rh = rh[pd.to_datetime(rh["date"]) <= _cut]
        ph = ph[pd.to_datetime(ph["date"]) <= _cut]
    rh = rh.sort_values("date").dropna(subset=[rank_col])
    ph = ph.sort_values("date").dropna(subset=["close"])
    if rh.empty or ph.empty:
        return False

    # ── Reclaim désactivé (vide/None/0) → D0 direct (comportement gelé) ──
    if not reclaim_ratio:
        last_ranks = rh[rank_col].astype(float).tail(n)
        if len(last_ranks) < n:
            return False
        if not bool((last_ranks >= threshold).all()):
            return False
        closes = ph["close"].astype(float)
        if len(closes) < n + 1:
            return False
        j = float(closes.iloc[-1])
        j_n = float(closes.iloc[-n - 1])
        if j <= 0 or j_n <= 0:
            return False
        return _dip_pass(j / j_n - 1.0, dip_pct)

    # ── Reclaim activé : entrée au 1er T où close[T] >= ratio * close[J-N] ──
    ratio = float(reclaim_ratio)
    max_wait = int(config.get("reclaim_max_wait", 10))
    r_dates = list(pd.to_datetime(rh["date"]))
    p_dates = list(pd.to_datetime(ph["date"]))
    rank_by_date = dict(zip(r_dates, rh[rank_col].astype(float).tolist()))
    close_by_date = dict(zip(p_dates, ph["close"].astype(float).tolist()))
    common_dates = sorted(set(p_dates).intersection(r_dates))
    t = pd.Timestamp(as_of_date) if as_of_date else p_dates[-1]
    if t not in close_by_date or t not in rank_by_date:
        return False
    close_t = float(close_by_date[t])
    if close_t <= 0 or float(rank_by_date[t]) < threshold:
        return False
    pos = {d: i for i, d in enumerate(common_dates)}
    if t not in pos:
        return False
    idx_t = pos[t]
    for i in range(max(0, idx_t - max_wait), idx_t):
        if i < n:
            continue
        jd = common_dates[i]
        # Persistance du rang sur les N séances finissant à J.
        j_ranks = [float(rank_by_date[common_dates[k]]) for k in range(i - n + 1, i + 1)]
        if not all(r >= threshold for r in j_ranks):
            continue
        # DIP à J : condition prix selon le signe de dip_pct.
        j_close = float(close_by_date[jd])
        j_n_close = float(close_by_date[common_dates[i - n]])
        if j_close <= 0 or j_n_close <= 0:
            continue
        if not _dip_pass(j_close / j_n_close - 1.0, dip_pct):
            continue
        # Reclaim à T : prix >= ratio * prix pré-DIP (close[J-N]).
        if close_t >= ratio * j_n_close:
            return True
    return False


def filter_day_candidates(
    ranks_day: pd.DataFrame,
    engine: Any,
    batch_id: str,
    trade_date: str,
    config: dict[str, Any],
    *,
    best_h: int | None = None,
    rank_source: str = "global",
) -> pd.DataFrame:
    """Filtre les rangs du jour : ne garde que les symboles passant le DIP.

    Args:
        ranks_day: DataFrame [symbol, <rank_col>, ...] — rangs du jour (cascade).
        engine, batch_id, trade_date: contexte DB.
        config: dict de load_dip_filter_config().
        best_h: horizon du batch (si rank_horizon vide).
        rank_source: "global" (global_rank_history, défaut) | "oracle"
            (oracle_extreme_predictions → percentile intra-date de proba_extreme,
            pour les batchs oracle-only sans global_rank_history).

    Returns:
        DataFrame filtré (symboles non-DIP retirés). Si config.enabled=False,
        retourne ranks_day inchangé.
    """
    if not config.get("enabled"):
        return ranks_day
    if ranks_day.empty:
        return ranks_day
    n = int(config.get("persist_days", 4))
    _oracle_source = str(rank_source or "global").strip().lower() == "oracle"
    rank_col = _rank_column(config, best_h)
    if _oracle_source:
        rank_col = "oracle_rank_pct"
    reclaim_ratio = config.get("reclaim_ratio")
    # Reclaim : scan des J antérieurs → fenêtre élargie de reclaim_max_wait.
    max_wait = int(config.get("reclaim_max_wait", 10)) if reclaim_ratio else 0

    symbols = [str(s) for s in ranks_day["symbol"].unique() if pd.notna(s)]
    if not symbols:
        return ranks_day

    # Charger historique rank (fenêtre) + prix (fenêtre) en une passe.
    if _oracle_source:
        rh = load_oracle_rank_history_df(engine, batch_id, trade_date, n, extra_days=max_wait)
    else:
        rh = load_rank_history_df(engine, batch_id, trade_date, n, rank_col, extra_days=max_wait)
    ph = load_price_history_df(engine, symbols, trade_date, n, extra_days=max_wait)
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
        "DIP_FILTER rule date=%s col=%s N=%d X=%.2f%% threshold=%.2f reclaim=%s "
        "before=%d after=%d rejected=%d",
        trade_date, rank_col, n,
        float(config.get("dip_pct", 0.02)) * 100.0,
        float(config.get("rank_threshold", 0.90)),
        str(reclaim_ratio) if reclaim_ratio else "off",
        len(symbols), len(keep), rejected,
    )
    return ranks_day[ranks_day["symbol"].astype(str).isin(keep)].copy()
