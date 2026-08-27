"""Audit de parité PROD P0/P2 — persistent_top10_dip (2026-08-27).

Objectif : isoler la valeur propre de DIP N4/X2 par rapport à la baseline,
avec PARFAITE parité du module risque.

Audit du module risque (fait avant ce script) :
- ``BacktestEngine`` ne bloque PAS lui-même les entrées en close_only :
  son ``RegimeFilterConfig`` est un filtre bear-vs-SMA, désactivé ici.
- Le comportement PROD réel (``service/market/regime_manager.py``, lignes
  1184-1186) : ``mode in ("close_only", "cash_only")`` → ``allow_new_entries=False``
  → AUCUNE nouvelle entrée ces jours-là. Confirmé aussi par
  ``RegimeState.is_blocking_entries`` (close_only, cash_only) et
  ``ExecutionConfig.blocks_new_entries``.
- Donc pour une parité fidèle, le veto régime PROD (close_only + cash_only)
  doit être appliqué aux DEUX variantes, via le MÊME chemin (filtre de
  signaux amont identique, puis même BacktestEngine/build_config PROD).

Variantes (aucun autre paramètre différent, aucun sweep de N/X) :
- P0_PROD = TOP10 global_rank (baseline) + veto régime PROD
- P2_PROD = DIP N4/X2 (persist_4 & ret_4 <= -2%) + MÊME veto régime PROD

Produit :
- Métriques : Total return, CAGR, Sharpe, Sortino, MaxDD, PF, win rate,
  trades, exposure, capital utilization, avg slots (+ régime breakdown).
- Attribution de capacité : raw signals, risk eligible, already open,
  no slot, executed, unused slots/day.

Usage : python -m modelFactory.dip_research.persistent_top10_dip_parity
"""
from __future__ import annotations

import argparse
import logging
import sys
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from backtesting.simulator import BacktestEngine
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.dip_research.persistent_top10_dip_portfolio import (
    RANK_COL,
    TOP10,
    N_DIP,
    X_DIP,
    _load_regime_map,
    load_regime_map_db,
    build_config,
    _enrich_atr,
    _metrics,
)

LOGGER = logging.getLogger(__name__)

# Comportement PROD vérifié : ces régimes bloquent TOUTES les nouvelles entrées.
BLOCKED_REGIMES = {"close_only", "cash_only"}


