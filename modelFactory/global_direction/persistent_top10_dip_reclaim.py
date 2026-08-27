"""modelFactory/global_direction/persistent_top10_dip_reclaim.py — reclaim research-only.

Expérience **research-only** : garder strictement le signal DIP gelé et comparer
l'entrée directe vs deux variantes de « reclaim » (confirmation de rebond).

Signal DIP gelé (détecté au close de J) :
    N = 4 ; X = 2%
    global_rank_20 >= 0.90 à J, J-1, J-2, J-3   (persist_4)
    ET close[J] / close[J-4] - 1 <= -0.02

start_price = close[J-4]
dip_price   = close[J]

Variantes (uniquement) :
    D0  : entrée directe après le DIP
    R50 : après J, attendre close[T] >= dip_price + 0.5*(start_price - dip_price)
          ET global_rank_20[T] >= 0.90 ; T > J ; max_wait = 10 séances
    R100: après J, attendre close[T] >= start_price
          ET global_rank_20[T] >= 0.90 ; T > J ; max_wait = 10 séances

Si aucune confirmation avant J+10 : signal expiré, aucune entrée.
Signal calculé au close T puis entrée selon le contrat PROD à la séance suivante.

Diagnostics produits :
1. Signal : nb DIP initiaux, % reclaim 50/100, % expirés, délai moyen/médian.
2. Depuis la vraie date d'entrée : D1..D10, BAD5, GOOD5, D10, D1, mean/median
   return, P(ret>0), PF, MFE, MAE.
3. Coût du retard : rebound_before_entry, remaining_return_after_entry,
   remaining_MFE.
4. Backtest portefeuille PROD-parity D0 vs R50 vs R100.

Aucun autre seuil de reclaim, aucun autre max_wait, aucun autre N/X.

Usage :
    python -m modelFactory.global_direction.persistent_top10_dip_reclaim --batch-id ...
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from database.connection import get_sqlalchemy_engine
from backtesting.simulator import BacktestEngine
from modelFactory.global_direction.config import resolve_global_direction_batch_id
from modelFactory.oracle.dataset import load_oracle_targets
from modelFactory.global_direction.dataset import DECILE_COL
from modelFactory.global_direction.persistent_top10_dip_portfolio import (
    RANK_COL, TOP10, N_DIP, X_DIP, build_config, _enrich_atr, _metrics, _load_regime_map,
)
from modelFactory.global_direction.persistent_top10_dip_parity import (
    BLOCKED_REGIMES, _schedule_local, capacity_attribution,
)

LOGGER = logging.getLogger(__name__)

HOLD = 20  # séances après entrée (fenêtre de détention)
MAX_WAIT = 10  # séances max entre J et la confirmation de reclaim

_FOLD_CUTS = [pd.Timestamp("2022-01-01"), pd.Timestamp("2023-01-01"),
              pd.Timestamp("2024-01-01"), pd.Timestamp("2025-01-01")]


def load_panel(engine: Any, batch_id: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Panel : labels Oracle (décile) à J + rank_20 + bars OHLCV/adj (lookback + forward)."""
    targets = load_oracle_targets(engine, batch_id, horizon=20)
    lab = targets[["prediction_date", "symbol", DECILE_COL]].rename(columns={"prediction_date": "date"})
    lab["date"] = pd.to_datetime(lab["date"], errors="coerce").dt.normalize()
    lab["symbol"] = lab["symbol"].astype(str).str.upper()

    rank = pd.read_sql(
        f"SELECT symbol, date, {RANK_COL} FROM global_rank_history WHERE date BETWEEN %s AND %s",
        engine, params=(start_date, end_date),
    )
    rank["date"] = pd.to_datetime(rank["date"], errors="coerce").dt.normalize()
    rank["symbol"] = rank["symbol"].astype(str).str.upper()

    lb = (pd.Timestamp(start_date) - pd.Timedelta(days=20)).date().isoformat()
    fwd = (pd.Timestamp(end_date) + pd.Timedelta(days=45)).date().isoformat()
    bars = pd.read_sql(
        "SELECT symbol, date, open, high, low, close, adj_close FROM stock_bars_daily "
        "WHERE date BETWEEN %s AND %s",
        engine, params=(lb, fwd),
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.dropna(subset=["date", "symbol", "close"])

    df = lab.merge(rank, on=["date", "symbol"], how="inner")
    df = df.merge(bars[["symbol", "date", "high", "low", "close", "adj_close"]],
                  on=["date", "symbol"], how="left")
    df = df[(df["date"] >= pd.Timestamp(start_date)) & (df["date"] <= pd.Timestamp(end_date))]
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    return df


def _per_symbol_paths(bars: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    """Indexe les bars par symbole (date/high/low/close) pour slicing."""
    out: dict[str, dict[str, np.ndarray]] = {}
    for sym, g in bars.sort_values("date").groupby("symbol"):
        out[sym] = {
            "date": g["date"].to_numpy(dtype="datetime64[ns]"),
            "high": g["high"].to_numpy(dtype=float),
            "low": g["low"].to_numpy(dtype=float),
            "close": g["close"].to_numpy(dtype=float),
        }
    return out


def _build_rank_index(panel: pd.DataFrame) -> dict[tuple[str, pd.Timestamp], float]:
    """Index (symbol, date) -> rank pour lookup rapide pendant le reclaim."""
    idx = {}
    for _, r in panel.iterrows():
        sym = str(r["symbol"])
        d = pd.Timestamp(r["date"]).normalize()
        v = r.get(RANK_COL)
        if pd.notna(v):
            idx[(sym, d)] = float(v)
    return idx


def _find_reclaim(
    sym: str, j: pd.Timestamp, start_price: float, dip_price: float, pct: float,
    paths: dict[str, dict[str, np.ndarray]],
    rank_index: dict[tuple[str, pd.Timestamp], float],
) -> tuple[pd.Timestamp | None, float | None, int | None]:
    """Cherche le premier T (J < T <= J+max_wait) avec close[T] >= seuil ET rank[T] >= 0.90.

    pct = 0.5 (R50) ou 1.0 (R100). Retourne (T, close[T], délai en séances)."""
    p = paths.get(sym)
    if p is None:
        return None, None, None
    dates = p["date"]
    j_np = np.datetime64(j)
    idx0 = int(np.searchsorted(dates, j_np, side="right"))
    if idx0 >= len(dates):
        return None, None, None
    idx_end = min(idx0 + MAX_WAIT, len(dates))
    threshold = dip_price + pct * (start_price - dip_price)
    for i in range(idx0, idx_end):
        d = pd.Timestamp(dates[i]).normalize()
        if not np.isfinite(p["close"][i]) or p["close"][i] <= 0:
            continue
        rk = rank_index.get((sym, d))
        if rk is None or not np.isfinite(rk) or rk < TOP10:
            continue
        if p["close"][i] >= threshold:
            return d, float(p["close"][i]), i - idx0 + 1
    return None, None, None


def forward_metrics_from_entry(
    sym: str, entry_date: pd.Timestamp, paths: dict[str, dict[str, np.ndarray]],
) -> dict[str, float | None]:
    """MFE / MAE / H20 depuis la vraie date d'entrée (entry_date), détention 20 séances."""
    p = paths.get(sym)
    if p is None:
        return {"h20": None, "mfe": None, "mae": None}
    dates = p["date"]
    idx = int(np.searchsorted(dates, np.datetime64(entry_date), side="right"))  # entrée à la clôture suivante
    entry_i = idx
    if entry_i >= len(dates) or entry_i + HOLD >= len(dates):
        return {"h20": None, "mfe": None, "mae": None}
    entry = p["close"][entry_i]
    if not np.isfinite(entry) or entry <= 0:
        return {"h20": None, "mfe": None, "mae": None}
    win_lo = entry_i + 1
    win_hi = entry_i + HOLD + 1
    closes = p["close"][win_lo:win_hi]
    highs = p["high"][win_lo:win_hi]
    lows = p["low"][win_lo:win_hi]
    if len(closes) < 1:
        return {"h20": None, "mfe": None, "mae": None}
    h20 = closes[-1] / entry - 1.0
    mfe = float(np.nanmax(highs / entry - 1.0)) if np.isfinite(highs).any() else None
    mae = float(np.nanmin(lows / entry - 1.0)) if np.isfinite(lows).any() else None
    return {"h20": h20, "mfe": mfe, "mae": mae}


def build_reclaim_rows(
    panel: pd.DataFrame,
    paths: dict[str, dict[str, np.ndarray]],
    rank_index: dict[tuple[str, pd.Timestamp], float],
) -> pd.DataFrame:
    """Construit les signaux D0/R50/R100 avec métriques forward depuis la vraie entrée."""
    df = panel.copy()
    df["top10"] = (df[RANK_COL] >= TOP10).astype(int)
    g_close = df.groupby("symbol")["close"]
    df["ret_4"] = df["close"] / g_close.shift(N_DIP) - 1.0
    df["persist_4"] = df.groupby("symbol")["top10"].transform(
        lambda x: x.rolling(N_DIP, min_periods=N_DIP).min())
    df["start_price"] = g_close.shift(N_DIP)  # close[J-4]
    df["dip_price"] = df["close"]             # close[J]

    dips = df[(df["persist_4"] == 1) & (df["ret_4"] <= -X_DIP)].copy()
    dips = dips.dropna(subset=["close", "start_price"])

    rows: list[dict[str, Any]] = []
    for _, r in dips.iterrows():
        sym = str(r["symbol"])
        j = pd.Timestamp(r["date"]).normalize()
        start_price = float(r["start_price"])
        dip_price = float(r["dip_price"])
        dec = int(r[DECILE_COL]) if pd.notna(r[DECILE_COL]) else None

        base = {
            "symbol": sym, "j": j, "decile": dec,
            "start_price": start_price, "dip_price": dip_price,
            "rebound_50": start_price + 0.5 * (start_price - dip_price),
            "rebound_100": start_price,
        }

        # D0 : entrée directe (entry_date = J+1)
        d0 = forward_metrics_from_entry(sym, j, paths)
        rows.append({**base, "strategy": "D0", "entry_date": j, "delay": 0,
                     "reclaim_price": dip_price, **d0,
                     "rebound_before_entry": 0.0})

        # R50
        t50, c50, d50 = _find_reclaim(sym, j, start_price, dip_price, 0.5, paths, rank_index)
        if t50 is not None:
            m50 = forward_metrics_from_entry(sym, t50, paths)
            reb50 = c50 / dip_price - 1.0 if dip_price > 0 else None
            rows.append({**base, "strategy": "R50", "entry_date": t50, "delay": d50,
                         "reclaim_price": c50, **m50, "rebound_before_entry": reb50})

        # R100
        t100, c100, d100 = _find_reclaim(sym, j, start_price, dip_price, 1.0, paths, rank_index)
        if t100 is not None:
            m100 = forward_metrics_from_entry(sym, t100, paths)
            reb100 = c100 / dip_price - 1.0 if dip_price > 0 else None
            rows.append({**base, "strategy": "R100", "entry_date": t100, "delay": d100,
                         "reclaim_price": c100, **m100, "rebound_before_entry": reb100})

    return pd.DataFrame(rows)


def signal_diagnostics(signals: pd.DataFrame) -> dict[str, Any]:
    """Diagnostic signal : DIP initiaux, % reclaim/expirés, délai moyen/médian."""
    n_dip = int(signals[signals["strategy"] == "D0"]["symbol"].nunique())
    # DIP initiaux = nombre de lignes D0 (une par DIP détecté)
    d0 = signals[signals["strategy"] == "D0"]
    n0 = int(len(d0))
    r50 = signals[signals["strategy"] == "R50"]
    r100 = signals[signals["strategy"] == "R100"]
    p50 = len(r50) / n0 if n0 else 0.0
    p100 = len(r100) / n0 if n0 else 0.0
    d50 = r50["delay"].dropna()
    d100 = r100["delay"].dropna()
    return {
        "n_dip_initial": n0,
        "pct_reclaim_50": round(100 * p50, 2),
        "pct_reclaim_100": round(100 * p100, 2),
        "pct_expired_50": round(100 * (1 - p50), 2),
        "pct_expired_100": round(100 * (1 - p100), 2),
        "delay_50_mean": round(float(d50.mean()), 2) if len(d50) else None,
        "delay_50_median": round(float(d50.median()), 2) if len(d50) else None,
        "delay_100_mean": round(float(d100.mean()), 2) if len(d100) else None,
        "delay_100_median": round(float(d100.median()), 2) if len(d100) else None,
    }


def metrics_per_strategy(signals: pd.DataFrame) -> pd.DataFrame:
    """Métriques depuis la vraie date d'entrée : déciles + forward."""
    out_rows: list[dict[str, Any]] = []
    for strat, g in signals.groupby("strategy"):
        sub = g.dropna(subset=["h20", "decile"]).copy()
        sub["_dec"] = sub["decile"].astype(int)
        h20 = g["h20"].dropna()
        dec = g["decile"].dropna().astype(int)
        mfe = g["mfe"].dropna()
        mae = g["mae"].dropna()
        bad5 = (sub["_dec"] <= 5).mean() if len(sub) else np.nan
        good5 = (sub["_dec"] >= 6).mean() if len(sub) else np.nan
        gains = h20[h20 > 0]
        losses = h20[h20 < 0]
        pf = float(gains.sum() / abs(losses.sum())) if len(gains) and len(losses) and losses.sum() != 0 else None
        dec_hist = {f"D{d}": int((dec == d).sum()) for d in range(1, 11)}
        out_rows.append({
            "strategy": strat, "n": int(len(g)),
            "mean_h20": float(h20.mean()) if len(h20) else None,
            "median_h20": float(h20.median()) if len(h20) else None,
            "p_positive": float((h20 > 0).mean()) if len(h20) else None,
            "pf": pf,
            "bad5_pct": float(bad5) if np.isfinite(bad5) else None,
            "good5_pct": float(good5) if np.isfinite(good5) else None,
            "mfe_mean": float(mfe.mean()) if len(mfe) else None,
            "mae_mean": float(mae.mean()) if len(mae) else None,
            **dec_hist,
        })
    return pd.DataFrame(out_rows)


def cost_of_delay(signals: pd.DataFrame) -> pd.DataFrame:
    """Coût du retard : rebound avant entrée, remaining après entrée, remaining MFE."""
    rows: list[dict[str, Any]] = []
    for strat, g in signals.groupby("strategy"):
        sub = g.dropna(subset=["rebound_before_entry", "h20", "mfe"])
        rows.append({
            "strategy": strat,
            "n": int(len(g)),
            "rebound_before_entry_mean": float(sub["rebound_before_entry"].mean()) if len(sub) else None,
            "rebound_before_entry_median": float(sub["rebound_before_entry"].median()) if len(sub) else None,
            "remaining_return_after_entry_mean": float(sub["h20"].mean()) if len(sub) else None,
            "remaining_return_after_entry_median": float(sub["h20"].median()) if len(sub) else None,
            "remaining_mfe_mean": float(sub["mfe"].mean()) if len(sub) else None,
        })
    return pd.DataFrame(rows)


def build_signals_for_backtest(signals: pd.DataFrame, name: str, reg_map: dict[pd.Timestamp, str]) -> pd.DataFrame:
    """Signaux portefeuille pour la variante (trade_date = entry_date) + veto régime PROD.

    Le veto régime PROD (close_only + cash_only) est le comportement PROD existant
    (``allow_new_entries=False``) — appliqué ici sur la date du signal (entry_date),
    identiquement aux 3 variantes, pour une parité fidèle avec l'audit P0/P2.
    """
    sub = signals[signals["strategy"] == name].copy()
    sub["trade_date"] = pd.to_datetime(sub["entry_date"]).dt.normalize()
    sub["regime"] = sub["trade_date"].map(reg_map).fillna("unknown")
    sub = sub[~sub["regime"].isin(BLOCKED_REGIMES)].copy()
    s = pd.DataFrame({
        "trade_date": sub["trade_date"],
        "symbol": sub["symbol"],
        "selected": True,
        "rank": 0.99,
        "score": 0.99,
        "variant": name,
    })
    return s


def main() -> None:
    parser = argparse.ArgumentParser(description="persistent_top10_dip reclaim (research-only).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2024-12-31")
    parser.add_argument("--out", default="artifacts/persistent_top10_dip_reclaim.csv")
    parser.add_argument("--out-backtest", default="artifacts/persistent_top10_dip_reclaim_backtest.csv")
    parser.add_argument("--diag-only", action="store_true",
                        help="Ne faire que le diagnostic signal (pas de backtest).")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")
    engine = get_sqlalchemy_engine()

    panel = load_panel(engine, batch_id, args.start_date, args.end_date)
    # bars nécessaires (lookback + forward) : toutes les dates, pas seulement
    # celles avec labels (le reclaim scrute J+1..J+10).
    lb = (pd.Timestamp(args.start_date) - pd.Timedelta(days=20)).date().isoformat()
    fwd = (pd.Timestamp(args.end_date) + pd.Timedelta(days=45)).date().isoformat()
    bars = pd.read_sql(
        "SELECT symbol, date, open, high, low, close, adj_close FROM stock_bars_daily "
        "WHERE date BETWEEN %s AND %s",
        engine, params=(lb, fwd),
    )
    bars["date"] = pd.to_datetime(bars["date"], errors="coerce").dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str).str.upper()
    bars = bars.dropna(subset=["date", "symbol", "close"])
    paths = _per_symbol_paths(bars)
    rank_index = _build_rank_index(panel)

    signals = build_reclaim_rows(panel, paths, rank_index)
    sig_diag = signal_diagnostics(signals)
    print("=== DIAGNOSTIC SIGNAL ===")
    for k, v in sig_diag.items():
        print(f"{k}: {v}")

    met = metrics_per_strategy(signals)
    print("\n=== MÉTRIQUES DEPUIS VRAIE ENTRÉE ===")
    pd.set_option("display.width", 400); pd.set_option("display.max_columns", None)
    print(met.to_string(index=False))

    cod = cost_of_delay(signals)
    print("\n=== COÛT DU RETARD ===")
    print(cod.to_string(index=False))

    if args.diag_only:
        met.to_csv(args.out, index=False)
        print(f"\nCSV métriques (diag only): {args.out}")
        return

    # Backtest portefeuille PROD-parity
    reg_map = _load_regime_map()
    all_signals = pd.concat([
        build_signals_for_backtest(signals, "D0", reg_map),
        build_signals_for_backtest(signals, "R50", reg_map),
        build_signals_for_backtest(signals, "R100", reg_map),
    ], ignore_index=True)

    symbols = sorted(all_signals["symbol"].unique())
    ph = ",".join(["%s"] * len(symbols))
    b2 = pd.read_sql(
        f"SELECT symbol, date, open, high, low, close, volume FROM stock_bars_daily "
        f"WHERE symbol IN ({ph}) AND date BETWEEN %s AND %s",
        engine, params=(*symbols, lb, args.end_date),
    )
    b2["trade_date"] = pd.to_datetime(b2["date"], errors="coerce").dt.normalize()
    b2["symbol"] = b2["symbol"].astype(str).str.upper()
    piv = {c: b2.pivot_table(index="trade_date", columns="symbol", values=c, aggfunc="last")
           for c in ["open", "high", "low", "close", "volume"]}

    bt_rows: list[dict[str, Any]] = []
    for name in ["D0", "R50", "R100"]:
        sig = all_signals[all_signals["variant"] == name][["trade_date", "symbol", "selected", "rank", "score"]]
        sig = sig[sig["symbol"].isin(piv["close"].columns)].copy()
        LOGGER.info("=== Variante %s : %d signaux ===", name, len(sig))
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
        bt_rows.append(m)
        print(pd.DataFrame([m]).to_string(index=False))

    pd.DataFrame(bt_rows).to_csv(args.out_backtest, index=False)
    print(f"\nCSV backtest: {args.out_backtest}")

    # Sauvegarde combinée
    met.to_csv(args.out, index=False)
    print(f"CSV métriques: {args.out}")


if __name__ == "__main__":
    main()
