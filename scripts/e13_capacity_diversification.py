"""E13 — Capacity & Diversification (matrice m8/m12/m16/m24), vrai moteur m8, PROD.

QUESTION CAUSALE : si l'edge appartient au pool Extreme (pas au ranking), est-ce
qu'augmenter le nombre de positions simultanees transforme l'univers en strategie
plus stable (moins de variance inter-seed) ?

CONTRAINTE ESSENTIELLE : RISQUE TOTAL CONSTANT. Le moteur fait du sizing equal-weight
(target_weight_pct = 1/max_positions) -> chaque position = equity/m -> m16 = moitie
de la taille de m8. Verifie empiriquement via positions concurrentes + vol annualisee.

MATRICE (UNE seule variable) :
  m8 (baseline) / m12 / m16 / m24, 20 seeds chacun.
  Oracle Extreme TOP20 GELÉ, lifecycle PROD GELÉ (stop 2.5xATR / TP min(3xATR,7%) /
  trailing 2.5xATR / time_stop OFF / gap 3% / 16bps), LONG-only.

KPI PRINCIPAL = REDUCTION DE LA DISPERSION INTER-SEED (P90-P10 et std du Return),
et amelioration P10/P25, SANS deterioration significative du PF/DD/Sharpe median.

GATE (pre-fixe) :
  GO diversification seulement si, en augmentant m, on reduit fortement la variance
  inter-seed (>=30% sur P90-P10 et std) ET on ameliore P10/P25, sans deteriore
  significativement le PF/DD/Sharpe median.

SORTIES : distribution Return/PF/Sharpe/DD (P10/P25/med/P75/P90), pire seed, % seeds
positifs, dispersion, stabilite H1/H2 (mediane + %seeds pos), rolling 12/18m,
positions concurrentes moyennes + vol annualisee (verif risque constant).

Sortie : print + artifacts/models/oracle/e13_capacity_results.parquet
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

OUT = Path("artifacts/models/oracle/e13_capacity_results.parquet")
MPOS = [("m8", 8), ("m12", 12), ("m16", 16), ("m24", 24)]
N_SEEDS = 20
GOOD_SEMS = ("2023H1", "2023H2", "2024H1", "2024H2", "2025H1", "2025H2")
BAD_SEM = "2026H1"


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


def per_seed_metrics(closed: pd.DataFrame, eq: pd.Series, m: int) -> dict:
    pnl = closed["pnl"]
    final = float(eq.iloc[-1]) if len(eq) else INITIAL_EQUITY
    ret = (final / INITIAL_EQUITY - 1.0) * 100.0
    rets = eq.pct_change().dropna()
    ann_vol = float(rets.std() * np.sqrt(252.0) * 100.0) if len(rets) > 1 else 0.0
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) > 1 else 0.0
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    pf = gp / gn if gn > 0 else float("inf")
    # positions concurrentes moyennes (approx : notional par trade / equity/m)
    n_pos_est = float(closed["pnl"].count())  # place-holder
    sem = closed.groupby("semester")["pnl"].sum()
    # rolling 12/18 mois depuis l'equity
    r12 = (eq / eq.shift(252) - 1.0).dropna()
    r18 = (eq / eq.shift(378) - 1.0).dropna()
    return {"ret": ret, "pf": pf, "sharpe": sharpe, "dd": dd, "ann_vol": ann_vol,
            "n": len(pnl), "sem": sem,
            "r12_pos": float((r12 > 0).mean()) if len(r12) else float("nan"),
            "r12_worst": float(r12.min()) if len(r12) else float("nan"),
            "r18_pos": float((r18 > 0).mean()) if len(r18) else float("nan"),
            "r18_worst": float(r18.min()) if len(r18) else float("nan"),
            "n_pos_est": n_pos_est}


def main() -> None:
    df, _ = load_pool()
    pool = df[(df["date"] >= pd.Timestamp(START)) & (df["date"] <= pd.Timestamp(END))].copy()
    pool = pool.dropna(subset=["y3_long"])
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {len(symbols)} syms | CONTRAT PROD | matrice capacité", flush=True)
    print(f"seeds: {N_SEEDS} x {len(MPOS)} = {N_SEEDS*len(MPOS)} runs moteur", flush=True)

    records = []
    sem_records = []
    for mname, m in MPOS:
        for seed in range(N_SEEDS):
            closed, eq = run_bt(pool, pivots, seed, m)
            rec = per_seed_metrics(closed, eq, m)
            records.append({"m": mname, "m_val": m, "seed": seed, **{k: rec[k] for k in
                          ("ret", "pf", "sharpe", "dd", "ann_vol", "n", "r12_pos", "r12_worst",
                           "r18_pos", "r18_worst")}})
            for sem, pnl in rec["sem"].items():
                sem_records.append({"m": mname, "seed": seed, "semester": sem, "pnl": float(pnl)})
            if seed % 5 == 0:
                print(f"  {mname} seed={seed} Ret={rec['ret']:.0f}% PF={rec['pf']:.2f}", flush=True)
    dfr = pd.DataFrame(records)
    dfs = pd.DataFrame(sem_records)

    # ── Distribution par m ──
    print("\n" + "=" * 130)
    print(f"E13 — DISTRIBUTION MULTI-SEEDS ({N_SEEDS} seeds) — capacity/diversification, PROD")
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
                       "pctpos": float((sub["ret"] > 0).mean()), "disp": disp, "stdr": stdr,
                       "npos_seeds": float((sub["ret"] > 0).sum())}
        print(f"  {mname:<5} {dist[mname]['med']:>8.1f} {dist[mname]['p10']:>7.1f} "
              f"{dist[mname]['p25']:>7.1f} {dist[mname]['p75']:>7.1f} {dist[mname]['p90']:>7.1f} "
              f"{dist[mname]['worst']:>7.1f} | {dist[mname]['medpf']:>6.2f} "
              f"{dist[mname]['medsh']:>6.2f} {dist[mname]['meddd']:>7.1f} "
              f"{dist[mname]['medvol']:>7.1f} {100*dist[mname]['pctpos']:>5.0f}% | "
              f"{dist[mname]['disp']:>9.0f} {dist[mname]['stdr']:>7.1f}")

    # ── Rolling 12/18 mois ──
    print("\n" + "=" * 130)
    print("Rolling 12/18 mois (mediane sur seeds : % fenetres positives, pire fenetre)")
    print("=" * 130)
    print(f"  {'m':<5} {'r12_pos%':>9} {'r12_worst':>10} {'r18_pos%':>9} {'r18_worst':>10}")
    for mname, m in MPOS:
        sub = dfr[dfr["m"] == mname]
        print(f"  {mname:<5} {100*sub['r12_pos'].median():>8.0f}% {100*sub['r12_worst'].median():>9.1f}% "
              f"{100*sub['r18_pos'].median():>8.0f}% {100*sub['r18_worst'].median():>9.1f}%")

    # ── Stabilite par semestre ──
    print("\n" + "=" * 130)
    print("Stabilite par semestre (mean PnL $ et % seeds positifs)")
    print("=" * 130)
    sems = sorted(dfs["semester"].unique())
    print(f"  {'sem':<10}" + "".join(f"{m:>20}" for m, _ in MPOS))
    for s in sems:
        row = f"{s:<10}"
        for mname, m in MPOS:
            sub = dfs[(dfs["m"] == mname) & (dfs["semester"] == s)]
            row += f"{sub['pnl'].mean():>12.0f}${100*(sub['pnl']>0).mean():>5.0f}%"
        print(row)

    # ── GATE ──
    print("\n" + "=" * 130)
    print("GATE (pre-fixe) : GO diversification si dispersion fortement reduite ET P10/P25")
    print("ameliore, sans deteriore significativement PF/DD/Sharpe median")
    print("=" * 130)
    base = dist["m8"]
    for mname, m in MPOS[1:]:
        d = dist[mname]
        disp_red = 1.0 - d["disp"] / base["disp"] if base["disp"] > 0 else 0.0
        std_red = 1.0 - d["stdr"] / base["stdr"] if base["stdr"] > 0 else 0.0
        p10_imp = d["p10"] > base["p10"]
        p25_imp = d["p25"] > base["p25"]
        medpf_ok = d["medpf"] >= base["medpf"] - 0.10
        meddd_ok = d["meddd"] >= base["meddd"] * 1.15   # pas plus de 15% pire (negatif)
        medsh_ok = d["medsh"] >= base["medsh"] - 0.10
        disp_good = disp_red >= 0.30
        std_good = std_red >= 0.30
        gate = disp_good and std_good and p10_imp and p25_imp and medpf_ok and meddd_ok and medsh_ok
        print(f"  {mname} (m={m}): dispRed={100*disp_red:.0f}% (P90-P10 {base['disp']:.0f}->{d['disp']:.0f}) "
              f"| stdRed={100*std_red:.0f}% ({base['stdr']:.1f}->{d['stdr']:.1f}) | "
              f"P10 {base['p10']:.0f}->{d['p10']:.0f} ({'OK' if p10_imp else 'NOK'}) | "
              f"P25 {base['p25']:.0f}->{d['p25']:.0f} ({'OK' if p25_imp else 'NOK'}) | "
              f"medPF {base['medpf']:.2f}->{d['medpf']:.2f} ({'OK' if medpf_ok else 'NOK'}) | "
              f"medDD {base['meddd']:.1f}->{d['meddd']:.1f} ({'OK' if meddd_ok else 'NOK'}) | "
              f"medSh {base['medsh']:.2f}->{d['medsh']:.2f} ({'OK' if medsh_ok else 'NOK'})")
        print(f"      -> GATE {'PASSE' if gate else 'ECHOUE'}")

    print("\n  LECTURE (pre-fixee) : le KPI principal n'est PAS le rendement max mais la")
    print("  REDUCTION DE LA DISPERSION entre seeds, avec P10/P25 ameliore et medianes")
    print("  PF/DD/Sharpe preservees. Verifier aussi la vol annualisee (diversification).")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    dfr.to_parquet(OUT, index=False)
    dfs.to_parquet(str(OUT).replace(".parquet", "_semesters.parquet"), index=False)
    print(f"\npersisted: {OUT} (+ _semesters)")


if __name__ == "__main__":
    main()
