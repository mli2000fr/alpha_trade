"""E13-B — Confirmation baseline m16 vs m24 (50 seeds), avant gel.

Validation finale LÉGÈRE, pas un nouveau cycle de recherche. Aucun autre paramètre.
- m16 vs m24 uniquement ; 50 seeds chacun.
- Oracle Extreme TOP20 / PROD lifecycle / LONG-only / risque total constant (equal-weight 1/m).
- Même période 2023-2026, mêmes coûts, mêmes gates.
- Mesures : médiane, P10/P25, pire seed, DD, PF, Sharpe, dispersion inter-seed (P90-P10, std),
  rolling 12/18 mois, % seeds positifs.

OBJECTIF : vérifier que m24 garde SON AVANTAGE de dispersion et que P10/pire seed restent
clairement supérieurs à m16, sur 50 seeds (plus stable que 20).

GATE (pre-fixe) : GO m24 comme baseline si, sur 50 seeds, m24 a
  - dispersion (P90-P10 et std) nettement < m16,
  - P10 et pire seed > m16,
  - médianes PF/DD/Sharpe non détériorées vs m16 (ou équivalentes).
Sinon m16 reste baseline.

Sortie : print + artifacts/models/oracle/e13b_baseline_confirmation.parquet
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
    START,
    build_signals,
    load_pivots,
    load_pool,
)

OUT = Path("artifacts/models/oracle/e13b_baseline_confirmation.parquet")
MPOS = [("m16", 16), ("m24", 24)]
N_SEEDS = 50


def make_engine(m: int) -> BacktestEngine:
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(), end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY, max_positions=m,
        atr_risk_stop_multiple=2.5, initial_stop_atr_multiple=2.5,
        tp_atr_multiple=3.0, tp_max_pct=0.07,
        trailing_stop_long_pct=None, trailing_stop_short_pct=None,
        use_canonical_costs=True, entry_limit_offset_pct=0.0,
        min_score_threshold=0.0, use_live_protection_logic=True,
        time_stop_enabled=False,
        microstructure=MicrostructureConfig(max_entry_gap_pct=0.03, intrabar_priority="conservative"),
    )
    return BacktestEngine(cfg)


def run_bt(pool: pd.DataFrame, pivots: dict, seed: int, m: int) -> tuple[pd.DataFrame, pd.Series]:
    sig = build_signals(pool, 0.80, 1.01, seed)
    res = make_engine(m).run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    eq = res.equity_curve
    closed = res.closed_trades_df.copy()
    closed["entry_date"] = pd.to_datetime(closed["entry_date"]).dt.normalize()
    closed["symbol"] = closed["symbol"].astype(str)
    closed["pnl"] = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
    closed["semester"] = closed["entry_date"].dt.year.astype(str) + \
        np.where(closed["entry_date"].dt.month <= 6, "H1", "H2")
    return closed, eq


def per_seed_metrics(closed: pd.DataFrame, eq: pd.Series) -> dict:
    pnl = closed["pnl"]
    final = float(eq.iloc[-1]) if len(eq) else INITIAL_EQUITY
    ret = (final / INITIAL_EQUITY - 1.0) * 100.0
    rets = eq.pct_change().dropna()
    ann_vol = float(rets.std() * np.sqrt(252.0) * 100.0) if len(rets) > 1 else 0.0
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) > 1 else 0.0
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    pf = gp / gn if gn > 0 else float("inf")
    sem = closed.groupby("semester")["pnl"].sum()
    r12 = (eq / eq.shift(252) - 1.0).dropna()
    r18 = (eq / eq.shift(378) - 1.0).dropna()
    return {"ret": ret, "pf": pf, "sharpe": sharpe, "dd": dd, "ann_vol": ann_vol,
            "n": len(pnl), "sem": sem,
            "r12_pos": float((r12 > 0).mean()) if len(r12) else float("nan"),
            "r12_worst": float(r12.min()) if len(r12) else float("nan"),
            "r18_pos": float((r18 > 0).mean()) if len(r18) else float("nan"),
            "r18_worst": float(r18.min()) if len(r18) else float("nan")}


def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {len(symbols)} syms | CONTRAT PROD | confirmation m16/m24", flush=True)
    print(f"seeds: {N_SEEDS} x 2 = {N_SEEDS*2} runs moteur", flush=True)

    records = []
    sem_records = []
    for mname, m in MPOS:
        for seed in range(N_SEEDS):
            closed, eq = run_bt(pool, pivots, seed, m)
            rec = per_seed_metrics(closed, eq)
            records.append({"m": mname, "m_val": m, "seed": seed, **{k: rec[k] for k in
                          ("ret", "pf", "sharpe", "dd", "ann_vol", "n", "r12_pos", "r12_worst",
                           "r18_pos", "r18_worst")}})
            for sem, pnl in rec["sem"].items():
                sem_records.append({"m": mname, "seed": seed, "semester": sem, "pnl": float(pnl)})
            if seed % 10 == 0:
                print(f"  {mname} seed={seed} Ret={rec['ret']:.0f}% PF={rec['pf']:.2f}", flush=True)
    dfr = pd.DataFrame(records)
    dfs = pd.DataFrame(sem_records)

    print("\n" + "=" * 130)
    print(f"E13-B — CONFIRMATION BASELINE m16 vs m24 ({N_SEEDS} seeds), PROD")
    print("=" * 130)
    print(f"  {'m':<5} {'medRet%':>8} {'P10':>7} {'P25':>7} {'P75':>7} {'P90':>7} {'pire':>7} | "
          f"{'medPF':>6} {'medSh':>6} {'medDD%':>7} {'medVol%':>7} {'%pos':>6} | "
          f"{'dispP90P10':>9} {'stdRet':>7}")
    dist = {}
    for mname, m in MPOS:
        sub = dfr[dfr["m"] == mname]
        disp = float(sub["ret"].quantile(0.90) - sub["ret"].quantile(0.10))
        stdr = float(sub["ret"].std())
        dist[mname] = {"med": float(sub["ret"].median()), "p10": float(sub["ret"].quantile(0.10)),
                       "p25": float(sub["ret"].quantile(0.25)), "p75": float(sub["ret"].quantile(0.75)),
                       "p90": float(sub["ret"].quantile(0.90)), "worst": float(sub["ret"].min()),
                       "medpf": float(sub["pf"].median()), "medsh": float(sub["sharpe"].median()),
                       "meddd": float(sub["dd"].median()), "medvol": float(sub["ann_vol"].median()),
                       "pctpos": float((sub["ret"] > 0).mean()), "disp": disp, "stdr": stdr}
        print(f"  {mname:<5} {dist[mname]['med']:>8.1f} {dist[mname]['p10']:>7.1f} "
              f"{dist[mname]['p25']:>7.1f} {dist[mname]['p75']:>7.1f} {dist[mname]['p90']:>7.1f} "
              f"{dist[mname]['worst']:>7.1f} | {dist[mname]['medpf']:>6.2f} "
              f"{dist[mname]['medsh']:>6.2f} {dist[mname]['meddd']:>7.1f} "
              f"{dist[mname]['medvol']:>7.1f} {100*dist[mname]['pctpos']:>5.0f}% | "
              f"{dist[mname]['disp']:>9.0f} {dist[mname]['stdr']:>7.1f}")

    d16, d24 = dist["m16"], dist["m24"]
    print("\n" + "=" * 130)
    print("Comparaison m24 vs m16")
    print("=" * 130)
    print(f"  dispersion P90-P10 : {d16['disp']:.0f} -> {d24['disp']:.0f}  (m24 {100*(1-d24['disp']/d16['disp']):.0f}% < m16)")
    print(f"  stdRet             : {d16['stdr']:.1f} -> {d24['stdr']:.1f}  (m24 {100*(1-d24['stdr']/d16['stdr']):.0f}% < m16)")
    print(f"  P10                : {d16['p10']:.1f}% -> {d24['p10']:.1f}%")
    print(f"  P25                : {d16['p25']:.1f}% -> {d24['p25']:.1f}%")
    print(f"  pire seed          : {d16['worst']:.1f}% -> {d24['worst']:.1f}%")
    print(f"  medRet             : {d16['med']:.1f}% -> {d24['med']:.1f}%")
    print(f"  medPF / medDD / medSh : {d16['medpf']:.2f}/{d16['meddd']:.1f}/{d16['medsh']:.2f} "
          f"-> {d24['medpf']:.2f}/{d24['meddd']:.1f}/{d24['medsh']:.2f}")

    print("\n  Rolling 12/18 mois (médiane sur seeds) :")
    print(f"  {'m':<5} {'r12_pos%':>9} {'r12_worst':>10} {'r18_pos%':>9} {'r18_worst':>10}")
    for mname, m in MPOS:
        sub = dfr[dfr["m"] == mname]
        print(f"  {mname:<5} {100*sub['r12_pos'].median():>8.0f}% {100*sub['r12_worst'].median():>9.1f}% "
              f"{100*sub['r18_pos'].median():>8.0f}% {100*sub['r18_worst'].median():>9.1f}%")

    print("\n  Stabilité par semestre (mean PnL $ / %seeds positifs) :")
    sems = sorted(dfs["semester"].unique())
    print(f"  {'sem':<10}" + "".join(f"{m:>20}" for m, _ in MPOS))
    for s in sems:
        row = f"{s:<10}"
        for mname, m in MPOS:
            sub = dfs[(dfs["m"] == mname) & (dfs["semester"] == s)]
            row += f"{sub['pnl'].mean():>12.0f}${100*(sub['pnl']>0).mean():>5.0f}%"
        print(row)

    # ── Gate m24 ──
    disp_ok = d24["disp"] < d16["disp"] * 0.70
    std_ok = d24["stdr"] < d16["stdr"] * 0.75
    p10_ok = d24["p10"] > d16["p10"]
    worst_ok = d24["worst"] > d16["worst"]
    med_ok = (d24["medpf"] >= d16["medpf"] - 0.05 and d24["meddd"] >= d16["meddd"] * 1.10
              and d24["medsh"] >= d16["medsh"] - 0.05)
    gate = disp_ok and std_ok and p10_ok and worst_ok and med_ok
    print("\n" + "=" * 130)
    print("GATE m24 comme baseline (pré-fixé) :")
    print("=" * 130)
    print(f"  dispersion m24 < m16*0.70 : {disp_ok} ({d24['disp']:.0f} vs {d16['disp']*0.70:.0f})")
    print(f"  std m24 < m16*0.75        : {std_ok} ({d24['stdr']:.1f} vs {d16['stdr']*0.75:.1f})")
    print(f"  P10 m24 > m16             : {p10_ok} ({d24['p10']:.1f} vs {d16['p10']:.1f})")
    print(f"  pire seed m24 > m16       : {worst_ok} ({d24['worst']:.1f} vs {d16['worst']:.1f})")
    print(f"  médianes PF/DD/Sh préservées : {med_ok}")
    print(f"  -> GATE {'PASSE : m24 = baseline (m16 challenger)' if gate else 'ECHOUE : m16 reste baseline'}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    dfr.to_parquet(OUT, index=False)
    dfs.to_parquet(str(OUT).replace(".parquet", "_semesters.parquet"), index=False)
    print(f"\npersisted: {OUT} (+ _semesters)")


if __name__ == "__main__":
    main()
