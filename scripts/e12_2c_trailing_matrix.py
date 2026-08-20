"""E12-2C — Matrice TRAILING seul, sous contrat PROD, vrai moteur m8.

SPEC user 2026-08-20 : T0=2.5xATR (baseline), T1=3.0xATR, T2=3.5xATR, T3=4.0xATR.
Stop initial GELÉ à 2.5xATR (decouplage initial_stop_atr_multiple=2.5), TP min(3xATR,7%),
gap 3%, costs 16bps, m8, PAS de time_stop. Seul le trailing varie (atr_risk_stop_multiple=T
-> risk_per_share -> distance trailing ; sizing budget egal inchange, PAS de confound).

MESURES :
  - Return/PF/Sharpe/DD/PnL/N/duree moyenne par variant (seed 7) + par semestre.
  - ATTRIBUTION causale vs T0 (seed 7, join sur symbol x signal_date) :
      T0 trailing -> TP   : PREMATURE sauves (n, gain sum ret%, MFE/MAE du chemin T0)
      T0 trailing -> trailing plus profond : TRUE_LOSER aggraves (n, perte supp)
      NET = gain sauves - pertes aggravees ; delai supplementaire moyen avant sortie.
  - Robustesse 5 seeds (medians + %seeds qui battent T0).
  - GATES G1-G7 (idem E12-2B) ; alerte si le gain vient d'une explosion de DD/duree.

REG.RESSION : T0 (trail 2.5, init 2.5, decouplage) doit reproduire E12-A0b bit-for-bit.
Sortie : print + artifacts/models/oracle/e12_2c_trailing_matrix.parquet
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
    END,
    INITIAL_EQUITY,
    SEED_REP,
    START,
    build_signals,
    load_pivots,
    load_pool,
)

CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e12_2c_trailing_matrix.parquet")
VARIANTS = [("T0", 2.5), ("T1", 3.0), ("T2", 3.5), ("T3", 4.0)]
SEEDS = [0, 3, 7, 11, 19]


def make_engine(trail_mult: float) -> BacktestEngine:
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(), end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY, max_positions=8,
        atr_risk_stop_multiple=trail_mult,        # TRAILING = T xATR
        initial_stop_atr_multiple=2.5,            # stop initial GELÉ 2.5xATR
        tp_atr_multiple=3.0, tp_max_pct=0.07,
        trailing_stop_long_pct=None,
        trailing_stop_short_pct=None,
        use_canonical_costs=True, entry_limit_offset_pct=0.0,
        min_score_threshold=0.0, use_live_protection_logic=True,
        time_stop_enabled=False,
        microstructure=MicrostructureConfig(max_entry_gap_pct=0.03, intrabar_priority="conservative"),
    )
    return BacktestEngine(cfg)


def run_bt(pool: pd.DataFrame, pivots: dict, seed: int, trail_mult: float) -> tuple[pd.DataFrame, pd.Series]:
    sig = build_signals(pool, 0.80, 1.01, seed)
    res = make_engine(trail_mult).run(
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


def metrics(closed: pd.DataFrame, eq: pd.Series) -> dict:
    pnl = closed["pnl"]
    final = float(eq.iloc[-1]) if len(eq) else INITIAL_EQUITY
    ret = (final / INITIAL_EQUITY - 1.0) * 100.0
    rets = eq.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) > 1 else 0.0
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    pf = gp / gn if gn > 0 else float("inf")
    sem_pnl = closed.groupby("semester")["pnl"].sum()

    def _sem_pf(g: pd.DataFrame) -> float:
        s = g["pnl"]
        gn2 = -float(s[s < 0].sum())
        return float(s[s > 0].sum()) / gn2 if gn2 > 0 else float("inf")

    sem_pf = closed.groupby("semester", group_keys=False).apply(_sem_pf, include_groups=False)
    top5 = float(pnl.sort_values(ascending=False).head(5).sum()) / max(float(pnl.sum()), 1e-9)
    top10 = float(pnl.sort_values(ascending=False).head(10).sum()) / max(float(pnl.sum()), 1e-9)
    return {"ret": ret, "pf": pf, "sharpe": sharpe, "dd": dd, "pnl": float(pnl.sum()),
            "n": len(pnl), "sem_pnl": sem_pnl, "sem_pf": sem_pf, "top5": top5, "top10": top10,
            "dur": float(closed["holding"].mean())}


def mfe_mae_for(closed: pd.DataFrame, px_high: pd.DataFrame, px_low: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sym, g in closed.groupby("symbol"):
        if sym not in px_high.columns:
            continue
        hh = px_high[sym].dropna(); ll = px_low[sym].dropna(); idx = hh.index
        for _, r in g.iterrows():
            ep = idx.searchsorted(r["entry_date"], side="left")
            xp = idx.searchsorted(r["exit_date"], side="left")
            if ep >= len(idx) or xp >= len(idx):
                continue
            if idx[ep] != r["entry_date"] and ep > 0:
                ep -= 1
            if xp < ep:
                xp = ep
            entry_px = float(r["entry_price"])
            if entry_px <= 0:
                continue
            seg_h = hh.iloc[ep:xp + 1].dropna(); seg_l = ll.iloc[ep:xp + 1].dropna()
            rows.append({"symbol": sym, "entry_date": r["entry_date"], "exit_date": r["exit_date"],
                         "mfe": float(seg_h.max() / entry_px - 1.0) if len(seg_h) else float("nan"),
                         "mae": float(seg_l.min() / entry_px - 1.0) if len(seg_l) else float("nan")})
    return pd.DataFrame(rows)


def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {len(symbols)} syms | CONTRAT PROD | trailing seul", flush=True)

    # OHLC high/low pour MFE/MAE des trades sauves
    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "high", "low"])
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    bars["symbol"] = bars["symbol"].astype(str)
    bb = bars[bars["symbol"].isin(symbols)]
    px_high = bb.pivot_table(index="trade_date", columns="symbol", values="high").sort_index()
    px_low = bb.pivot_table(index="trade_date", columns="symbol", values="low").sort_index()

    # ── Regression : T0 (trail 2.5, init 2.5, decouplage) vs E12-A0b ──
    c0, _ = run_bt(pool, pivots, SEED_REP, 2.5)
    pnl0 = float(c0["pnl"].sum())
    ec = c0["exit_reason"].value_counts().to_dict()
    ok = abs(pnl0 - 72462.0) < 1.0 and ec.get("take_profit", 0) == 488 and \
        ec.get("trailing_stop", 0) == 182 and ec.get("initial_stop", 0) == 131 and \
        ec.get("time_stop", 0) == 0
    print(f"REGRESSION T0 (trail 2.5, init 2.5, decouplage) : PnL={pnl0:.0f}$ (attendu 72462) "
          f"| exits={ec} -> {'OK' if ok else 'ECHEC'}", flush=True)
    if not ok:
        print("STOP : regression non reproduite.")
        return

    results = []
    seed7 = {}
    for vname, mult in VARIANTS:
        for seed in SEEDS:
            closed, eq = run_bt(pool, pivots, seed, mult)
            m = metrics(closed, eq)
            results.append({"variant": vname, "trail_atr": mult, "seed": seed, **{k: m[k] for k in
                          ("ret", "pf", "sharpe", "dd", "pnl", "n", "top5", "top10", "dur")}})
            if seed == SEED_REP:
                seed7[vname] = (closed, eq)
        print(f"  {vname} (trailing {mult}xATR) done", flush=True)
    dfr = pd.DataFrame(results)

    # ── Table consolidee (seed 7) ──
    print("\n" + "=" * 130)
    print("E12-2C  Matrice trailing seul — seed 7 (vrai moteur m8, PROD)")
    print("=" * 130)
    print(f"  {'var':<5} {'trail':>6} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'DD%':>7} {'PnL$':>10} "
          f"{'N':>5} {'durJ':>6} {'Sem+':>5} {'TP':>4} {'trail':>5} {'init':>5} {'top5%':>6}")
    for vname, mult in VARIANTS:
        c, eq = seed7[vname]
        m = metrics(c, eq)
        ec = c["exit_reason"].value_counts().to_dict()
        print(f"  {vname:<5} {mult:>5.1f} {m['ret']:>8.1f} {m['pf']:>6.2f} {m['sharpe']:>7.2f} "
              f"{m['dd']:>7.1f} {m['pnl']:>10.0f} {m['n']:>5} {m['dur']:>6.1f} "
              f"{int((m['sem_pnl']>0).sum()):>4}/7 {ec.get('take_profit',0):>4} "
              f"{ec.get('trailing_stop',0):>5} {ec.get('initial_stop',0):>5} {100*m['top5']:>5.0f}%")

    print("\n  PnL par semestre (seed 7) :")
    sems = sorted(seed7["T0"][0]["semester"].unique())
    print(f"  {'sem':<8}" + "".join(f"{v:>12}" for v, _ in VARIANTS))
    for sem in sems:
        row = f"  {sem:<8}"
        for vname, _ in VARIANTS:
            c, _ = seed7[vname]
            row += f"{c[c['semester']==sem]['pnl'].sum():>12.0f}"
        print(row)

    # ── Robustesse 5 seeds ──
    print("\n" + "=" * 130)
    print("Robustesse 5 seeds : medianes + %seeds qui battent T0")
    print("=" * 130)
    print(f"  {'var':<5} {'medRet%':>8} {'medPF':>6} {'medDD%':>8} {'medPnL$':>10} {'medDurJ':>8} {'%bat T0':>8}")
    for vname, mult in VARIANTS:
        sub = dfr[dfr["variant"] == vname]
        if vname == "T0":
            print(f"  {vname:<5} {sub['ret'].median():>8.1f} {sub['pf'].median():>6.2f} "
                  f"{sub['dd'].median():>8.1f} {sub['pnl'].median():>10.0f} {sub['dur'].median():>8.1f} {'-':>8}")
        else:
            s0 = dfr[dfr["variant"] == "T0"]
            beat = float((sub["ret"].values > s0["ret"].values).mean())
            print(f"  {vname:<5} {sub['ret'].median():>8.1f} {sub['pf'].median():>6.2f} "
                  f"{sub['dd'].median():>8.1f} {sub['pnl'].median():>10.0f} {sub['dur'].median():>8.1f} "
                  f"{100*beat:>7.0f}%")

    # ── Attribution causale vs T0 (seed 7) ──
    print("\n" + "=" * 130)
    print("Attribution vs T0 (seed 7) : trades trailing_stop de T0 -> devenir sous T_i")
    print("=" * 130)
    c_t0, _ = seed7["T0"]
    base_tr = c_t0[c_t0["exit_reason"] == "trailing_stop"]
    print(f"  T0 trailing_stop = {len(base_tr)} trades")
    # MFE/MAE du chemin T0 pour tous les trailing T0
    base_tr_m = base_tr.merge(mfe_mae_for(base_tr, px_high, px_low),
                              on=["symbol", "entry_date", "exit_date"], how="left")
    for vname, mult in VARIANTS[1:]:
        c_i, _ = seed7[vname]
        m = base_tr_m.merge(c_i[["symbol", "signal_date", "exit_reason", "exit_date", "return_pct"]],
                            on=["symbol", "signal_date"], suffixes=("", "_ti"))
        if m.empty:
            print(f"  {vname}: (aucune intersection)")
            continue
        saved = m[m["exit_reason_ti"] == "take_profit"]
        aggr_mask = (m["exit_reason_ti"] == "trailing_stop") & (m["return_pct_ti"] < m["return_pct"])
        aggr = m[aggr_mask]
        other = m[~m["exit_reason_ti"].isin(["take_profit", "trailing_stop"])]
        saved_gain = float((saved["return_pct_ti"] - saved["return_pct"]).sum()) if len(saved) else 0.0
        aggr_loss = float((m.loc[aggr_mask, "return_pct"] - m.loc[aggr_mask, "return_pct_ti"]).sum())
        extra_delay = float((pd.to_datetime(saved["exit_date_ti"]) - pd.to_datetime(saved["exit_date"])).dt.days.mean()) if len(saved) else float("nan")
        print(f"  {vname} (trail {mult}xATR) : T0 trail->TP (PREMATURE sauves) = {len(saved):>4} "
              f"(gain {saved_gain:>7.1f}%, MFE med {100*saved['mfe'].median():.1f}% MAE med "
              f"{100*saved['mae'].median():.1f}%, delai supp {extra_delay:.0f}j) | "
              f"T0 trail->trail plus profond = {len(aggr):>4} (perte supp {aggr_loss:>7.1f}%) | "
              f"autre = {len(other):>4} | NET={saved_gain - aggr_loss:>8.1f}%")

    # ── Gates ──
    print("\n" + "=" * 130)
    print("GATES E12-2C")
    print("=" * 130)
    s0 = dfr[dfr["variant"] == "T0"]
    for vname, mult in VARIANTS[1:]:
        sub = dfr[dfr["variant"] == vname]
        m0 = metrics(*seed7["T0"]); mi = metrics(*seed7[vname])
        sem_better = int((mi["sem_pf"].reindex(sems).fillna(0) > m0["sem_pf"].reindex(sems).fillna(0)).sum())
        g1 = sem_better >= 5
        s26_0 = float(m0["sem_pnl"].get("2026H1", 0)); s26_i = float(mi["sem_pnl"].get("2026H1", 0))
        g2 = s26_i > s26_0
        wors = ((m0["sem_pnl"] < 0) & (mi["sem_pnl"] < m0["sem_pnl"] * 1.5)).sum()
        g3 = bool(wors == 0)
        dd0 = abs(m0["dd"]); ddi = abs(mi["dd"])
        g4 = (ddi / dd0 - 1.0) <= 0.20 if dd0 > 0 else True
        g5 = mi["top5"] <= 0.25 and (mi["top5"] - m0["top5"]) <= 0.10
        c_i, _ = seed7[vname]
        mm = base_tr_m.merge(c_i[["symbol", "signal_date", "exit_reason", "return_pct"]],
                             on=["symbol", "signal_date"], suffixes=("", "_ti"))
        saved_gain = float((mm[mm["exit_reason_ti"] == "take_profit"]["return_pct_ti"] -
                            mm[mm["exit_reason_ti"] == "take_profit"]["return_pct"]).sum()) \
            if len(mm[mm["exit_reason_ti"] == "take_profit"]) else 0.0
        aggr_loss = float((mm["return_pct"] - mm["return_pct_ti"])[
            (mm["exit_reason_ti"] == "trailing_stop") & (mm["return_pct_ti"] < mm["return_pct"])].sum())
        g6 = saved_gain >= aggr_loss
        beat = float((sub["ret"].values > s0["ret"].values).mean())
        g7 = beat >= 0.6
        print(f"  {vname} (trail {mult}xATR) : G1={g1} ({sem_better}/7) | G2={g2} (26H1 {s26_0:.0f}->{s26_i:.0f}$) | "
              f"G3={g3} | G4={g4} (DD {m0['dd']:.1f}->{mi['dd']:.1f}%) | G5={g5} (top5 {100*m0['top5']:.0f}->{100*mi['top5']:.0f}%) | "
              f"G6={g6} ({saved_gain:.0f} vs {aggr_loss:.0f}) | G7={g7} ({100*beat:.0f}% seeds) | "
              f"dur {m0['dur']:.1f}->{mi['dur']:.1f}j")
        npass = sum([g1, g2, g3, g4, g5, g6, g7])
        print(f"      -> {npass}/7 gates")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    dfr.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
