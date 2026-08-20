"""E6-B4 — EV comme RANKING pur : EV_TOP20 trié PAR EV (levée de l'ambiguïté mécanique).

PROBLÈME IDENTIFIÉ (spec user 2026-08-20) :
  Le `EV_TOP20` testé en B2/B3 était hybride : filtre des candidats par EV, MAIS le
  moteur triait/entrait ensuite par RANG Y3 (score brut). Si un candidat a un bon EV
  mais un score Y3 bas, le moteur ne l'exécute jamais → « EV_ONLY s'éteint » en
  2025-26 pourrait être une conséquence d'ARCHITECTURE, pas une disparition du signal.

  EV_TOP20 actuel = filtre EV ↓ tri par score Y3 ↓ top 8   (HYBRIDE)
  EV_TOP20_EVSORT = filtre EV ↓ tri PAR EV ↓ top 8 EV       (EV comme RANKING PUR)

TEST E6-B4 (un seul, sans grille ni optimisation) :
  EV_TOP20_EVSORT contre les politiques gelées. Même m8, coûts, exits, folds,
  même Platt OOF, mêmes estimations train-only. Aucun changement de TOP20,
  aucun seuil supplémentaire.

INTERPRÉTATION (pré-fixée) :
  - Si les EV_ONLY entrent mais restent mauvais en 2025-26 → EV marginal RÉELLEMENT éteint → clôturer EV.
  - Si les EV_ONLY entrent et améliorent plusieurs périodes → B2/B3 ne testaient pas un vrai EV-ranking.
  - Si sort_by_EV dégrade globalement → garder le ranking Y3 simple.

COMPARATEURS : RANK_TOP20 (Y3), RANK_TOP10 (Y3), EV_TOP20 (hybride, réf),
              EV_TOP20_EVSORT (nouveau : tri par EV).

Sortie : print + artifacts/models/oracle/e6_b4_results.parquet
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
    add_ev_features,
    load_pivots,
    load_pool,
)

OUT = Path("artifacts/models/oracle/e6_b4_results.parquet")
INITIAL_EQUITY = 100_000.0


def build_signals_evsort(pool: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Variante avec tri PAR EV : le `rank` passé au moteur = rang EV_LONG."""
    df = pool.copy()
    df["_ev_rank_pct"] = df.groupby("date")["EV_LONG"].rank(pct=True)
    if variant == "EV_TOP20_EVSORT":
        df = df[df["_ev_rank_pct"] >= 0.80]
    elif variant == "EV_TOP10_EVSORT":
        df = df[df["_ev_rank_pct"] >= 0.90]
    else:
        raise ValueError(f"variante non supportée: {variant}")
    # Tri du moteur par rang EV (1 = meilleur EV) au lieu du rang Y3
    df["rank"] = df.groupby("date")["EV_LONG"].rank(ascending=False)
    df["score"] = df["EV_LONG"]
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20", "p_cal", "E_gain", "E_loss", "EV_LONG"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = "buy"
    return sig


