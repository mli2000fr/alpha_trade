"""E8 — Oracle Extreme Economic Ranking : le gradient de proba_extreme porte-t-il
de la tradabilité ? (sans tuning)

CONTEXTE (spec user 2026-08-20) : E7 montre que classer le pool Extreme par
`proba_extreme` (Oracle brut) = 149.90% vs Y3-TOP20 = 37.47%. MAIS il ne faut PAS
conclure « proba_extreme = score LONG ». Deux mécanismes possibles :
  A) proba_extreme porte un vrai gradient économique (↑ proba → ↑ PnL LONG)
  B) Y3 casse une sélection déjà excellente ; proba_extreme n'est pas directionnel,
     il conserve juste les gros movers (upside LONG des gagnants).

QUATRE QUESTIONS FIGÉES (aucun tuning, aucun TOP5/15 choisi après coup) :
  Q1. Le gradient de proba_extreme est-il économiquement MONOTONE dans le pool ?
      → découper le pool Extreme (top 10%) en quintiles fixes E1..E5 par rang de
        proba_extreme ; mesurer avec le vrai moteur LONG-only : expectancy, PF,
        PnL, win, MFE, MAE, semestres positifs. Attendu : ↑proba → ↑MFE/↑expectancy/↑PF.
  Q2. Oracle-sort bat-il RANDOM-sort dans exactement le même pool / m8 ?
      → sépare « valeur du gate Extreme » de « valeur du classement interne ».
      Si pool+random ≈ pool+Oracle → le gate fait tout ; si Oracle >> random →
      le ranking interne a une vraie valeur.
  Q3. L'avantage est-il stable H1/H2 et rolling 12/18 mois ? (Oracle-sort gelé)
  Q4. Phénomène LONG spécifique ou vrai signal d'AMPLITUDE (observable SHORT aussi) ?
      → LONG vs SHORT sur le même ranking Oracle. Si les deux bénéficient du score
      mais avec sorties différentes → amplitude. Si seul LONG gagne → asymétrie
      population/moteur.

INTERPRÉTATION STRICTE : ne pas dire « proba_extreme = score LONG » mais
  « proba_extreme = score de magnitude dont la valeur économique LONG semble très
  forte dans E7 ».

Sortie : print + artifacts/models/oracle/e8_results.parquet
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
from scripts.e6_b3_rolling_stability import WINDOWS_12M, WINDOWS_18M

PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")
OUT = Path("artifacts/models/oracle/e8_results.parquet")
INITIAL_EQUITY = 100_000.0
COST_RT = 0.0016

# Quintiles du pool Extreme (par rang proba_extreme intra-date)
QUINTILES = [("E1_top0-20", 0.80, 1.01), ("E2_20-40", 0.60, 0.80),
             ("E3_40-60", 0.40, 0.60), ("E4_60-80", 0.20, 0.40),
             ("E5_bottom80-100", 0.00, 0.20)]


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


def build_signals(pool: pd.DataFrame, *, lo: float = 0.0, hi: float = 1.01,
                  sort: str = "oracle", side: str = "buy", seed: int = 42) -> pd.DataFrame:
    """Candidats du pool Extreme, quintile [lo,hi) de proba_extreme, tri oracle/random.

    sort='oracle' : rank par proba_extreme (desc). sort='random' : rank aléatoire seedé.
    side : 'buy' (LONG) ou 'sell' (SHORT).
    """
    df = pool.copy()
    df["_pe_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    df = df[(df["_pe_pct"] >= lo) & (df["_pe_pct"] < hi)]
    if sort == "oracle":
        df["rank"] = df.groupby("date")["proba_extreme"].rank(ascending=False)
    elif sort == "random":
        rng = np.random.default_rng(seed)
        df["_rand"] = rng.random(len(df))
        df["rank"] = df.groupby("date")["_rand"].rank(ascending=False)
    else:
        raise ValueError(sort)
    df["score"] = df["proba_extreme"]
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = side
    return sig


def run_bt(sig: pd.DataFrame, pivots: dict, label: str, side: str = "buy") -> dict:
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
    closed["signal_date"] = pd.to_datetime(closed["signal_date"]).dt.normalize()
    closed["semester"] = closed["entry_date"].dt.year.astype(str) + \
        np.where(closed["entry_date"].dt.month <= 6, "H1", "H2")
    closed["pnl"] = pnl
    sem = closed.groupby("semester").agg(n=("pnl", "size"), pnl=("pnl", "sum"))
    n_sem = len(sem); n_pos = int((sem["pnl"] > 0).sum()) if n_sem else 0
    return {
        "bench": label, "return_pct": ret, "pf": pf, "sharpe": sharpe, "max_dd_pct": dd,
        "n_trades": n, "expectancy": float(pnl.mean()) if n else 0.0,
        "n_semesters": n_sem, "n_pos_semesters": n_pos, "semesters": sem, "closed": closed,
    }


def attach_mfe_mae(trades: pd.DataFrame, side: str) -> pd.DataFrame:
    """Joint MFE/MAE depuis les labels de chemin (LONG ou SHORT)."""
    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    path["symbol"] = path["symbol"].astype(str)
    mfe_col = "y3_long_mfe" if side == "buy" else "y3_short_mfe"
    mae_col = "y3_long_mae" if side == "buy" else "y3_short_mae"
    return trades.merge(path[["symbol", "date", mfe_col, mae_col]],
                        left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")


def window_metrics(eq: pd.Series, trades: pd.DataFrame, w_start: pd.Timestamp, w_end: pd.Timestamp) -> dict:
    eq_w = eq.loc[(eq.index >= w_start) & (eq.index <= w_end)]
    ret = float(eq_w.iloc[-1] / eq_w.iloc[0] - 1.0) * 100.0 if len(eq_w) > 1 else 0.0
    rets = eq_w.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq_w / eq_w.cummax()) - 1.0).min() * 100.0) if len(eq_w) > 1 else 0.0
    t = trades[(trades["entry_date"] >= w_start) & (trades["entry_date"] <= w_end)]
    pnl = pd.to_numeric(t["pnl"], errors="coerce").fillna(0.0)
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    return {
        "window": f"{w_start.date()}→{w_end.date()}", "n": len(pnl),
        "return_pct": ret, "pf": gp / gn if gn > 0 else float("inf"),
        "sharpe": sharpe, "max_dd_pct": dd,
        "expectancy": float(pnl.mean()) if len(pnl) else 0.0,
    }


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy().dropna(subset=["y3_long"])
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool Extreme: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")

    # ═════ Q1 : monotonie du gradient proba_extreme (quintiles, LONG-only) ═════
    print("\n" + "=" * 130)
    print("Q1 — GRADIENT proba_extreme dans le pool Extreme (quintiles, LONG-only, m8)")
    print("=" * 130)
    print(f"  {'bucket':<20} {'n':>5} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'MaxDD%':>8} "
          f"{'expect$':>8} {'win%':>6} {'sem+':>5} {'MFE%':>7} {'MAE%':>7}")
    q1_results = {}
    for label, lo, hi in QUINTILES:
        sig = build_signals(pool, lo=lo, hi=hi, sort="oracle", side="buy")
        r = run_bt(sig, pivots, label, "buy")
        q1_results[label] = r
        tc = attach_mfe_mae(r["closed"], "buy")
        mfe = pd.to_numeric(tc["y3_long_mfe"], errors="coerce").dropna().mean()
        mae = pd.to_numeric(tc["y3_long_mae"], errors="coerce").dropna().mean()
        pnl = pd.to_numeric(r["closed"]["pnl"], errors="coerce").fillna(0.0)
        print(f"  {label:<20} {r['n_trades']:>5} {r['return_pct']:>8.1f} {r['pf']:>6.2f} {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>8.1f} {r['expectancy']:>8.2f} {(pnl>0).mean()*100:>6.1f} "
              f"{r['n_pos_semesters']:>3}/{r['n_semesters']} {100*mfe:>7.2f} {100*mae:>7.2f}", flush=True)
    # Monotonie ?
    exps = [q1_results[l]["expectancy"] for l, _, _ in QUINTILES]
    print(f"  expectancy par quintile (E1→E5) : {[f'{e:.0f}' for e in exps]}")
    mono = all(exps[i] > exps[i + 1] for i in range(len(exps) - 1))
    print(f"  monotonie décroissante E1>E2>E3>E4>E5 : {mono}")

    # ═════ Q2 : Oracle-sort vs RANDOM-sort (même pool, m8) ═════
    print("\n" + "=" * 130)
    print("Q2 — Oracle-sort vs RANDOM-sort dans le MÊME pool Extreme (m8, LONG-only)")
    print("=" * 130)
    sig_oracle = build_signals(pool, lo=0.0, hi=1.01, sort="oracle", side="buy")
    sig_random = build_signals(pool, lo=0.0, hi=1.01, sort="random", side="buy")
    r_oracle = run_bt(sig_oracle, pivots, "Oracle-sort", "buy")
    r_random = run_bt(sig_random, pivots, "Random-sort", "buy")
    print(f"  {'bench':<12} {'n':>5} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'MaxDD%':>8} {'expect$':>8}")
    for r in (r_random, r_oracle):
        print(f"  {r['bench']:<12} {r['n_trades']:>5} {r['return_pct']:>8.1f} {r['pf']:>6.2f} "
              f"{r['sharpe']:>7.2f} {r['max_dd_pct']:>8.1f} {r['expectancy']:>8.2f}")
    print(f"  → delta Oracle − Random : Return {r_oracle['return_pct']-r_random['return_pct']:+.1f} pts")

    # ═════ Q3 : stabilité H1/H2 + rolling 12/18m (Oracle-sort) ═════
    print("\n" + "=" * 130)
    print("Q3 — STABILITÉ Oracle-sort : par semestre + rolling 12/18m")
    print("=" * 130)
    print("  PnL par semestre (Oracle-sort) :")
    for s, row in r_oracle["semesters"].iterrows():
        print(f"    {s:<10} n={row['n']:>4} PnL={row['pnl']:>9.0f}")
    # rolling 12m (equity réelle du run Oracle-sort)
    res_oracle = make_engine().run(
        open_df=pivots["open"], close=pivots["close"], high=pivots["high"], low=pivots["low"],
        signals_df=sig_oracle, volume=pivots["volume"])
    eq_oracle = res_oracle.equity_curve
    rows12 = []
    for w_start, w_end in WINDOWS_12M:
        rows12.append(window_metrics(eq_oracle, r_oracle["closed"], w_start, w_end))
    for r in rows12:
        print(f"    {r['window']:<24} Ret={r['return_pct']:>7.1f}% PF={r['pf']:>5.2f} Sharpe={r['sharpe']:>5.2f} "
              f"MaxDD={r['max_dd_pct']:>6.1f}% expect={r['expectancy']:>7.2f} n={r['n']:>4}")

    # ═════ Q4 : LONG vs SHORT sur le même ranking Oracle ═════
    print("\n" + "=" * 130)
    print("Q4 — LONG vs SHORT sur le MÊME ranking Oracle (amplitude vs direction)")
    print("=" * 130)
    sig_short = build_signals(pool, lo=0.0, hi=1.01, sort="oracle", side="sell")
    r_short = run_bt(sig_short, pivots, "SHORT", "sell")
    print(f"  {'bench':<8} {'n':>5} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'MaxDD%':>8} {'expect$':>8} {'sem+':>6}")
    for r in (r_oracle, r_short):
        print(f"  {r['bench']:<8} {r['n_trades']:>5} {r['return_pct']:>8.1f} {r['pf']:>6.2f} "
              f"{r['sharpe']:>7.2f} {r['max_dd_pct']:>8.1f} {r['expectancy']:>8.2f} "
              f"{r['n_pos_semesters']:>3}/{r['n_semesters']}")
    # MFE/MAE SHORT
    tc_s = attach_mfe_mae(r_short["closed"], "sell")
    tc_l = attach_mfe_mae(r_oracle["closed"], "buy")
    mfe_s = pd.to_numeric(tc_s["y3_short_mfe"], errors="coerce").dropna().mean()
    mae_s = pd.to_numeric(tc_s["y3_short_mae"], errors="coerce").dropna().mean()
    mfe_l = pd.to_numeric(tc_l["y3_long_mfe"], errors="coerce").dropna().mean()
    mae_l = pd.to_numeric(tc_l["y3_long_mae"], errors="coerce").dropna().mean()
    print(f"  MFE/MAE : LONG {100*mfe_l:.2f}%/{100*mae_l:.2f}% | SHORT {100*mfe_s:.2f}%/{100*mae_s:.2f}%")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{k: v for k, v in r.items() if k != "semesters" and k != "closed"} for r in q1_results.values()]).to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
