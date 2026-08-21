"""E12-A0b — Recheck diagnostique E11 sous CONTRAT PROD (zero optimisation).

SPEC user 2026-08-20 : verrouillage E12 = basculer sur le contrat PROD canonique
(B25_POST_TP_FIX_P14_M8). E12-A0b = recheck diagnostique PUR de E11 sous PROD,
avant tout sweep. Meme Oracle O0 / meme Extreme TOP20 pool / meme m8, mais
lifecycle exact PROD :
  - initial stop 2.5xATR            (--atr-risk-stop-multiple 2.5)
  - TP min(3xATR, 7%)               (--tp-atr-multiple 3.0 --tp-max-pct 0.07)
  - trailing risk-based 2.5xATR     (trailing_stop_long_pct=None -> derive du stop)
  - time_stop DESACTIVE             (prod : 0 fills)
  - gap filter 3%                   (max_entry_gap_pct=0.03)
  - intrabar conservative / next_open / costs 16bps RT / m8

DIAGNOSTICS recalcules (identiques a E11) :
  - PnL par exit reason ; MFE/MAE (recalcules depuis OHLC sur le chemin PROD) ;
  - MFE avant stop ; post-exit J+3/5/10 ; 2026H1 vs autres semestres ;
  - vraie erreur (MFE<3% & perte) vs premature stop (MFE>5/7% & perte) ;
  - distribution 20 seeds (PnL, 2026H1).
  Comparaison explicite E-LIFECYCLE (lu depuis e11_results.parquet) vs PROD.

Sortie : print + artifacts/models/oracle/e12_a0b_prod_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.microstructure import MicrostructureConfig
from backtesting.simulator import BacktestConfig, BacktestEngine
from scripts.e11_extreme_long_payoff_diag import (
    BAD_SEM,
    END,
    GOOD_SEMS,
    INITIAL_EQUITY,
    SEED_REP,
    START,
    build_signals,
    load_pivots,
    load_pool,
    post_exit_info,
)

CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e12_a0b_prod_results.parquet")
E11_PARQUET = Path("artifacts/models/oracle/e11_results.parquet")
N_SEEDS = 20
REASONS = ("take_profit", "trailing_stop", "initial_stop", "time_stop", "end_of_data")


def make_prod_engine() -> BacktestEngine:
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(), end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY, max_positions=8,
        atr_risk_stop_multiple=2.5,          # PROD
        tp_atr_multiple=3.0, tp_max_pct=0.07,  # PROD
        trailing_stop_long_pct=None,         # PROD : risk-based 2.5xATR
        trailing_stop_short_pct=None,
        use_canonical_costs=True, entry_limit_offset_pct=0.0,
        min_score_threshold=0.0, use_live_protection_logic=True,
        time_stop_enabled=False,             # PROD : neutralise (0 fills)
        microstructure=MicrostructureConfig(max_entry_gap_pct=0.03, intrabar_priority="conservative"),
    )
    return BacktestEngine(cfg)


def run_bt_prod(pool: pd.DataFrame, pivots: dict, seed: int) -> tuple[pd.DataFrame, pd.Series]:
    sig = build_signals(pool, 0.80, 1.01, seed)
    res = make_prod_engine().run(
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
    closed["return_pct"] = pd.to_numeric(closed["return_pct"], errors="coerce").fillna(0.0)
    closed["semester"] = closed["entry_date"].dt.year.astype(str) + \
        np.where(closed["entry_date"].dt.month <= 6, "H1", "H2")
    closed["holding"] = (closed["exit_date"] - closed["entry_date"]).dt.days
    return closed, eq


def mfe_mae_from_ohlc(closed: pd.DataFrame, px_high: pd.DataFrame, px_low: pd.DataFrame) -> pd.DataFrame:
    """MFE/MAE recalcules depuis OHLC sur le chemin reel (entry..exit) du moteur PROD."""
    rows: list[dict] = []
    for sym, g in closed.groupby("symbol"):
        if sym not in px_high.columns:
            continue
        hh = px_high[sym].dropna()
        ll = px_low[sym].dropna()
        idx = hh.index
        for _, r in g.iterrows():
            ep = idx.searchsorted(r["entry_date"], side="left")
            xp = idx.searchsorted(r["exit_date"], side="left")
            if ep >= len(idx):
                continue
            if idx[ep] != r["entry_date"] and ep > 0:
                ep -= 1
            if xp >= len(idx):
                xp = len(idx) - 1
            if xp < ep:
                xp = ep
            entry_px = float(r["entry_price"])
            if entry_px <= 0:
                continue
            seg_h = hh.iloc[ep:xp + 1].dropna()
            seg_l = ll.iloc[ep:xp + 1].dropna()
            mfe = float(seg_h.max() / entry_px - 1.0) if len(seg_h) else float("nan")
            mae = float(seg_l.min() / entry_px - 1.0) if len(seg_l) else float("nan")
            rows.append({"symbol": sym, "entry_date": r["entry_date"], "exit_date": r["exit_date"],
                         "exit_reason": r["exit_reason"], "mfe": mfe, "mae": mae})
    return pd.DataFrame(rows)


def _pf(ser: pd.Series) -> float:
    gp = float(ser[ser > 0].sum())
    gn = float(-ser[ser < 0].sum())
    return gp / gn if gn > 0 else float("inf")


def diagnostics(closed: pd.DataFrame, tag: str) -> dict:
    """Tables identiques a E11-A/D. Retourne un dict de metriques cle pour la comparaison."""
    print("\n" + "=" * 118)
    print(f"DIAGNOSTICS {tag}  (seed {SEED_REP})")
    print("=" * 118)

    # A0 par semestre
    print("\n  Par semestre :")
    print(f"  {'sem':<8} {'n':>4} {'PnL$':>9} {'Exp$':>7} {'PF':>5} {'medMFE%':>8} {'medMAE%':>8} "
          f"{'MAE/MFE':>7} | {'TP%':>4} {'trail%':>6} {'stop%':>6}")
    sem_stats = {}
    for sem in sorted(closed["semester"].unique()):
        g = closed[closed["semester"] == sem]
        mf = g["mfe"].median(); ma = g["mae"].median()
        ratio = abs(ma / mf) if mf and not np.isnan(mf) else float("nan")
        sem_stats[sem] = {"n": len(g), "pnl": g["pnl"].sum(), "pf": _pf(g["pnl"]),
                          "mfe": mf, "mae": ma, "ratio": ratio}
        tp = 100 * (g["exit_reason"] == "take_profit").mean()
        tr = 100 * (g["exit_reason"] == "trailing_stop").mean()
        st = 100 * (g["exit_reason"] == "initial_stop").mean()
        print(f"  {sem:<8} {len(g):>4} {g['pnl'].sum():>9.0f} {g['pnl'].mean():>7.0f} {_pf(g['pnl']):>5.2f} "
              f"{100*mf:>7.2f}% {100*ma:>7.2f}% {ratio:>7.2f} | {tp:>3.0f}% {tr:>5.0f}% {st:>5.0f}%")

    # A2 qualite entrees par semestre
    print("\n  Qualite entrees (vraies erreurs MFE<3% vs premature MFE>5/7%, et perte) :")
    print(f"  {'sem':<8} {'err<3%':>6} {'PnL$':>9} | {'lf>5%':>6} {'PnL$':>9} | {'lf>7%':>6} {'PnL$':>9}")
    for sem in sorted(closed["semester"].unique()):
        g = closed[closed["semester"] == sem]
        err = g[(g["pnl"] < 0) & (g["mfe"] < 0.03)]
        lf5 = g[(g["pnl"] < 0) & (g["mfe"] >= 0.05)]
        lf7 = g[(g["pnl"] < 0) & (g["mfe"] >= 0.07)]
        print(f"  {sem:<8} {len(err):>6} {err['pnl'].sum():>9.0f} | {len(lf5):>6} {lf5['pnl'].sum():>9.0f} | "
              f"{len(lf7):>6} {lf7['pnl'].sum():>9.0f}")

    # A3 stops GOOD vs 2026H1 (MFE avant stop + post-exit + auraient atteint +k%)
    stops = closed[closed["exit_reason"].isin(["initial_stop", "trailing_stop"])]
    if len(stops):
        print("\n  Stops (initial+trailing) : MFE avant stop + post-exit + auraient atteint +k% :")
        print(f"  {'groupe':<9} {'n':>4} {'medMFE%':>8} | {'J+3%':>7} {'J+5%':>7} {'J+10%':>8} "
              f"{'%J10>0':>7} | {'+5%':>5} {'+7%':>5} {'+10%':>6} {'+13%':>6}")
        for label, mask in [("GOOD", stops["semester"].isin(GOOD_SEMS)),
                            ("2026H1", stops["semester"] == BAD_SEM),
                            ("TOUT", pd.Series(True, index=stops.index))]:
            g = stops[mask]
            if g.empty:
                continue
            print(f"  {label:<9} {len(g):>4} {100*g['mfe'].median():>7.2f}% | "
                  f"{100*g['ret_J3'].median():>6.2f}% {100*g['ret_J5'].median():>6.2f}% "
                  f"{100*g['ret_J10'].median():>7.2f}% {100*(g['ret_J10']>0).mean():>6.0f}% | "
                  f"{100*g['hit_5'].mean():>4.0f}% {100*g['hit_7'].mean():>4.0f}% "
                  f"{100*g['hit_10'].mean():>5.0f}% {100*g['hit_13'].mean():>5.0f}%")

    # D par reason
    print("\n  Par exit reason (PnL$, expectancy, MFE/MAE, post-exit) :")
    print(f"  {'reason':<16} {'n':>4} {'PnL$':>10} {'Exp$':>8} {'win%':>6} {'medMFE%':>8} "
          f"{'medMAE%':>8} {'J+3%':>7} {'J+5%':>7} {'J+10%':>8}")
    for reason in REASONS:
        g = closed[closed["exit_reason"] == reason]
        if g.empty:
            continue
        print(f"  {reason:<16} {len(g):>4} {g['pnl'].sum():>10.0f} {g['pnl'].mean():>8.0f} "
              f"{100*(g['pnl']>0).mean():>5.0f}% {100*g['mfe'].median():>7.2f}% "
              f"{100*g['mae'].median():>7.2f}% {100*g['ret_J3'].median():>6.2f}% "
              f"{100*g['ret_J5'].median():>6.2f}% {100*g['ret_J10'].median():>7.2f}%")

    # metriques cle pour comparaison
    s26 = closed[closed["semester"] == BAD_SEM]
    stops26 = s26[s26["exit_reason"].isin(["initial_stop", "trailing_stop"])]
    err26 = s26[(s26["pnl"] < 0) & (s26["mfe"] < 0.03)]
    return {
        "n": len(closed), "pnl": float(closed["pnl"].sum()),
        "pf": _pf(closed["pnl"]),
        "s26_pnl": float(s26["pnl"].sum()), "s26_pf": _pf(s26["pnl"]),
        "s26_mfe": float(s26["mfe"].median()), "s26_mae": float(s26["mae"].median()),
        "s26_stops_pnl": float(stops26["pnl"].sum()), "s26_err_pnl": float(err26["pnl"].sum()),
        "ratio_lifecycle_errors": (abs(float(stops26["pnl"].sum())) /
                                   abs(float(err26["pnl"].sum()))
                                   if abs(float(err26["pnl"].sum())) > 0 else float("nan")),
    }


def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)

    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close"])
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    px_close = bars.pivot_table(index="trade_date", columns="symbol", values="close").sort_index()
    px_high = bars.pivot_table(index="trade_date", columns="symbol", values="high").sort_index()
    px_low = bars.pivot_table(index="trade_date", columns="symbol", values="low").sort_index()

    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | "
          f"{len(symbols)} syms | CONTRAT PROD", flush=True)

    # 20 seeds PROD
    per_seed = []
    for seed in range(N_SEEDS):
        closed, eq = run_bt_prod(pool, pivots, seed)
        per_seed.append({"seed": seed, "closed": closed, "eq": eq})
        if seed % 5 == 0:
            print(f"  seed {seed} done | PnL={closed['pnl'].sum():.0f}$", flush=True)

    # Seed representative : MFE/MAE + post-exit
    c7 = per_seed[SEED_REP]["closed"].copy()
    mma = mfe_mae_from_ohlc(c7, px_high, px_low)
    c7 = c7.merge(mma, on=["symbol", "entry_date", "exit_date", "exit_reason"], how="left")
    post = post_exit_info(c7, px_close, px_high)
    c7 = c7.merge(post[["symbol", "exit_date", "exit_reason", "ret_J3", "ret_J5", "ret_J10",
                        "hit_5", "hit_7", "hit_10", "hit_13"]],
                  on=["symbol", "exit_date", "exit_reason"], how="left")
    c7["semester"] = c7["entry_date"].dt.year.astype(str) + \
        np.where(c7["entry_date"].dt.month <= 6, "H1", "H2")

    print(f"\nrun PROD seed {SEED_REP}: {len(c7)} trades | PnL={c7['pnl'].sum():.0f}$ | "
          f"sem+={(c7.groupby('semester')['pnl'].sum()>0).sum()}/{c7['semester'].nunique()}", flush=True)

    d_prod = diagnostics(c7, "E12-A0b  PROD (B25_POST_TP_FIX_P14_M8)")

    # Distribution 20 seeds
    print("\n" + "=" * 118)
    print("DISTRIBUTION 20 SEEDS PROD (EXTREME_TOP20, m8)")
    print("=" * 118)
    recs = []
    for p in per_seed:
        cl = p["closed"]
        s26 = cl[cl["semester"] == BAD_SEM]["pnl"].sum()
        recs.append({"seed": p["seed"], "pnl": cl["pnl"].sum(),
                     "ret": (float(p["eq"].iloc[-1]) / INITIAL_EQUITY - 1) * 100,
                     "s26": float(s26)})
    rdf = pd.DataFrame(recs)
    print(f"  {'seed':>4} {'PnL$':>9} {'Ret%':>7} {'s26$':>9}")
    for _, r in rdf.iterrows():
        print(f"  {int(r['seed']):>4} {r['pnl']:>9.0f} {r['ret']:>7.1f} {r['s26']:>9.0f}")
    print(f"  median PnL={rdf['pnl'].median():.0f}$ | median Ret={rdf['ret'].median():.1f}% | "
          f"P10={rdf['ret'].quantile(0.10):.0f}% P90={rdf['ret'].quantile(0.90):.0f}%")
    print(f"  seeds 2026H1 positifs = {100*(rdf['s26']>0).mean():.0f}%")

    # Comparaison E-LIFECYCLE vs PROD
    print("\n" + "=" * 118)
    print("COMPARAISON E-LIFECYCLE (E11) vs PROD (E12-A0b) — seed 7")
    print("=" * 118)
    if E11_PARQUET.exists():
        e11 = pd.read_parquet(E11_PARQUET)
        e11["semester"] = pd.to_datetime(e11["entry_date"]).dt.year.astype(str) + \
            np.where(pd.to_datetime(e11["entry_date"]).dt.month <= 6, "H1", "H2")
        s26 = e11[e11["semester"] == BAD_SEM]
        stops26 = s26[s26["exit_reason"].isin(["initial_stop", "trailing_stop"])]
        err26 = s26[(s26["pnl"] < 0) & (s26["mfe"] < 0.03)]
        d_el = {"n": len(e11), "pnl": float(e11["pnl"].sum()), "pf": _pf(e11["pnl"]),
                "s26_pnl": float(s26["pnl"].sum()), "s26_pf": _pf(s26["pnl"]),
                "s26_mfe": float(s26["mfe"].median()), "s26_mae": float(s26["mae"].median()),
                "s26_stops_pnl": float(stops26["pnl"].sum()),
                "s26_err_pnl": float(err26["pnl"].sum()),
                "ratio_lifecycle_errors": (abs(float(stops26["pnl"].sum())) /
                                           abs(float(err26["pnl"].sum()))
                                           if abs(float(err26["pnl"].sum())) > 0 else float("nan"))}
    else:
        d_el = None

    rows = [
        ("PnL total seed 7 ($)", "pnl"), ("PF seed 7", "pf"),
        ("2026H1 PnL ($)", "s26_pnl"), ("2026H1 PF", "s26_pf"),
        ("2026H1 medMFE (%)", "s26_mfe"), ("2026H1 medMAE (%)", "s26_mae"),
        ("2026H1 stops PnL ($)", "s26_stops_pnl"), ("2026H1 vraies erreurs PnL ($)", "s26_err_pnl"),
        ("ratio lifecycle/erreurs", "ratio_lifecycle_errors"),
    ]
    print(f"  {'metrique':<30} {'E-LIFECYCLE':>14} {'PROD':>14}")
    for label, key in rows:
        el = d_el[key] if d_el else float("nan")
        pr = d_prod[key]
        if key in ("s26_mfe", "s26_mae", "ratio_lifecycle_errors"):
            el_s = f"{100*el:.1f}%" if isinstance(el, (int, float)) and not np.isnan(el) else "n/a"
            pr_s = f"{100*pr:.1f}%" if isinstance(pr, (int, float)) and not np.isnan(pr) else "n/a"
        else:
            el_s = f"{el:,.0f}" if isinstance(el, (int, float)) and not np.isnan(el) else "n/a"
            pr_s = f"{pr:,.0f}" if isinstance(pr, (int, float)) and not np.isnan(pr) else "n/a"
        print(f"  {label:<30} {el_s:>14} {pr_s:>14}")

    print("\n  QUESTIONS (pre-fixees) :")
    if d_el:
        print(f"  - 2026H1 MAE profonde ? E-LIFECYCLE medMAE={100*d_el['s26_mae']:.1f}% vs "
              f"PROD medMAE={100*d_prod['s26_mae']:.1f}%")
        print(f"  - stops prematures ? E-LIFECYCLE stops 2026H1={d_el['s26_stops_pnl']:.0f}$ vs "
              f"PROD stops 2026H1={d_prod['s26_stops_pnl']:.0f}$")
        print(f"  - ratio lifecycle/erreurs : E-LIFECYCLE={d_el['ratio_lifecycle_errors']:.2f} vs "
              f"PROD={d_prod['ratio_lifecycle_errors']:.2f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    c7.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