def build_signals_y3(pool: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Réplique build_signals de E6-B2 (filtre EV, tri Y3) + RANK par Y3."""
    from scripts.e6_b2_ev_long_backtest import build_signals as _bs
    return _bs(pool, variant)


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
    # Semestre par date d'entrée
    sem = pd.DataFrame()
    if n:
        c = closed.copy()
        c["entry_date"] = pd.to_datetime(c["entry_date"]).dt.normalize()
        c["semester"] = c["entry_date"].dt.year.astype(str) + np.where(c["entry_date"].dt.month <= 6, "H1", "H2")
        c["pnl"] = pd.to_numeric(c["pnl"], errors="coerce").fillna(0.0)
        sem = c.groupby("semester").agg(pnl=("pnl", "sum"), n=("pnl", "size"))
    n_sem = len(sem); n_pos = int((sem["pnl"] > 0).sum()) if n_sem else 0
    return {
        "bench": label, "return_pct": ret, "sharpe": sharpe, "pf": pf, "max_dd_pct": dd,
        "n_trades": n, "expectancy": float(pnl.mean()) if n else 0.0,
        "n_semesters": n_sem, "n_pos_semesters": n_pos, "semesters": sem, "closed": closed,
    }


def classify_evonly(trades: pd.DataFrame, pool: pd.DataFrame, label: str) -> pd.DataFrame:
    """Classe chaque trade exécuté : COMMON / EV_ONLY / RANK_ONLY (R20 = top20 Y3)."""
    pool = pool.copy()
    pool["date"] = pd.to_datetime(pool["date"]).dt.normalize()
    pool["_rk20"] = pool.groupby("date")["_proba_catboost"].rank(pct=True) >= 0.80
    pool["_ev20"] = pool.groupby("date")["EV_LONG"].rank(pct=True) >= 0.80
    flags = pool.groupby(["symbol", "date"]).agg(rk20=("_rk20", "max"), ev20=("_ev20", "max")).reset_index()
    flags.columns = ["symbol", "signal_date", "rk20", "ev20"]
    t = trades.copy()
    t["signal_date"] = pd.to_datetime(t["signal_date"]).dt.normalize()
    t["symbol"] = t["symbol"].astype(str)
    t = t.merge(flags, on=["symbol", "signal_date"], how="left")
    t["rk20"] = t["rk20"].fillna(False).astype(bool)
    t["ev20"] = t["ev20"].fillna(False).astype(bool)
    t["group"] = np.where(t["rk20"] & t["ev20"], "COMMON",
                          np.where(t["ev20"] & ~t["rk20"], "EV_ONLY",
                                   np.where(t["rk20"] & ~t["ev20"], "RANK_ONLY", "OUTSIDE")))
    t["bench"] = label
    return t


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy().dropna(subset=["y3_long"])
    pool = add_ev_features(pool, feature_columns)
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")

    runs = {
        "RANK_TOP20": build_signals_y3(pool, "RANK_TOP20"),
        "RANK_TOP10": build_signals_y3(pool, "RANK_TOP10"),
        "EV_TOP20_hybrid": build_signals_y3(pool, "EV_TOP20"),
        "EV_TOP20_EVSORT": build_signals_evsort(pool, "EV_TOP20_EVSORT"),
        "EV_TOP10_EVSORT": build_signals_evsort(pool, "EV_TOP10_EVSORT"),
    }

    print("\n=== E6-B4 — EV comme RANKING pur (tri par EV) ===", flush=True)
    results = {}
    for label, sig in runs.items():
        print(f"=== {label} ===", flush=True)
        results[label] = run_bt(sig, pivots, label)
        r = results[label]
        print(f"  Return={r['return_pct']:.2f}% PF={r['pf']:.2f} Sharpe={r['sharpe']:.2f} "
              f"MaxDD={r['max_dd_pct']:.2f}% trades={r['n_trades']} expect={r['expectancy']:.2f}$ "
              f"sem+={r['n_pos_semesters']}/{r['n_semesters']}", flush=True)

    print("\n" + "=" * 120)
    print("Table comparée")
    print("=" * 120)
    hdr = f"{'bench':<18} {'Return%':>9} {'PF':>7} {'Sharpe':>7} {'MaxDD%':>9} {'trades':>7} {'expect$':>8} {'sem+':>6}"
    print(hdr); print("-" * 120)
    for label in runs:
        r = results[label]
        print(f"{label:<18} {r['return_pct']:>8.2f}% {r['pf']:>7.2f} {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>8.2f}% {r['n_trades']:>7} {r['expectancy']:>8.2f} "
              f"{r['n_pos_semesters']:>3}/{r['n_semesters']}")

    # PnL par semestre
    print("\n" + "=" * 120)
    print("PnL par semestre ($) — RANK_TOP20 / EV_TOP20_EVSORT")
    print("=" * 120)
    sems = sorted(set().union(*[results[l]["semesters"].index for l in ("RANK_TOP20", "EV_TOP20_EVSORT", "EV_TOP20_hybrid")]))
    print(f"{'semester':<10} {'RANK20':>14} {'EV20_hyb':>14} {'EV20_EVSORT':>14}")
    for s in sems:
        row = f"{s:<10}"
        for l in ("RANK_TOP20", "EV_TOP20_hybrid", "EV_TOP20_EVSORT"):
            if s in results[l]["semesters"].index:
                row += f"{results[l]['semesters'].loc[s,'pnl']:>13.0f}$"
            else:
                row += f"{'—':>14}"
        print(row)

    # Classification EV_ONLY : hybride vs EVSORT
    print("\n" + "=" * 120)
    print("Classification des trades exécutés (COMMON / EV_ONLY / RANK_ONLY)")
    print("=" * 120)
    all_cl = pd.concat([
        classify_evonly(results["EV_TOP20_hybrid"]["closed"], pool, "EV20_hybrid"),
        classify_evonly(results["EV_TOP20_EVSORT"]["closed"], pool, "EV20_EVSORT"),
    ], ignore_index=True)
    print(f"  {'bench':<12} {'group':<10} {'n':>5} {'PnL$':>9} {'PF':>6} {'expect$':>8} {'win%':>6}")
    for b in ("EV20_hybrid", "EV20_EVSORT"):
        for g, sub in all_cl[all_cl["bench"] == b].groupby("group"):
            pnl = pd.to_numeric(sub["pnl"], errors="coerce").fillna(0.0)
            gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
            print(f"  {b:<12} {g:<10} {len(pnl):>5} {pnl.sum():>9.0f} "
                  f"{(gp/gn if gn>0 else float('inf')):>6.2f} {pnl.mean():>8.2f} {(pnl>0).mean()*100:>5.1f}%")

    # Focus EV_ONLY par semestre (EVSORT)
    print("\n" + "=" * 120)
    print("EV_ONLY exécutés par semestre (EV_TOP20_EVSORT) — le test décisif")
    print("=" * 120)
    evs = all_cl[(all_cl["bench"] == "EV20_EVSORT") & (all_cl["group"] == "EV_ONLY")].copy()
    if not evs.empty:
        evs["entry_date"] = pd.to_datetime(evs["entry_date"]).dt.normalize()
        evs["semester"] = evs["entry_date"].dt.year.astype(str) + np.where(evs["entry_date"].dt.month <= 6, "H1", "H2")
        sem = evs.groupby("semester").agg(n=("pnl", "size"), pnl=("pnl", "sum"))
        print(f"  {'semester':<10} {'n':>5} {'PnL$':>9}")
        for s, r in sem.iterrows():
            print(f"  {s:<10} {r['n']:>5} {r['pnl']:>9.0f}")
        tot = evs["pnl"].sum()
        print(f"  TOTAL     {len(evs):>5} {tot:>9.0f}")
    else:
        print("  (aucun EV_ONLY exécuté dans EV_TOP20_EVSORT)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    all_cl.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