def build_signals_parity(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Signaux P0_PROD / P2_PROD avec le même veto régime PROD amont.

    Régime : source DB ``stock_macro_indicators_daily`` (alimentée en continu,
    couvre 2026) avec fallback ``regime.ttx`` — parité avec le moteur PROD.
    """
    rank = pd.read_sql(
        f"SELECT symbol, date, {RANK_COL} FROM global_rank_history WHERE date BETWEEN %s AND %s",
        engine, params=(start_date, end_date),
    )
    rank["date"] = pd.to_datetime(rank["date"], errors="coerce").dt.normalize()
    rank["symbol"] = rank["symbol"].astype(str).str.upper()

    lb = (pd.Timestamp(start_date) - pd.Timedelta(days=20)).date().isoformat()
    bars = pd.read_sql(
        "SELECT symbol, date, close, adj_close FROM stock_bars_daily WHERE date BETWEEN %s AND %s",
        engine, params=(lb, end_date),
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.dropna(subset=["date", "symbol", "close"])

    df = rank.merge(bars[["symbol", "date", "adj_close"]], on=["date", "symbol"], how="left")
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    df["top10"] = (df[RANK_COL] >= TOP10).astype(int)
    g_close = df.groupby("symbol")["adj_close"]
    df["ret_4"] = df["adj_close"] / g_close.shift(N_DIP) - 1.0
    df["persist_4"] = df.groupby("symbol")["top10"].transform(
        lambda x: x.rolling(N_DIP, min_periods=N_DIP).min())
    reg_map = load_regime_map_db(engine)
    df["regime"] = df["date"].map(reg_map).fillna("unknown")

    # Veto régime PROD : identique pour les DEUX variantes (parité).
    veto = ~df["regime"].isin(BLOCKED_REGIMES)
    base = df[(df["top10"] == 1) & veto].copy()
    dip2 = df[(df["persist_4"] == 1) & (df["ret_4"] <= -X_DIP) & veto].copy()

    def _sig(frame: pd.DataFrame, name: str) -> pd.DataFrame:
        s = pd.DataFrame({
            "trade_date": frame["date"],
            "symbol": frame["symbol"],
            "selected": True,
            "rank": frame[RANK_COL].astype(float),
            # score = global_rank (>= 0.90) : passe le seuil PROD min_score_threshold=0.7
            "score": frame[RANK_COL].astype(float),
            "regime": frame["regime"].values,
        })
        s["variant"] = name
        return s

    return pd.concat([
        _sig(base, "P0_PROD"),
        _sig(dip2, "P2_PROD"),
    ], ignore_index=True)


def _schedule_local(signals: pd.DataFrame, trading_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Réplique BacktestEngine._schedule_signals_for_execution (J -> J+1 open)."""
    if signals.empty:
        return signals.copy()
    scheduled = signals.copy()
    scheduled["trade_date"] = pd.to_datetime(scheduled["trade_date"])
    idx = trading_days.searchsorted(scheduled["trade_date"].to_numpy(dtype="datetime64[ns]"), side="right")
    valid = idx < len(trading_days)
    scheduled = scheduled.loc[valid].copy()
    if scheduled.empty:
        return scheduled
    scheduled["signal_date"] = scheduled["trade_date"]
    scheduled["execution_date"] = trading_days.take(idx[valid]).values
    return scheduled


def capacity_attribution(
    signals: pd.DataFrame,
    result: Any,
    trading_days: pd.DatetimeIndex,
    max_positions: int = 20,
) -> dict[str, float]:
    """Attribution de capacité au niveau des signaux + occupation réelle du moteur.

    - raw_signals        : signaux bruts de la variante (déjà veto régime PROD appliqué).
    - risk_eligible      : signaux programmables (présents dans OHLCV + J+1 dispo).
    - already_open       : signaux dont le symbole était déjà en position ce jour-là.
    - no_slot            : signaux excédentaires au-delà de max_positions ce jour-là.
    - executed           : entrées réellement ouvertes (events entry_opened).
    - unused_slots_day   : moyenne des slots libres par jour de trading.
    """
    ev = result.trade_events_df
    n_executed = int((ev["event_type"] == "entry_opened").sum()) if not ev.empty else 0

    # Occupation réelle des positions jour par jour (entry_opened + exits).
    openings: list[tuple[pd.Timestamp, str]] = []
    if not ev.empty:
        op = ev[ev["event_type"] == "entry_opened"]
        openings = [
            (pd.Timestamp(r["event_date"]).normalize(), str(r["symbol"]))
            for _, r in op.iterrows()
        ]
    closed = {}
    if result.closed_trades_df is not None and not result.closed_trades_df.empty:
        for _, r in result.closed_trades_df.iterrows():
            closed[(pd.Timestamp(r["entry_date"]).normalize(), str(r["symbol"]))] = pd.Timestamp(r["exit_date"]).normalize()

    # Pour chaque ouverture, date de sortie (fin de période si jamais fermée).
    exits: dict[tuple[pd.Timestamp, str], pd.Timestamp] = {}
    for k in openings:
        if k in closed:
            exits[k] = closed[k]
        else:
            exits[k] = trading_days[-1]

    # occupation[day] = set des symboles en position ce jour (avant entrées du jour)
    occupation: dict[pd.Timestamp, set[str]] = {}
    active: dict[str, pd.Timestamp] = {}
    end = trading_days[-1]
    for day in trading_days:
        # fermer les positions sorties avant/à ce jour
        for sym, ex in list(active.items()):
            if ex < day:
                del active[sym]
        # ouvrir celles entrées ce jour (pour l'occupation du lendemain)
        for (ed, sym) in openings:
            if ed == day:
                active[sym] = exits.get((ed, sym), end)
        occupation[day] = set(active.keys())

    # Signaux programmés triés par rank (ordre d'exécution du moteur).
    scheduled = _schedule_local(signals, trading_days)
    n_raw = int(len(signals))
    n_eligible = int(len(scheduled))
    already_open = 0
    no_slot = 0
    for day, grp in scheduled.groupby("execution_date"):
        day_ts = pd.Timestamp(day).normalize()
        pos_today = occupation.get(day_ts, set())
        # On retire les positions qui entrent ce jour même pour ne pas compter
        # "already open" sur une entrée du même jour (occupation est après-entrée).
        pos_before = set()
        for sym in pos_today:
            pos_before.add(sym)
        # retirer les symboles qui s'ouvrent ce jour (ils ne sont pas encore en position au début)
        opening_today = {sym for (ed, sym) in openings if ed == day_ts}
        pos_before -= opening_today
        slots_used = len(pos_before)
        sorted_grp = grp.sort_values(["rank", "symbol"])
        for _, row in sorted_grp.iterrows():
            sym = str(row["symbol"])
            if sym in pos_before:
                already_open += 1
            elif slots_used >= max_positions:
                no_slot += 1
            else:
                slots_used += 1

    n_days = max(1, int(len(trading_days)))
    used_per_day = [len(v) for v in occupation.values()]
    avg_used = float(np.mean(used_per_day)) if used_per_day else 0.0
    unused_slots_day = max(0.0, float(max_positions) - avg_used)

    return {
        "raw_signals": float(n_raw),
        "risk_eligible": float(n_eligible),
        "already_open": float(already_open),
        "no_slot": float(no_slot),
        "executed": float(n_executed),
        "unused_slots_day": unused_slots_day,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="persistent_top10_dip parity audit (P0/P2 PROD).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--out", default="artifacts/persistent_top10_dip_parity.csv")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()

    all_signals = build_signals_parity(engine, batch_id, args.start_date, args.end_date)
    symbols = sorted(all_signals["symbol"].unique())
    lb = (pd.Timestamp(args.start_date) - pd.Timedelta(days=25)).date().isoformat()
    ph = ",".join(["%s"] * len(symbols))
    bars = pd.read_sql(
        f"SELECT symbol, date, open, high, low, close, volume FROM stock_bars_daily "
        f"WHERE symbol IN ({ph}) AND date BETWEEN %s AND %s",
        engine, params=(*symbols, lb, args.end_date),
    )
    bars["trade_date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    piv = {c: bars.pivot_table(index="trade_date", columns="symbol", values=c, aggfunc="last")
           for c in ["open", "high", "low", "close", "volume"]}

    reg_map = load_regime_map_db(engine)
    rows: list[dict[str, Any]] = []
    for name in ["P0_PROD", "P2_PROD"]:
        sig = all_signals[all_signals["variant"] == name][["trade_date", "symbol", "selected", "rank", "score"]]
        sig = sig[sig["symbol"].isin(piv["close"].columns)].copy()
        LOGGER.info("=== Variante %s : %d signaux bruts ===", name, len(sig))
        cfg = build_config(args.start_date, args.end_date)
        eng = BacktestEngine(cfg)
        sig = _enrich_atr(sig, piv)
        res = eng.run(
            open_df=piv["open"], close=piv["close"], high=piv["high"], low=piv["low"],
            volume=piv["volume"], signals_df=sig,
        )
        m = _metrics(res, sig, reg_map, name)
        cap = capacity_attribution(sig, res, res.equity_curve.index, max_positions=cfg.max_positions)
        m.update({f"cap_{k}": v for k, v in cap.items()})
        rows.append(m)
        pd.set_option("display.width", 400); pd.set_option("display.max_columns", None)
        print(pd.DataFrame([m]).to_string(index=False))

    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False)
    print(f"\nCSV: {args.out}")


if __name__ == "__main__":
    main()
