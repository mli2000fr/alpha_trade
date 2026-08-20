"""E11 — Extreme LONG Payoff & Selection Diagnostic (ZÉRO optimisation).

CONTEXTE (spec user 2026-08-20) : E10 a gelé Oracle O0 + Extreme TOP20 comme univers
LONG validé (statistiquement) mais la variance m8 est énorme (P10 36% → P90 193%) et
2026H1 est mauvais (30% seeds positifs, −11.4k) indépendamment de Y3/EV/seed.

DEUX OBJECTIFS DIAGNOSTIQUES (pas de tuning) :

A. EXPLIQUER 2026H1 (payoff/lifecycle) :
   - Analyser les trades perdants (trailing_stop, initial_stop) d'un run EXTREME_TOP20
     représentatif : MFE avant sortie, MAE, retour après sortie J+3/J+5/J+10,
     vraies erreurs vs winners coupés avant maturation, fausses alertes Extreme.
   - Comparer GOOD semestres (2023-2025) vs 2026H1 pour voir si 2026H1 = plus de
     stop-outs avant excursion positive, plus de fausses alertes, changement MFE/MAE.

B. EXPLIQUER LA VARIANCE m8 (sélection) :
   - Concentration par cohorte : contribution des top 1/5/10 trades du run.
   - Equal-weight théorique du pool (moyenne des returns candidats, pas de m8) :
     s'il est stable alors que m8 est instable → le problème est capacity/selection.
   - Dispersion des returns individuels du pool par jour (std intra-jour) :
     si élevée, les candidats ne sont pas interchangeables ; si faible, la sélection
     importe peu et m8 dépend surtout du timing.
   - Nombre de candidats « interchangeables » par jour (returns dans ±0.5×std).

SHORT : hors périmètre (chantier séparé). AUCUN nouveau TP/SL, aucun nouveau sélecteur.

Sortie : print + artifacts/models/oracle/e11_results.parquet
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

PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")
CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e11_results.parquet")
INITIAL_EQUITY = 100_000.0
SEED = 7  # run représentatif EXTREME_TOP20
GOOD_SEMS = ("2023H1", "2023H2", "2024H1", "2024H2", "2025H1", "2025H2")
BAD_SEM = "2026H1"


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


def run_bt(sig: pd.DataFrame, pivots: dict) -> tuple[pd.DataFrame, pd.Series]:
    res = make_engine().run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    eq = res.equity_curve
    closed = res.closed_trades_df.copy()
    closed["signal_date"] = pd.to_datetime(closed["signal_date"]).dt.normalize()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"]).dt.normalize()
    closed["exit_date"] = pd.to_datetime(closed["exit_date"]).dt.normalize()
    closed["symbol"] = closed["symbol"].astype(str)
    closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
    closed["semester"] = closed["entry_date"].dt.year.astype(str) + \
        np.where(closed["entry_date"].dt.month <= 6, "H1", "H2")
    return closed, eq


def attach_path_metrics(closed: pd.DataFrame) -> pd.DataFrame:
    """Joint MFE/MAE/return du chemin simulé (labels) sur (symbol, signal_date)."""
    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    path["symbol"] = path["symbol"].astype(str)
    return closed.merge(path[["symbol", "date", "y3_long_mfe", "y3_long_mae", "y3_long_ret"]],
                        left_on=["symbol", "signal_date"], right_on=["symbol", "date"], how="left")


def post_exit_returns(closed: pd.DataFrame) -> pd.DataFrame:
    """Retour après sortie J+3/J+5/J+10 (close to close, depuis le cache OHLC)."""
    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "close"])
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    # Matrice close pivotée pour recherche rapide
    px = bars.pivot_table(index="trade_date", columns="symbol", values="close").sort_index()
    idx = px.index
    out = []
    for _, r in closed.iterrows():
        sym = r["symbol"]
        if sym not in px.columns:
            continue
        col = px[sym].dropna()
        pos = col.index.searchsorted(r["exit_date"], side="left")
        if pos >= len(col.index) or col.index[pos] != r["exit_date"]:
            if pos == 0:
                continue
            pos -= 1  # jour <= exit
        base = float(col.iloc[pos])
        if base <= 0:
            continue
        row = {"symbol": sym, "exit_date": r["exit_date"], "semester": r["semester"],
               "exit_reason": r["exit_reason"], "pnl": r["pnl"]}
        for k in (3, 5, 10):
            j = pos + k
            if j < len(col.index):
                row[f"ret_J{k}"] = float(col.iloc[j] / base - 1.0)
            else:
                row[f"ret_J{k}"] = float("nan")
        out.append(row)
    return pd.DataFrame(out)


def payoff_diagnostic(closed: pd.DataFrame, post: pd.DataFrame) -> None:
    """A. Décompose les perdants par reason, MFE/MAE, retour post-sortie, GOOD vs 2026H1."""
    print("\n" + "=" * 130)
    print("A. PAYOFF / LIFECYCLE — trades perdants par reason d'exit (EXTREME_TOP20, seed %d)" % SEED)
    print("=" * 130)
    c = attach_path_metrics(closed)
    c["mfe"] = pd.to_numeric(c["y3_long_mfe"], errors="coerce")
    c["mae"] = pd.to_numeric(c["y3_long_mae"], errors="coerce")
    c["holding"] = (c["exit_date"] - c["entry_date"]).dt.days

    print(f"\n  Par reason d'exit (tout le run) :")
    print(f"  {'reason':<16} {'n':>4} {'PnL$':>9} {'win%':>6} {'medMFE%':>8} {'medMAE%':>8} {'medDurJ':>7}")
    for reason, g in c.groupby("exit_reason"):
        print(f"  {reason:<16} {len(g):>4} {g['pnl'].sum():>9.0f} {100*(g['pnl']>0).mean():>5.0f}% "
              f"{100*g['mfe'].median():>7.2f}% {100*g['mae'].median():>7.2f}% {g['holding'].median():>7.1f}")

    # GOod vs bad semesters pour les perdants
    print(f"\n  GOOD semesters vs 2026H1 (perdants trailing_stop + initial_stop) :")
    print(f"  {'groupe':<10} {'n':>4} {'PnL$':>9} {'medMFE%':>8} {'medMAE%':>8} {'MAE/MFE':>8}")
    losers = c[c["exit_reason"].isin(["trailing_stop", "initial_stop"])].copy()
    for label, mask in [("GOOD", losers["semester"].isin(GOOD_SEMS)), ("2026H1", losers["semester"] == BAD_SEM)]:
        g = losers[mask]
        if g.empty:
            continue
        ratio = abs(g["mae"].median() / g["mfe"].median()) if g["mfe"].median() else float("nan")
        print(f"  {label:<10} {len(g):>4} {g['pnl'].sum():>9.0f} {100*g['mfe'].median():>7.2f}% "
              f"{100*g['mae'].median():>7.2f}% {ratio:>8.2f}")

    # Winners coupés avant maturation : MFE élevé mais sortie perdante
    print(f"\n  Winners coupés avant maturation (MFE >= +8% mais PnL < 0, par reason) :")
    wc = c[(c["mfe"] >= 0.08) & (c["pnl"] < 0)]
    if not wc.empty:
        print(f"  {'reason':<16} {'n':>4} {'PnL$':>9} {'medMFE%':>8} {'medMAE%':>8}")
        for reason, g in wc.groupby("exit_reason"):
            print(f"  {reason:<16} {len(g):>4} {g['pnl'].sum():>9.0f} {100*g['mfe'].median():>7.2f}% {100*g['mae'].median():>7.2f}%")
    else:
        print("  (aucun)")

    # Retour post-sortie (J+3/5/10) par reason — la sortie a-t-elle eu raison ?
    print(f"\n  Retour après sortie (close-to-close J+3/5/10) par reason :")
    print(f"  {'reason':<16} {'n':>4} {'J+3%':>8} {'J+5%':>8} {'J+10%':>9} {'%J+10>0':>8}")
    for reason, g in post.groupby("exit_reason"):
        print(f"  {reason:<16} {len(g):>4} {100*g['ret_J3'].median():>7.2f}% {100*g['ret_J5'].median():>7.2f}% "
              f"{100*g['ret_J10'].median():>8.2f}% {100*(g['ret_J10']>0).mean():>7.0f}%")

    # Fausses alertes : MFE < seuil (jamais de vrai mouvement) par semestre
    print(f"\n  Fausses alertes Extreme (MFE < +2%) par semestre :")
    fa = c[c["mfe"] < 0.02]
    for sem in sorted(c["semester"].unique()):
        g = fa[fa["semester"] == sem]
        tot = c[c["semester"] == sem]
        print(f"  {sem:<8} fausses_alertes={len(g):>4} ({100*len(g)/max(len(tot),1):>4.0f}% des trades) "
              f"PnL_fa={g['pnl'].sum():>8.0f}")


def selection_diagnostic(pool: pd.DataFrame, closed: pd.DataFrame, eq: pd.Series) -> None:
    """B. Variance m8 : equal-weight pool vs m8, concentration, dispersion intra-jour."""
    print("\n" + "=" * 130)
    print("B. SÉLECTION / VARIANCE m8")
    print("=" * 130)

    # B1. Equal-weight théorique du pool (moyenne des returns candidats, ret − coûts)
    df = pool.copy()
    df["_pe_pct"] = df.groupby("date")["proba_extreme"].rank(pct=True)
    pool20 = df[(df["_pe_pct"] >= 0.80)].copy()
    pool20["_net"] = pool20["y3_long_ret"] - 0.0016
    ew_expect = float(pool20["_net"].mean())
    ew_by_date = pool20.groupby("date")["_net"].mean()
    print(f"  B1. Equal-weight POOL TOP20 (théorique, pas de m8) :")
    print(f"      expectancy moyenne/trade = {100*ew_expect:.3f}% | par jour : mean={100*ew_by_date.mean():.3f}% "
          f"std={100*ew_by_date.std():.3f}% | jours positifs={(ew_by_date>0).mean()*100:.0f}%")
    m8_expect = float(closed["pnl"].mean())
    print(f"      m8 (seed {SEED}) expectancy/trade = {m8_expect:.2f}$ | n={len(closed)}")

    # B2. Concentration par cohorte (top 1/5/10 trades du run m8)
    pnl = closed["pnl"].sort_values(ascending=False)
    total = float(pnl.sum())
    print(f"  B2. Concentration m8 (run seed {SEED}) :")
    for k in (1, 5, 10, 20):
        print(f"      Top{k} trades : {pnl.head(k).sum():>9.0f}$ ({100*pnl.head(k).sum()/total:>4.0f}% du PnL)")

    # B3. Dispersion intra-jour des returns du pool (std par jour)
    disp = pool20.groupby("date")["_net"].std()
    print(f"  B3. Dispersion intra-jour du pool (std des returns candidats/jour) :")
    print(f"      std moyen={100*disp.mean():.3f}% | médian={100*disp.median():.3f}% | "
          f"jours nb candidats moyen={pool20.groupby('date').size().mean():.0f}")

    # B4. Candidats « interchangeables » : part du pool dans ±0.5×std intra-jour autour de la médiane
    def _interchangeable(g):
        s = g["_net"]
        med = s.median()
        half = 0.5 * s.std() if s.std() > 0 else 0.0
        return float(((s >= med - half) & (s <= med + half)).mean())
    inter = pool20.groupby("date").apply(_interchangeable, include_groups=False)
    print(f"  B4. Candidats interchangeables par jour (dans ±0.5×std de la médiane) :")
    print(f"      part moyenne={100*inter.mean():.0f}% | médiane={100*inter.median():.0f}%")

    # B5. Equity m8 vs proxy equal-weight cumulé (comparaison de stabilité)
    daily_ew = pool20.groupby("date")["_net"].sum().sort_index().cumsum()
    print(f"  B5. Stabilité : le pool equal-weight est-il stable alors que m8 est instable ?")
    print(f"      maxDD proxy equal-weight cumulé = {100*((daily_ew-daily_ew.cummax()).min()):.1f} pts "
          f"(ret cumulé, échelle trade-unit) | m8 MaxDD réel = {100*((eq/eq.cummax()-1).min()):.1f}%")


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")

    print(f"\n=== E11 — EXTREME LONG PAYOFF & SELECTION DIAGNOSTIC (run EXTREME_TOP20 seed {SEED}) ===", flush=True)
    closed, eq = run_bt(build_signals(pool, 0.80, 1.01, SEED), pivots)
    print(f"run: {len(closed)} trades | PnL={closed['pnl'].sum():.0f}$ | "
          f"sem+={(closed.groupby('semester')['pnl'].sum()>0).sum()}/{closed['semester'].nunique()}")

    post = post_exit_returns(closed)
    payoff_diagnostic(closed, post)
    selection_diagnostic(pool, closed, eq)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    attach_path_metrics(closed).merge(post, on=["symbol", "exit_date", "semester", "exit_reason", "pnl"], how="left") \
        .to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
