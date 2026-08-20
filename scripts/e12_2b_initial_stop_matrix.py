"""E12-2B — Matrice stop INITIAL seul, sous contrat PROD, vrai moteur m8.

SPEC user 2026-08-20 : S0=2.5xATR (baseline), S1=3.0xATR, S2=3.5xATR, S3=4.0xATR.
TP min(3xATR,7%) / trailing 2.5xATR / time_stop OFF / gap 3% / costs 16bps / m8 :
TOUT gelé au contrat PROD. Seul le stop initial varie (decouplage opt-in
initial_stop_atr_multiple du moteur recherche : trailing derive de risk_per_share
= 2.5xATR, PAS de l'initial stop elargi).

REG.RESSION au demarrage : seed 7 avec config par defaut (initial_stop_atr_multiple=0)
doit reproduire E12-A0b bit-for-bit : PnL +72,462 ; exits TP 488 / trailing 182 /
initial 131 / time_stop 0. Sinon STOP.

GATES (pre-fixes) :
  G1 PF/expectancy > baseline sur >=5/7 semestres
  G2 amelioration 2026H1 (mais pas unique moteur)
  G3 aucun semestre avec degradation catastrophique
  G4 MaxDD consolide n'augmente pas de plus de ~15-20% relatif
  G5 gain non concentre sur quelques trades
  G6 premature sauves >= true losers aggraves (attribution join vs S0)
  G7 survit au vrai moteur m8 + majorite des seeds

Sortie : print + artifacts/models/oracle/e12_2b_stop_matrix.parquet
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

OUT = Path("artifacts/models/oracle/e12_2b_stop_matrix.parquet")
VARIANTS = [("S0", 2.5), ("S1", 3.0), ("S2", 3.5), ("S3", 4.0)]
SEEDS = [0, 3, 7, 11, 19]


def make_engine(initial_stop_mult: float) -> BacktestEngine:
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(), end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY, max_positions=8,
        atr_risk_stop_multiple=2.5,          # trailing = 2.5xATR (risk_per_share)
        initial_stop_atr_multiple=initial_stop_mult,  # stop initial seul (0=defaut, 2.5=PROD)
        tp_atr_multiple=3.0, tp_max_pct=0.07,
        trailing_stop_long_pct=None,
        trailing_stop_short_pct=None,
        use_canonical_costs=True, entry_limit_offset_pct=0.0,
        min_score_threshold=0.0, use_live_protection_logic=True,
        time_stop_enabled=False,
        microstructure=MicrostructureConfig(max_entry_gap_pct=0.03, intrabar_priority="conservative"),
    )
    return BacktestEngine(cfg)


def run_bt(pool: pd.DataFrame, pivots: dict, seed: int, init_mult: float) -> tuple[pd.DataFrame, pd.Series]:
    sig = build_signals(pool, 0.80, 1.01, seed)
    res = make_engine(init_mult).run(
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
        gn = -float(s[s < 0].sum())
        if gn <= 0:
            return float("inf")
        return float(s[s > 0].sum()) / gn

    sem_pf = closed.groupby("semester", group_keys=False).apply(_sem_pf, include_groups=False)
    top5 = float(pnl.sort_values(ascending=False).head(5).sum()) / max(float(pnl.sum()), 1e-9)
    top10 = float(pnl.sort_values(ascending=False).head(10).sum()) / max(float(pnl.sum()), 1e-9)
    return {"ret": ret, "pf": pf, "sharpe": sharpe, "dd": dd, "pnl": float(pnl.sum()),
            "n": len(pnl), "sem_pnl": sem_pnl, "sem_pf": sem_pf, "top5": top5, "top10": top10}


def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {len(symbols)} syms | CONTRAT PROD | stop initial seul", flush=True)

    # ── Regression : config par defaut (initial_stop_atr_multiple=0) vs E12-A0b ──
    c0, _ = run_bt(pool, pivots, SEED_REP, 0.0)
    pnl0 = float(c0["pnl"].sum())
    ec = c0["exit_reason"].value_counts().to_dict()
    ok = abs(pnl0 - 72462.0) < 1.0 and ec.get("take_profit", 0) == 488 and \
        ec.get("trailing_stop", 0) == 182 and ec.get("initial_stop", 0) == 131 and \
        ec.get("time_stop", 0) == 0
    print(f"REGRESSION (seed {SEED_REP}, config par defaut) : PnL={pnl0:.0f}$ (attendu 72462) "
          f"| exits={ec} -> {'OK' if ok else 'ECHEC'}", flush=True)
    if not ok:
        print("STOP : regression E12-A0b non reproduite, ne pas lancer la matrice.")
        return

    # ── Matrice : variants x seeds ──
    results = []      # (variant, seed, metrics)
    seed7 = {}        # variant -> (closed, eq)
    for vname, mult in VARIANTS:
        for seed in SEEDS:
            closed, eq = run_bt(pool, pivots, seed, mult)
            m = metrics(closed, eq)
            results.append({"variant": vname, "stop_atr": mult, "seed": seed, **{k: m[k] for k in
                          ("ret", "pf", "sharpe", "dd", "pnl", "n", "top5", "top10")}})
            if seed == SEED_REP:
                seed7[vname] = (closed, eq)
        print(f"  {vname} (stop {mult}xATR) done", flush=True)

    dfr = pd.DataFrame(results)

    # ── Table consolidee (seed 7) ──
    print("\n" + "=" * 130)
    print("E12-2B  Matrice stop initial seul — seed 7 (vrai moteur m8, PROD)")
    print("=" * 130)
    print(f"  {'var':<5} {'stop':>6} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'DD%':>7} {'PnL$':>10} "
          f"{'N':>5} {'Sem+':>5} {'TP':>4} {'trail':>5} {'init':>5} {'top5%':>6}")
    for vname, mult in VARIANTS:
        c, eq = seed7[vname]
        m = metrics(c, eq)
        ec = c["exit_reason"].value_counts().to_dict()
        sem_pos = int((m["sem_pnl"] > 0).sum())
        print(f"  {vname:<5} {mult:>5.1f} {m['ret']:>8.1f} {m['pf']:>6.2f} {m['sharpe']:>7.2f} "
              f"{m['dd']:>7.1f} {m['pnl']:>10.0f} {m['n']:>5} {sem_pos:>4}/7 {ec.get('take_profit',0):>4} "
              f"{ec.get('trailing_stop',0):>5} {ec.get('initial_stop',0):>5} {100*m['top5']:>5.0f}%")

    # ── Par semestre (PnL, seed 7) ──
    print("\n  PnL par semestre (seed 7) :")
    sems = sorted(seed7["S0"][0]["semester"].unique())
    print(f"  {'sem':<8}" + "".join(f"{v:>12}" for v, _ in VARIANTS))
    for sem in sems:
        row = f"  {sem:<8}"
        for vname, _ in VARIANTS:
            c, _ = seed7[vname]
            row += f"{c[c['semester']==sem]['pnl'].sum():>12.0f}"
        print(row)

    # ── Robustesse multi-seed ──
    print("\n" + "=" * 130)
    print("Robustesse 5 seeds (0,3,7,11,19) : medianes + %seeds qui battent S0")
    print("=" * 130)
    print(f"  {'var':<5} {'medRet%':>8} {'medPF':>6} {'medDD%':>8} {'medPnL$':>10} {'%bat S0 ret':>12}")
    for vname, mult in VARIANTS:
        sub = dfr[dfr["variant"] == vname]
        if vname == "S0":
            print(f"  {vname:<5} {sub['ret'].median():>8.1f} {sub['pf'].median():>6.2f} "
                  f"{sub['dd'].median():>8.1f} {sub['pnl'].median():>10.0f} {'-':>12}")
        else:
            s0 = dfr[dfr["variant"] == "S0"]
            beat = float((sub["ret"].values > s0["ret"].values).mean())
            print(f"  {vname:<5} {sub['ret'].median():>8.1f} {sub['pf'].median():>6.2f} "
                  f"{sub['dd'].median():>8.1f} {sub['pnl'].median():>10.0f} {100*beat:>11.0f}%")

    # ── Attribution vs S0 (seed 7) : premature sauves / true losers aggraves ──
    print("\n" + "=" * 130)
    print("Attribution vs S0 (seed 7) : exit_reason change sur les memes (symbol, signal_date)")
    print("=" * 130)
    c_s0, _ = seed7["S0"]
    base_init = c_s0[c_s0["exit_reason"] == "initial_stop"]
    print(f"  S0 initial_stop = {len(base_init)} trades")
    for vname, mult in VARIANTS[1:]:
        c_i, _ = seed7[vname]
        merged = base_init.merge(c_i[["symbol", "signal_date", "exit_reason", "return_pct"]],
                                 on=["symbol", "signal_date"], suffixes=("_s0", "_si"))
        if merged.empty:
            print(f"  {vname}: (aucune intersection)")
            continue
        saved = merged[merged["exit_reason_si"] == "take_profit"]
        aggr = merged[(merged["exit_reason_si"] == "initial_stop") & (merged["return_pct_si"] < merged["return_pct_s0"])]
        trail = merged[merged["exit_reason_si"] == "trailing_stop"]
        saved_gain = float((saved["return_pct_si"] - saved["return_pct_s0"]).sum()) if len(saved) else 0.0
        aggr_loss = float((aggr["return_pct_s0"] - aggr["return_pct_si"]).sum()) if len(aggr) else 0.0
        print(f"  {vname} (stop {mult}xATR) : S0 init->TP (PREMATURE sauves) = {len(saved):>4} "
              f"(gain {saved_gain:>7.1f}%) | init->init plus profond (TRUE_LOSER aggraves) = {len(aggr):>4} "
              f"(perte supp {aggr_loss:>7.1f}%) | init->trailing = {len(trail):>4} | "
              f"NET={saved_gain - aggr_loss:>8.1f}%")

    # ── Gates ──
    print("\n" + "=" * 130)
    print("GATES E12-2B")
    print("=" * 130)
    s0 = dfr[dfr["variant"] == "S0"]
    for vname, mult in VARIANTS[1:]:
        sub = dfr[dfr["variant"] == vname]
        # G1 : PF > baseline sur >=5/7 semestres (seed 7)
        m0 = metrics(*seed7["S0"]); mi = metrics(*seed7[vname])
        sem_better = int((mi["sem_pf"].reindex(sems).fillna(0) > m0["sem_pf"].reindex(sems).fillna(0)).sum())
        g1 = sem_better >= 5
        # G2 : 2026H1 ameliore
        s26_0 = float(m0["sem_pnl"].get("2026H1", 0)); s26_i = float(mi["sem_pnl"].get("2026H1", 0))
        g2 = s26_i > s26_0
        # G3 : pas de semestre catastrophe (aucun semestre perd plus de 1.5x vs S0)
        wors = ((m0["sem_pnl"] < 0) & (mi["sem_pnl"] < m0["sem_pnl"] * 1.5)).sum()
        g3 = bool(wors == 0)
        # G4 : MaxDD consolide +<=20% relatif
        dd0 = abs(m0["dd"]); ddi = abs(mi["dd"])
        g4 = (ddi / dd0 - 1.0) <= 0.20 if dd0 > 0 else True
        # G5 : concentration (top5) pas explosee (>20% du PnL ou +10pts vs S0)
        g5 = mi["top5"] <= 0.25 and (mi["top5"] - m0["top5"]) <= 0.10
        # G6 : premature sauves >= true losers aggraves (attribution)
        c_i, _ = seed7[vname]
        merged = base_init.merge(c_i[["symbol", "signal_date", "exit_reason", "return_pct"]],
                                 on=["symbol", "signal_date"], suffixes=("_s0", "_si"))
        saved_gain = float(((merged[merged["exit_reason_si"] == "take_profit"]["return_pct_si"] -
                             merged[merged["exit_reason_si"] == "take_profit"]["return_pct_s0"]).sum())) \
            if len(merged[merged["exit_reason_si"] == "take_profit"]) else 0.0
        aggr_loss = float(((merged[(merged["exit_reason_si"] == "initial_stop") &
                                   (merged["return_pct_si"] < merged["return_pct_s0"])]["return_pct_s0"] -
                            merged[(merged["exit_reason_si"] == "initial_stop") &
                                   (merged["return_pct_si"] < merged["return_pct_s0"])]["return_pct_si"]).sum())) \
            if len(merged[(merged["exit_reason_si"] == "initial_stop") & (merged["return_pct_si"] < merged["return_pct_s0"])]) else 0.0
        g6 = saved_gain >= aggr_loss
        # G7 : survit m8 + majorite seeds
        beat = float((sub["ret"].values > s0["ret"].values).mean())
        g7 = beat >= 0.6
        print(f"  {vname} (stop {mult}xATR) : G1={g1} ({sem_better}/7) | G2={g2} (26H1 {s26_0:.0f}->{s26_i:.0f}$) | "
              f"G3={g3} | G4={g4} (DD {m0['dd']:.1f}->{mi['dd']:.1f}%) | G5={g5} (top5 {100*m0['top5']:.0f}->{100*mi['top5']:.0f}%) | "
              f"G6={g6} ({saved_gain:.0f} vs {aggr_loss:.0f}) | G7={g7} ({100*beat:.0f}% seeds)")
        npass = sum([g1, g2, g3, g4, g5, g6, g7])
        print(f"      -> {npass}/7 gates")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    dfr.to_parquet(OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
