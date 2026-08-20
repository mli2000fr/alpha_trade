"""E7 — Validation économique finale de l'architecture gelée (branche LONG E6).

STATUT : E6 = CLOSED / TOP20 = champion research LONG. On ne touche plus à Y3
(pas de TOP15/25, pas de nouveau CatBoost, pas de nouveau seuil).

ARCHITECTURE GELÉE (à valider) :
  Oracle O0 → Extreme detection → pool top 10% Extreme → CatBoost Y3-LONG
  → ranking OOF → conserver TOP20 Y3 → moteur m8 LONG

QUESTION E7 : « Si je l'intègre réellement à α-Trade, Y3 apporte-t-il quelque
chose qu'un filtre beaucoup plus simple n'apporterait pas ? »

MÉTHODE : comparer le portefeuille AVEC vs SANS Y3, en gardant EXACTEMENT le même
Oracle O0, lifecycle, m8, coûts, sizing et périodes :
  - NO_Y3_ALL     : pool Extreme entier, ordre par proba_extreme (Oracle seul)
  - NO_Y3_TOP20   : top 20% du pool par proba_extreme (Oracle seul)
  - WITH_Y3_TOP20 : top 20% du pool par score Y3-LONG (politique gelée)
Le moteur est identique (m8, stop 3.5×ATR, TP min(4×ATR,13%), trailing long 7%,
coûts canoniques 16 bps, marché).

MÉTRIQUES : Return, PF, Sharpe, MaxDD, expectancy, N trades, turnover, par semestre,
positions refusées/acceptées (diagnostics), contribution des trades exclus par Y3
(niveau candidat), et focus 2025H2/2026H1.

DIAGNOSTIC 2026H1 (le point critique) : AUC Y3 > 0.5 mais P&L négatif →
décomposer par raison d'exit (TP / stop / trailing / time) pour voir si le problème
restant est la sélection ou l'ASYMMÉTRIE payoff/exit/régime.

Sortie : print + artifacts/models/oracle/e7_results.parquet
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

OUT = Path("artifacts/models/oracle/e7_results.parquet")
INITIAL_EQUITY = 100_000.0
COST_RT = 0.0016

VARIANTS = ["NO_Y3_ALL", "NO_Y3_TOP20", "WITH_Y3_TOP20"]


def build_signals(pool: pd.DataFrame, variant: str) -> pd.DataFrame:
    df = pool.copy()
    if variant == "WITH_Y3_TOP20":
        df = df[df.groupby("date")["_proba_catboost"].rank(pct=True) >= 0.80]
        df["rank"] = df.groupby("date")["_proba_catboost"].rank(ascending=False)
        df["score"] = df["_proba_catboost"]
    else:
        if variant == "NO_Y3_TOP20":
            df = df[df.groupby("date")["proba_extreme"].rank(pct=True) >= 0.80]
        df["rank"] = df.groupby("date")["proba_extreme"].rank(ascending=False)
        df["score"] = df["proba_extreme"]
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = "buy"
    return sig


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
    notional = float((pd.to_numeric(closed.get("quantity", pd.Series(dtype=float)), errors="coerce").fillna(0) *
                      pd.to_numeric(closed.get("entry_price", pd.Series(dtype=float)), errors="coerce").fillna(0)).sum()) if n else 0.0
    avg_eq = float(eq.mean()) if len(eq) else INITIAL_EQUITY
    turnover = (notional / avg_eq) / max(len(eq) / 252.0, 0.01) if avg_eq > 0 else 0.0
    diag = res.diagnostics
    return {
        "bench": label, "return_pct": ret, "pf": pf, "sharpe": sharpe, "max_dd_pct": dd,
        "n_trades": n, "expectancy": float(pnl.mean()) if n else 0.0, "turnover": turnover,
        "closed": closed, "diag": diag.to_dict(),
    }


def semester_table(closed: pd.DataFrame, label: str) -> pd.DataFrame:
    c = closed.copy()
    c["entry_date"] = pd.to_datetime(c["entry_date"]).dt.normalize()
    c["semester"] = c["entry_date"].dt.year.astype(str) + np.where(c["entry_date"].dt.month <= 6, "H1", "H2")
    c["pnl"] = pd.to_numeric(c["pnl"], errors="coerce").fillna(0.0)
    g = c.groupby("semester").agg(n=("pnl", "size"), pnl=("pnl", "sum"))
    g["bench"] = label
    return g.reset_index()


def exit_reason_decomp(closed: pd.DataFrame, label: str, semester: str | None = None) -> pd.DataFrame:
    c = closed.copy()
    c["entry_date"] = pd.to_datetime(c["entry_date"]).dt.normalize()
    c["semester"] = c["entry_date"].dt.year.astype(str) + np.where(c["entry_date"].dt.month <= 6, "H1", "H2")
    c["pnl"] = pd.to_numeric(c["pnl"], errors="coerce").fillna(0.0)
    if semester:
        c = c[c["semester"] == semester]
    g = c.groupby("exit_reason").agg(n=("pnl", "size"), pnl=("pnl", "sum"),
                                     win=("pnl", lambda s: float((s > 0).mean())))
    g["bench"] = label
    return g.reset_index()


def y3_excluded_contribution(pool: pd.DataFrame) -> pd.DataFrame:
    """Contribution des trades exclus par Y3 (bottom 80% du pool par score Y3).

    Au niveau candidat (ret réalisé − coûts) : le pool Extreme entier vs la part
    que Y3 garde (TOP20) vs celle qu'il exclut (bottom 80%).
    """
    df = pool.copy()
    df["_net"] = df["y3_long_ret"] - COST_RT
    df["_in_top20"] = df.groupby("date")["_proba_catboost"].rank(pct=True) >= 0.80
    rows = []
    for name, mask in [("pool_entier", np.ones(len(df), dtype=bool)),
                       ("Y3_garde_TOP20", df["_in_top20"]),
                       ("Y3_exclut_bottom80", ~df["_in_top20"])]:
        sub = df[mask]
        ret = sub["_net"]
        gp = float(ret[ret > 0].sum()); gn = float(-ret[ret < 0].sum())
        rows.append({
            "groupe": name, "n": len(sub), "pnl": float(ret.sum()),
            "pf": gp / gn if gn > 0 else float("inf"),
            "expectancy": float(ret.mean()),
        })
    return pd.DataFrame(rows)


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy().dropna(subset=["y3_long"])
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")

    print("\n=== E7 — Portefeuille AVEC vs SANS Y3 (même Oracle O0 / lifecycle / m8 / coûts) ===", flush=True)
    results = {}
    for v in VARIANTS:
        print(f"=== {v} ===", flush=True)
        results[v] = run_bt(build_signals(pool, v), pivots, v)
        r = results[v]
        print(f"  Return={r['return_pct']:.2f}% PF={r['pf']:.2f} Sharpe={r['sharpe']:.2f} "
              f"MaxDD={r['max_dd_pct']:.2f}% trades={r['n_trades']} expect={r['expectancy']:.2f}$ "
              f"turnover={r['turnover']:.1f}x", flush=True)

    print("\n" + "=" * 120)
    print("Table comparée (architecture gelée : WITH_Y3_TOP20 vs baselines sans Y3)")
    print("=" * 120)
    hdr = f"{'bench':<15} {'Return%':>9} {'PF':>7} {'Sharpe':>7} {'MaxDD%':>9} {'trades':>7} {'expect$':>8} {'turnover':>9}"
    print(hdr); print("-" * 120)
    for v in VARIANTS:
        r = results[v]
        print(f"{v:<15} {r['return_pct']:>8.2f}% {r['pf']:>7.2f} {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>8.2f}% {r['n_trades']:>7} {r['expectancy']:>8.2f} {r['turnover']:>9.1f}")

    # Par semestre
    print("\n" + "=" * 120)
    print("PnL par semestre ($)")
    print("=" * 120)
    sems_all = pd.concat([semester_table(results[v]["closed"], v) for v in VARIANTS])
    piv_sem = sems_all.pivot_table(index="semester", columns="bench", values="pnl", aggfunc="sum", fill_value=0)
    print(piv_sem.to_string())

    # Diagnostics capacité (positions refusées/acceptées)
    print("\n" + "=" * 120)
    print("Diagnostics capacité (rejets) par variante")
    print("=" * 120)
    for v in VARIANTS:
        d = results[v]["diag"]
        rej = sum(d.get(k, 0) for k in ("blocked_by_concentration", "blocked_by_blacklist",
                                         "blocked_by_sectoral_cap", "blocked_by_gross_exposure",
                                         "blocked_cash_entries"))
        print(f"  {v:<15} trades={results[v]['n_trades']} rejets_capacité={rej}")

    # Contribution des trades exclus par Y3 (niveau candidat)
    print("\n" + "=" * 120)
    print("Contribution Y3 au niveau candidat (ret réalisé − coûts)")
    print("=" * 120)
    excl = y3_excluded_contribution(pool)
    for r in excl.itertuples():
        print(f"  {r.groupe:<20} n={r.n:>6} PnL={r.pnl:>9.0f} PF={r.pf:>6.2f} expect={100*r.expectancy:>7.3f}%")

    # Focus 2025H2 / 2026H1 + décomposition par exit
    print("\n" + "=" * 120)
    print("FOCUS récent : 2025H2 / 2026H1 — décomposition par raison d'exit (WITH_Y3_TOP20)")
    print("=" * 120)
    for sem in ("2025H2", "2026H1"):
        dec = exit_reason_decomp(results["WITH_Y3_TOP20"]["closed"], "WITH_Y3_TOP20", semester=sem)
        print(f"\n  {sem}:")
        for r in dec.itertuples():
            print(f"    {r.exit_reason:<16} n={r.n:>4} PnL={r.pnl:>9.0f} win={100*r.win:>5.1f}%")
    # Décomposition complète pour contexte
    print("\n  (contexte — tout semestre confondu)")
    for r in exit_reason_decomp(results["WITH_Y3_TOP20"]["closed"], "WITH_Y3_TOP20").itertuples():
        print(f"    {r.exit_reason:<16} n={r.n:>4} PnL={r.pnl:>9.0f} win={100*r.win:>5.1f}%")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    sems_all.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
