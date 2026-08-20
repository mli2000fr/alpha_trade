"""E9 — Extreme Gate Validation : le GATE Oracle top10% est-il un mécanisme LONG robuste ?

CONTEXTE (spec user 2026-08-20) : E8 a déplacé le centre de gravité. Le signal qui
survit est : « être dans le top 10% de proba_extreme suffit à définir un univers LONG
économiquement intéressant ». Random-sort ≈ Oracle-sort dans le pool → l'ordre interne
est secondaire. La question n'est plus « comment mieux classer les extrêmes ? » mais
« le gate lui-même est-il robuste comme mécanisme de sélection LONG ? ».

MÉTHODE (très simple, AUCUN tuning, même moteur m8 / coûts / lifecycle LONG ; pas de
Y3, pas d'EV, pas de rank B25) :
  - NO_GATE            : univers de départ (tous les candidats OOS), random within
  - EXTREME_TOP10      : gate Extreme top10% (proba_extreme), random within  ← CANDIDAT
  - EXTREME_TOP10_CTRL : même gate, random within (contrôle explicite — devrait ≈ TOP10)
  - DIAGNOSTIC 10-20%  : tranche juste sous le gate (proba_extreme 10-20%), random within
                        → si nettement moins bonne, frontière économique autour du top10 ;
                        → si aussi bonne, le choix top10 peut être arbitraire (prudence).

MÉTRIQUES : Return, PF, Sharpe, MaxDD, expectancy, N trades, win, sem+, turnover,
concentration PnL (Top5). Par semestre + rolling 12m (EXTREME_TOP10).

GATES (fixés AVANT) :
  G1 : expectancy(EXTREME_TOP10) > expectancy(NO_GATE)  → valeur incrémentale du gate
  G2 : PF(EXTREME_TOP10) > PF(NO_GATE)
  G3 : EXTREME_TOP10 positif sur majorité des semestres (>50%)
  G4 : MaxDD(EXTREME_TOP10) pas catastrophique (<= 1.3 × |MaxDD(NO_GATE)| + marge)
  G5 : pas de jackpot (Top5 <= 50% du PnL) + pas 2025/26-only (≥1 semestre 2023-24 positif)
  G6 : majorité des fenêtres rolling 12m positives
  DIAG : tranche 10-20% nettement moins bonne que top10 → frontière confirmée

SHORT : SÉPARÉ (chantier payoff/exits/MAE — PAS un problème de ranking). Hors périmètre E9.

Sortie : print + artifacts/models/oracle/e9_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.simulator import BacktestConfig, BacktestEngine
from scripts.e6_b2_ev_long_backtest import (
    END,
    START,
    load_pivots,
    load_pool,
)
from scripts.e6_b3_rolling_stability import WINDOWS_12M

OUT = Path("artifacts/models/oracle/e9_results.parquet")
INITIAL_EQUITY = 100_000.0

# (label, lo_pe, hi_pe) — rang proba_extreme pct sur le pool complet
VARIANTS = [
    ("NO_GATE", 0.00, 1.01),
    ("EXTREME_TOP10", 0.90, 1.01),
    ("EXTREME_TOP10_CTRL", 0.90, 1.01),
    ("DIAG_10_20", 0.80, 0.90),
]


def make_engine() -> BacktestEngine:
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(), end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY, max_positions=8,
        atr_risk_stop_multiple=3.5, tp_atr_multiple=4.0, tp_max_pct=0.13,
        trailing_stop_long_pct=0.07, trailing_stop_short_pct=None,
        use_canonical_costs=True, entry_limit_offset_pct=0.0,
        min_score_threshold=0.0, use_live_protection_logic=True,
    )
    return BacktestEngine(cfg)


def build_signals(pool: pd.DataFrame, lo: float, hi: float, seed: int) -> pd.DataFrame:
    """Candidats du pool complet dans la tranche [lo,hi) de proba_extreme, random within."""
    df = pool.copy()
    df["_pe_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    df = df[(df["_pe_pct"] >= lo) & (df["_pe_pct"] < hi)]
    rng = np.random.default_rng(seed)
    df["_rand"] = rng.random(len(df))
    df["rank"] = df.groupby("date")["_rand"].rank(ascending=False)
    df["score"] = df["proba_extreme"]
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = "buy"
    return sig


def run_bt(sig: pd.DataFrame, pivots: dict, label: str) -> dict:
    res = make_engine().run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    eq = res.equity_curve
    closed = res.closed_trades_df
    final = float(eq.iloc[-1]) if len(eq) else INITIAL_EQUITY
    ret = (final / INITIAL_EQUITY - 1.0) * 100.0
    rets = eq.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) > 1 else 0.0
    pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
    n = len(pnl)
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    pf = gp / gn if gn > 0 else float("inf")
    notional = float((pd.to_numeric(closed.get("quantity", pd.Series(dtype=float)), errors="coerce").fillna(0) *
                      pd.to_numeric(closed.get("entry_price", pd.Series(dtype=float)), errors="coerce").fillna(0)).sum()) if n else 0.0
    avg_eq = float(eq.mean()) if len(eq) else INITIAL_EQUITY
    turnover = (notional / avg_eq) / max(len(eq) / 252.0, 0.01) if avg_eq > 0 else 0.0
    # Concentration Top5
    top5_pct = float(pnl.sort_values(ascending=False).head(5).sum() / pnl.sum()) if n and pnl.sum() != 0 else float("nan")
    closed = closed.copy()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"]).dt.normalize()
    closed["semester"] = closed["entry_date"].dt.year.astype(str) + \
        np.where(closed["entry_date"].dt.month <= 6, "H1", "H2")
    closed["pnl"] = pnl
    sem = closed.groupby("semester").agg(n=("pnl", "size"), pnl=("pnl", "sum"))
    n_sem = len(sem); n_pos = int((sem["pnl"] > 0).sum()) if n_sem else 0
    return {
        "bench": label, "return_pct": ret, "pf": pf, "sharpe": sharpe, "max_dd_pct": dd,
        "n_trades": n, "expectancy": float(pnl.mean()) if n else 0.0,
        "win_rate": float((pnl > 0).mean()) if n else 0.0, "turnover": turnover,
        "top5_pct": top5_pct, "n_semesters": n_sem, "n_pos_semesters": n_pos,
        "semesters": sem, "closed": closed, "equity": eq,
    }


def window_metrics(eq: pd.Series, trades: pd.DataFrame, w_start: pd.Timestamp, w_end: pd.Timestamp) -> dict:
    eq_w = eq.loc[(eq.index >= w_start) & (eq.index <= w_end)]
    ret = float(eq_w.iloc[-1] / eq_w.iloc[0] - 1.0) * 100.0 if len(eq_w) > 1 else 0.0
    t = trades[(trades["entry_date"] >= w_start) & (trades["entry_date"] <= w_end)]
    pnl = pd.to_numeric(t["pnl"], errors="coerce").fillna(0.0)
    return {"window": f"{w_start.date()}→{w_end.date()}", "return_pct": ret, "n": len(pnl),
            "pnl": float(pnl.sum())}


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    # pool complet (avec et sans gate) : garder y3_long dispo pour le moteur
    pool = pool.dropna(subset=["y3_long"])
    print(f"pool complet: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()}")
    for lo, hi in [(0.90, 1.01), (0.80, 0.90), (0.00, 1.01)]:
        n_in = ((pool.groupby("date")["proba_extreme"].rank(pct=True) >= lo) &
                (pool.groupby("date")["proba_extreme"].rank(pct=True) < hi)).sum()
        print(f"  tranche [{lo:.2f},{hi:.2f}) : {n_in:,} candidats")

    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"OHLCV : {len(symbols)} symboles | {pivots['close'].shape[0]} jours")

    print("\n=== E9 — GATE EXTREME VALIDATION (LONG-only, m8, random within) ===", flush=True)
    results = {}
    for label, lo, hi in VARIANTS:
        seed = 42 if label == "EXTREME_TOP10_CTRL" else 43 if label == "NO_GATE" else 7
        print(f"=== {label} ===", flush=True)
        results[label] = run_bt(build_signals(pool, lo, hi, seed), pivots, label)
        r = results[label]
        print(f"  Return={r['return_pct']:.2f}% PF={r['pf']:.2f} Sharpe={r['sharpe']:.2f} "
              f"MaxDD={r['max_dd_pct']:.2f}% trades={r['n_trades']} expect={r['expectancy']:.2f}$ "
              f"win={100*r['win_rate']:.1f}% turnover={r['turnover']:.1f}x Top5={100*r['top5_pct']:.1f}% "
              f"sem+={r['n_pos_semesters']}/{r['n_semesters']}", flush=True)

    print("\n" + "=" * 130)
    print("Table comparée — valeur du gate Extreme")
    print("=" * 130)
    hdr = f"{'bench':<22} {'n':>5} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'MaxDD%':>8} {'expect$':>8} {'win%':>6} {'Top5%':>7} {'sem+':>6}"
    print(hdr); print("-" * 130)
    for label, _, _ in VARIANTS:
        r = results[label]
        print(f"{label:<22} {r['n_trades']:>5} {r['return_pct']:>8.1f} {r['pf']:>6.2f} {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>8.1f} {r['expectancy']:>8.2f} {100*r['win_rate']:>6.1f} "
              f"{100*r['top5_pct']:>7.1f} {r['n_pos_semesters']:>3}/{r['n_semesters']}")

    # Par semestre
    print("\n" + "=" * 130)
    print("PnL par semestre ($)")
    print("=" * 130)
    sems = sorted(set().union(*[results[l]["semesters"].index for l, _, _ in VARIANTS]))
    print(f"{'semester':<10}" + "".join(f"{lbl:>14}" for lbl, _, _ in VARIANTS))
    for s in sems:
        row = f"{s:<10}"
        for lbl, _, _ in VARIANTS:
            if s in results[lbl]["semesters"].index:
                row += f"{results[lbl]['semesters'].loc[s,'pnl']:>13.0f}$"
            else:
                row += f"{'—':>14}"
        print(row)

    # Rolling 12m EXTREME_TOP10
    print("\n" + "=" * 130)
    print("Rolling 12m — EXTREME_TOP10")
    print("=" * 130)
    rows12 = []
    for w_start, w_end in WINDOWS_12M:
        rows12.append(window_metrics(results["EXTREME_TOP10"]["equity"], results["EXTREME_TOP10"]["closed"], w_start, w_end))
    for r in rows12:
        print(f"  {r['window']:<24} Ret={r['return_pct']:>7.1f}% n={r['n']:>4} PnL={r['pnl']:>9.0f}")
    n_pos_12 = sum(1 for r in rows12 if r["return_pct"] > 0)

    # ── GATES ──
    print("\n" + "=" * 130)
    print("GATES (fixés avant de regarder les résultats)")
    print("=" * 130)
    ng, xt = results["NO_GATE"], results["EXTREME_TOP10"]
    g1 = xt["expectancy"] > ng["expectancy"]
    g2 = xt["pf"] > ng["pf"]
    g3 = xt["n_pos_semesters"] > 0.5 * xt["n_semesters"]
    g4 = abs(xt["max_dd_pct"]) <= 1.3 * abs(ng["max_dd_pct"]) + 5.0
    sem_23_24 = [s for s in sems if s.startswith(("2023", "2024"))]
    pos_23_24 = sum(1 for s in sem_23_24 if s in xt["semesters"].index and xt["semesters"].loc[s, "pnl"] > 0)
    g5 = (not np.isnan(xt["top5_pct"])) and xt["top5_pct"] <= 0.50 and pos_23_24 >= 1
    g6 = n_pos_12 >= len(rows12) / 2
    # DIAG : tranche 10-20% vs top10
    diag = results["DIAG_10_20"]
    diag_ok = diag["expectancy"] < xt["expectancy"]

    print(f"G1 (gate expectancy > univers)     : {g1}  ({xt['expectancy']:.2f} vs {ng['expectancy']:.2f})")
    print(f"G2 (gate PF > univers PF)          : {g2}  ({xt['pf']:.2f} vs {ng['pf']:.2f})")
    print(f"G3 (gate >50% semestres +)         : {g3}  ({xt['n_pos_semesters']}/{xt['n_semesters']})")
    print(f"G4 (gate DD <= 1.3×univers+marge)  : {g4}  ({abs(xt['max_dd_pct']):.2f}% vs {abs(ng['max_dd_pct']):.2f}%)")
    print(f"G5 (pas jackpot + pas 25/26-only)  : {g5}  (Top5={100*xt['top5_pct']:.1f}%, 2023-24: {pos_23_24}/{len(sem_23_24)})")
    print(f"G6 (majorité rolling 12m +)        : {g6}  ({n_pos_12}/{len(rows12)})")
    print(f"DIAG (tranche 10-20% < top10)      : {diag_ok}  ({diag['expectancy']:.2f} vs {xt['expectancy']:.2f})")

    n_pass = sum([g1, g2, g3, g4, g5, g6])
    print(f"\nGATES PASSÉS : {n_pass}/6" + (f" + DIAG {'✅' if diag_ok else '❌'}" if True else ""))
    if n_pass >= 5 and g1 and g2 and g3:
        print("=> GATE EXTREME confirmé : mécanisme LONG robuste et à valeur incrémentale.")
    elif n_pass >= 4:
        print("=> GATE EXTREME acceptable avec réserves.")
    else:
        print("=> GATE EXTREME non confirmé — prudence.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{k: v for k, v in r.items() if k not in ("semesters", "closed", "equity")}
                  for r in results.values()]).to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
