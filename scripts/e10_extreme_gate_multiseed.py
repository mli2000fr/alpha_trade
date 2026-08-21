"""E10 — Extreme Gate Multi-Seed Stability : distribution sur sélections aléatoires.

CONTEXTE (spec user 2026-08-20) : E9 a montré une variance de seed catastrophique
(TOP10 seed7 = 78% vs seed42 = 171%) et l'absence de frontière nette (10-20% ≈ top10).
Le test décisif n'est plus le meilleur run mais la DISTRIBUTION sur sélections aléatoires :
« le pool lui-même reste-t-il bon EN MOYENNE ? ».

MÉTHODE (3 univers gelés, AUCUN tuning) :
  - NO_GATE         : univers complet, random within
  - EXTREME_TOP10   : top10% proba_extreme, random within
  - EXTREME_TOP20   : top20% proba_extreme, random within
  ≥20 seeds (10 min) : même moteur m8, mêmes coûts/exits/lifecycle LONG, même période.
  On ne regarde PAS le meilleur run : distribution complète.

SORTIE PRINCIPALE (par univers) :
  - médiane Return/PF/Sharpe/DD/expectancy
  - P10 / P25 / P75 / P90
  - pire seed ; % seeds positifs ; % seeds où TOP10 bat TOP20
  - stabilité par semestre (mean PnL + % seeds positifs par semestre)

LECTURE (pré-fixée par user) :
  - TOP20 median PF > NO_GATE ; TOP20 P25 PF > ~1 ; TOP20 > NO_GATE sur majorité seeds
    → le gate Extreme est réel (même si l'ordre interne est peu informatif).
  - TOP10 ≈ TOP20 → choisir TOP20 (moins dépendant d'une frontière arbitraire,
    plus de candidats pour m8).
  - médiane bonne mais intervalle énorme (ex. Return 20%-180%) → le gate améliore
    statistiquement l'univers mais la stratégie reste trop dépendante du hasard.
  - AUCUN nouveau ranker pour « résoudre » la variance (risque d'overfit).

Sortie : print + artifacts/models/oracle/e10_results.parquet
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

OUT = Path("artifacts/models/oracle/e10_results.parquet")
INITIAL_EQUITY = 100_000.0
N_SEEDS = 20

UNIVERSES = [("NO_GATE", 0.00, 1.01), ("EXTREME_TOP10", 0.90, 1.01), ("EXTREME_TOP20", 0.80, 1.01)]


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


def run_bt(sig: pd.DataFrame, pivots: dict) -> dict:
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
    closed = closed.copy()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"]).dt.normalize()
    closed["semester"] = closed["entry_date"].dt.year.astype(str) + \
        np.where(closed["entry_date"].dt.month <= 6, "H1", "H2")
    closed["pnl"] = pnl
    sem = closed.groupby("semester")["pnl"].sum()
    return {
        "return_pct": ret, "pf": pf, "sharpe": sharpe, "max_dd_pct": dd,
        "expectancy": float(pnl.mean()) if n else 0.0, "n_trades": n,
        "semesters": sem,
    }


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")
    print(f"seeds: {N_SEEDS} × {len(UNIVERSES)} univers = {N_SEEDS*len(UNIVERSES)} runs moteur")

    # Collecter tous les runs
    records = []  # (univers, seed, metrics)
    sem_records = []  # (univers, seed, semester, pnl)
    for univ, lo, hi in UNIVERSES:
        for seed in range(N_SEEDS):
            r = run_bt(build_signals(pool, lo, hi, seed), pivots)
            rec = {"univ": univ, "seed": seed, **{k: r[k] for k in
                    ("return_pct", "pf", "sharpe", "max_dd_pct", "expectancy", "n_trades")}}
            records.append(rec)
            for sem, pnl in r["semesters"].items():
                sem_records.append({"univ": univ, "seed": seed, "semester": sem, "pnl": float(pnl)})
            if seed % 5 == 0:
                print(f"  {univ} seed={seed} Ret={r['return_pct']:.0f}% PF={r['pf']:.2f}", flush=True)

    dfr = pd.DataFrame(records)
    dfs = pd.DataFrame(sem_records)

    # ── Distribution par univers ──
    print("\n" + "=" * 130)
    print(f"E10 — DISTRIBUTION MULTI-SEEDS ({N_SEEDS} seeds) — gate Extreme LONG-only, m8")
    print("=" * 130)
    dist = {}
    for univ, _, _ in UNIVERSES:
        sub = dfr[dfr["univ"] == univ]
        dist[univ] = {
            "median_return": float(sub["return_pct"].median()),
            "p10_return": float(sub["return_pct"].quantile(0.10)),
            "p25_return": float(sub["return_pct"].quantile(0.25)),
            "p75_return": float(sub["return_pct"].quantile(0.75)),
            "p90_return": float(sub["return_pct"].quantile(0.90)),
            "min_return": float(sub["return_pct"].min()),
            "median_pf": float(sub["pf"].median()),
            "p25_pf": float(sub["pf"].quantile(0.25)),
            "median_sharpe": float(sub["sharpe"].median()),
            "median_dd": float(sub["max_dd_pct"].median()),
            "median_expect": float(sub["expectancy"].median()),
            "median_trades": float(sub["n_trades"].median()),
            "pct_positive": float((sub["return_pct"] > 0).mean()),
        }
    print(f"  {'univ':<14} {'medRet%':>8} {'P10':>7} {'P25':>7} {'P75':>7} {'P90':>7} {'pire':>7} | "
          f"{'medPF':>6} {'P25PF':>6} {'medSh':>6} {'medDD%':>7} {'medExp$':>8} {'medN':>5} {'%pos':>6}")
    print("-" * 130)
    for univ, _, _ in UNIVERSES:
        d = dist[univ]
        print(f"  {univ:<14} {d['median_return']:>8.1f} {d['p10_return']:>7.1f} {d['p25_return']:>7.1f} "
              f"{d['p75_return']:>7.1f} {d['p90_return']:>7.1f} {d['min_return']:>7.1f} | "
              f"{d['median_pf']:>6.2f} {d['p25_pf']:>6.2f} {d['median_sharpe']:>6.2f} "
              f"{d['median_dd']:>7.1f} {d['median_expect']:>8.2f} {d['median_trades']:>5.0f} {100*d['pct_positive']:>5.0f}%")

    # ── TOP10 vs TOP20 : % seeds où TOP10 bat TOP20 ──
    print("\n" + "=" * 130)
    print("TOP10 vs TOP20 — % seeds où TOP10 bat TOP20")
    print("=" * 130)
    piv = dfr.pivot(index="seed", columns="univ", values="return_pct")
    if "EXTREME_TOP10" in piv and "EXTREME_TOP20" in piv:
        beat = float((piv["EXTREME_TOP10"] > piv["EXTREME_TOP20"]).mean())
        print(f"  TOP10 bat TOP20 sur {100*beat:.0f}% des seeds (Return)")
        med10, med20 = dist["EXTREME_TOP10"]["median_return"], dist["EXTREME_TOP20"]["median_return"]
        print(f"  median Return : TOP10 {med10:.1f}% vs TOP20 {med20:.1f}%")
        if abs(med10 - med20) <= 15:
            print("  → distributions proches → privilégier TOP20 (frontière moins arbitraire, + de candidats m8)")

    # ── Stabilité par semestre (mean PnL + % seeds positifs) ──
    print("\n" + "=" * 130)
    print("Stabilité par semestre (mean PnL $ et % seeds positifs)")
    print("=" * 130)
    sems = sorted(dfs["semester"].unique())
    print(f"  {'semester':<10}" + "".join(f"{u:>22}" for u, _, _ in UNIVERSES))
    for s in sems:
        row = f"{s:<10}"
        for u, _, _ in UNIVERSES:
            sub = dfs[(dfs["univ"] == u) & (dfs["semester"] == s)]
            row += f"{sub['pnl'].mean():>12.0f}${100*(sub['pnl']>0).mean():>5.0f}%"
        print(row)

    # ── VERDICT (lecture pré-fixée) ──
    print("\n" + "=" * 130)
    print("LECTURE (pré-fixée)")
    print("=" * 130)
    d_ng, d_t20 = dist["NO_GATE"], dist["EXTREME_TOP20"]
    v1 = d_t20["median_pf"] > d_ng["median_pf"]
    v2 = d_t20["p25_pf"] > 1.0
    # % seeds TOP20 > NO_GATE
    if "NO_GATE" in piv and "EXTREME_TOP20" in piv:
        beat_ng = float((piv["EXTREME_TOP20"] > piv["NO_GATE"]).mean())
    else:
        beat_ng = float("nan")
    v3 = beat_ng >= 0.5
    # dispersion : intervalle P10-P90
    spread = d_t20["p90_return"] - d_t20["p10_return"]
    huge = spread > 80  # ex. 20%-180% → intervalle 160
    print(f"  V1 TOP20 median PF > NO_GATE   : {v1}  ({d_t20['median_pf']:.2f} vs {d_ng['median_pf']:.2f})")
    print(f"  V2 TOP20 P25 PF > 1.0          : {v2}  (P25 PF = {d_t20['p25_pf']:.2f})")
    print(f"  V3 TOP20 > NO_GATE (majorité)  : {v3}  ({100*beat_ng:.0f}% des seeds)")
    print(f"  Dispersion TOP20 (P90−P10)     : {spread:.0f} pts {'⚠️ ÉNORME' if huge else ''}")

    print("\n  CONCLUSION :")
    if v1 and v2 and v3 and not huge:
        print("  → Gate Extreme RÉEL : le pool top20% améliore l'univers en moyenne avec une")
        print("    dispersion raisonnable. L'ordre interne est secondaire mais le gate porte la valeur.")
    elif v1 and v2 and v3 and huge:
        print("  → Gate améliore statistiquement l'univers MAIS la stratégie portefeuille reste")
        print("    TROP dépendante du hasard de sélection → pas considérée robuste (dispersion énorme).")
    else:
        print("  → Gate Extreme NON confirmé : les critères de robustesse ne passent pas.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    dfr.to_parquet(OUT, index=False)
    dfs.to_parquet(str(OUT).replace(".parquet", "_semesters.parquet"), index=False)
    print(f"\npersisted: {OUT} (+ _semesters)")


if __name__ == "__main__":
    main()
