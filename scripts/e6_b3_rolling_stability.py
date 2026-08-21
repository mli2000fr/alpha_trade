"""E6-B3 — Rolling stability (test de FALSIFICATION) : EV_TOP20 vs RANK_TOP10.

OBJECTIF (spec user 2026-08-20) : vérifier la persistance temporelle de l'avantage
EV_TOP20, sachant que EV_ONLY semble surtout gagner en 2023. AUCUN retraining,
aucun tuning, aucune nouvelle feature — on réutilise exactement les scores/EV OOF
existants et on regarde la performance en fenêtres glissantes.

MÉTHODE :
- 2 découpages en parallèle : 12 mois glissants (offset 3 mois) pour détecter les
  ruptures, et 18 mois glissants (offset 6 mois) pour réduire le bruit.
  Descriptif, pas de recherche de meilleure fenêtre.
- Comparaison UNIQUEMENT : RANK_TOP10 vs EV_TOP20.
- Métriques par fenêtre : Return (somme PnL / equity), PF, expectancy, MaxDD
  (PnL réalisé cumulé par date de sortie), N trades, et surtout ΔEV =
  expectancy(EV_TOP20) − expectancy(RANK_TOP10).
- Diagnostic : contribution COMMON / EV_ONLY / RANK_ONLY par fenêtre.
- Focus 2025→2026H1 : EV_TOP20 reste-t-il meilleur via COMMON seul (ranking EV
  sans valeur marginale récente) ou EV_ONLY contribue-t-il encore ?

GATE (fixé AVANT de regarder les résultats) :
  EV_TOP20 reste candidat seulement si :
  G1 : majorité des fenêtres 12m ont ΔEV >= 0
  G2 : majorité des fenêtres 18m ont ΔEV >= 0
  G3 : l'avantage n'est PAS limité aux fenêtres contenant 2023 (au moins une
       fenêtre sans 2023 a ΔEV >= 0)
  G4 : pas de longue séquence récente où EV_TOP20 est systématiquement < RANK_TOP10
       (<= 2 fenêtres 12m consécutives négatives en fin de période)
  Si G1-G4 tous passés → challenger sérieux. Sinon → signal historique non stable.

Sortie : print + artifacts/models/oracle/e6_b3_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.e6_b2_ev_long_backtest import (
    END,
    START,
    add_ev_features,
    load_pivots,
    load_pool,
)
from scripts.e6_b2c_causal_attribution import (
    classify_trades,
    make_engine,
    run_and_collect,
)

OUT = Path("artifacts/models/oracle/e6_b3_results.parquet")
INITIAL_EQUITY = 100_000.0

WINDOWS_12M = [(d, d + pd.DateOffset(months=12) - pd.Timedelta(days=1))
               for d in pd.date_range(START, END, freq="3MS")]
WINDOWS_18M = [(d, d + pd.DateOffset(months=18) - pd.Timedelta(days=1))
               for d in pd.date_range(START, END, freq="6MS")]
# Clamp au END
WINDOWS_12M = [(s, min(e, pd.Timestamp(END))) for s, e in WINDOWS_12M if s <= pd.Timestamp(END)]
WINDOWS_18M = [(s, min(e, pd.Timestamp(END))) for s, e in WINDOWS_18M if s <= pd.Timestamp(END)]


def window_metrics(trades: pd.DataFrame, w_start: pd.Timestamp, w_end: pd.Timestamp) -> dict:
    """Métriques sur les trades dont l'entrée tombe dans la fenêtre."""
    t = trades[(trades["entry_date"] >= w_start) & (trades["entry_date"] <= w_end)]
    n = len(t)
    if n == 0:
        return {"n": 0, "return_pct": 0.0, "pf": float("nan"), "expectancy": 0.0,
                "max_dd_pct": 0.0, "pnl": 0.0}
    pnl = pd.to_numeric(t["pnl"], errors="coerce").fillna(0.0)
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    # MaxDD : PnL réalisé cumulé par date de sortie
    daily = t.assign(_pnl=pnl).groupby(t["exit_date"])["_pnl"].sum().sort_index().cumsum()
    if len(daily) > 1:
        dd = float((daily - daily.cummax()).min())
    else:
        dd = float(daily.min()) if len(daily) else 0.0
    return {
        "n": n,
        "return_pct": float(pnl.sum()) / INITIAL_EQUITY * 100.0,
        "pf": gp / gn if gn > 0 else float("inf"),
        "expectancy": float(pnl.mean()),
        "max_dd_pct": dd / INITIAL_EQUITY * 100.0,
        "pnl": float(pnl.sum()),
    }


def group_pnl_by_window(trades: pd.DataFrame, w_start: pd.Timestamp, w_end: pd.Timestamp) -> dict:
    """PnL par groupe (COMMON/EV_ONLY/RANK_ONLY) dans la fenêtre."""
    t = trades[(trades["entry_date"] >= w_start) & (trades["entry_date"] <= w_end)]
    out = {}
    for g, sub in t.groupby("group"):
        out[g] = float(pd.to_numeric(sub["pnl"], errors="coerce").fillna(0.0).sum())
    return out


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy().dropna(subset=["y3_long"])
    pool = add_ev_features(pool, feature_columns)
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]

    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")

    # Rejouer les deux portefeuilles (une seule fois chacun — pas de retraining)
    print("\n=== Rejeu moteur (RANK_TOP10 / EV_TOP20) ===", flush=True)
    t_rank = classify_trades(run_and_collect(pool, pivots, "RANK_TOP10"), pool)
    t_ev = classify_trades(run_and_collect(pool, pivots, "EV_TOP20"), pool)
    t_rank["entry_date"] = pd.to_datetime(t_rank["entry_date"]).dt.normalize()
    t_ev["entry_date"] = pd.to_datetime(t_ev["entry_date"]).dt.normalize()
    t_rank["exit_date"] = pd.to_datetime(t_rank["exit_date"]).dt.normalize()
    t_ev["exit_date"] = pd.to_datetime(t_ev["exit_date"]).dt.normalize()
    print(f"  RANK_TOP10 : {len(t_rank)} trades | PnL={t_rank['pnl'].sum():.0f}$")
    print(f"  EV_TOP20   : {len(t_ev)} trades | PnL={t_ev['pnl'].sum():.0f}$")

    # ── 12 mois glissants ──
    print("\n" + "=" * 130)
    print("FENÊTRES 12 MOIS GLISSANTS (offset 3 mois)")
    print("=" * 130)
    rows_12 = []
    for w_start, w_end in WINDOWS_12M:
        m_r = window_metrics(t_rank, w_start, w_end)
        m_e = window_metrics(t_ev, w_start, w_end)
        delta = m_e["expectancy"] - m_r["expectancy"]
        g_r = group_pnl_by_window(t_rank, w_start, w_end)
        g_e = group_pnl_by_window(t_ev, w_start, w_end)
        contains_2023 = w_start.year == 2023 or (w_start <= pd.Timestamp("2023-12-31") <= w_end)
        rows_12.append({
            "window": f"{w_start.date()}→{w_end.date()}", "contains_2023": contains_2023,
            "r_n": m_r["n"], "r_ret": m_r["return_pct"], "r_pf": m_r["pf"], "r_exp": m_r["expectancy"],
            "e_n": m_e["n"], "e_ret": m_e["return_pct"], "e_pf": m_e["pf"], "e_exp": m_e["expectancy"],
            "e_maxdd": m_e["max_dd_pct"],
            "delta_exp": delta,
            "r_common": g_r.get("COMMON", 0.0), "r_only": g_r.get("RANK_ONLY", 0.0),
            "e_common": g_e.get("COMMON", 0.0), "e_only": g_e.get("EV_ONLY", 0.0),
        })
    df12 = pd.DataFrame(rows_12)
    print(f"  {'fenêtre':<24} {'2023':>4} | {'R_n':>4} {'R_ret%':>7} {'R_exp':>7} | "
          f"{'E_n':>4} {'E_ret%':>7} {'E_exp':>7} {'E_DD%':>7} | {'ΔEV':>7} | {'E_COMMON':>9} {'E_ONLY':>8}")
    for r in df12.itertuples():
        print(f"  {r.window:<24} {str(r.contains_2023):>4} | {r.r_n:>4} {r.r_ret:>7.1f} {r.r_exp:>7.2f} | "
              f"{r.e_n:>4} {r.e_ret:>7.1f} {r.e_exp:>7.2f} {r.e_maxdd:>7.1f} | {r.delta_exp:>7.2f} | "
              f"{r.e_common:>9.0f} {r.e_only:>8.0f}")

    # ── 18 mois glissants ──
    print("\n" + "=" * 130)
    print("FENÊTRES 18 MOIS GLISSANTS (offset 6 mois)")
    print("=" * 130)
    rows_18 = []
    for w_start, w_end in WINDOWS_18M:
        m_r = window_metrics(t_rank, w_start, w_end)
        m_e = window_metrics(t_ev, w_start, w_end)
        delta = m_e["expectancy"] - m_r["expectancy"]
        g_e = group_pnl_by_window(t_ev, w_start, w_end)
        contains_2023 = w_start.year == 2023 or (w_start <= pd.Timestamp("2023-12-31") <= w_end)
        rows_18.append({
            "window": f"{w_start.date()}→{w_end.date()}", "contains_2023": contains_2023,
            "r_n": m_r["n"], "r_ret": m_r["return_pct"], "r_pf": m_r["pf"], "r_exp": m_r["expectancy"],
            "e_n": m_e["n"], "e_ret": m_e["return_pct"], "e_pf": m_e["pf"], "e_exp": m_e["expectancy"],
            "e_maxdd": m_e["max_dd_pct"], "delta_exp": delta,
            "e_common": g_e.get("COMMON", 0.0), "e_only": g_e.get("EV_ONLY", 0.0),
        })
    df18 = pd.DataFrame(rows_18)
    print(f"  {'fenêtre':<24} {'2023':>4} | {'R_n':>4} {'R_ret%':>7} {'R_exp':>7} | "
          f"{'E_n':>4} {'E_ret%':>7} {'E_exp':>7} {'E_DD%':>7} | {'ΔEV':>7} | {'E_COMMON':>9} {'E_ONLY':>8}")
    for r in df18.itertuples():
        print(f"  {r.window:<24} {str(r.contains_2023):>4} | {r.r_n:>4} {r.r_ret:>7.1f} {r.r_exp:>7.2f} | "
              f"{r.e_n:>4} {r.e_ret:>7.1f} {r.e_exp:>7.2f} {r.e_maxdd:>7.1f} | {r.delta_exp:>7.2f} | "
              f"{r.e_common:>9.0f} {r.e_only:>8.0f}")

    # ── GATE (pré-fixé) ──
    print("\n" + "=" * 130)
    print("GATE (fixé avant de regarder les résultats)")
    print("=" * 130)
    d12 = df12["delta_exp"].dropna()
    d18 = df18["delta_exp"].dropna()
    g1 = bool((d12 >= 0).mean() >= 0.5) if len(d12) else False
    g2 = bool((d18 >= 0).mean() >= 0.5) if len(d18) else False
    # G3 : au moins une fenêtre SANS 2023 avec ΔEV >= 0
    non2023_12 = df12[~df12["contains_2023"]]["delta_exp"].dropna()
    non2023_18 = df18[~df18["contains_2023"]]["delta_exp"].dropna()
    g3 = bool((non2023_12 >= 0).any() or (non2023_18 >= 0).any())
    # G4 : pas de longue séquence récente négative (<= 2 fenêtres 12m consécutives en fin)
    trailing = df12["delta_exp"].dropna().tolist()
    neg_streak = 0
    for v in reversed(trailing):
        if v < 0:
            neg_streak += 1
        else:
            break
    g4 = neg_streak <= 2

    print(f"G1 (majorité fenêtres 12m ΔEV>=0) : {g1}  ({(d12>=0).mean()*100:.0f}% des {len(d12)})")
    print(f"G2 (majorité fenêtres 18m ΔEV>=0) : {g2}  ({(d18>=0).mean()*100:.0f}% des {len(d18)})")
    print(f"G3 (≥1 fenêtre sans 2023 ΔEV>=0)  : {g3}  (12m: {(non2023_12>=0).sum()}/{len(non2023_12)}, "
          f"18m: {(non2023_18>=0).sum()}/{len(non2023_18)})")
    print(f"G4 (pas longue séquence récente -) : {g4}  ({neg_streak} fenêtres 12m négatives consécutives en fin)")

    # Focus 2025→2026H1
    print("\n--- FOCUS 2025 → 2026H1 (fenêtres 12m) ---")
    for r in df12.itertuples():
        if r.window.startswith(("2025", "2026")):
            print(f"  {r.window}: ΔEV={r.delta_exp:+.2f} | E_COMMON={r.e_common:.0f}$ E_ONLY={r.e_only:.0f}$ "
                  f"(E_ONLY part = {100*r.e_only/(abs(r.e_common)+abs(r.e_only)):.0f}%)")

    n_pass = sum([g1, g2, g3, g4])
    print(f"\nGATES PASSÉS : {n_pass}/4")
    if n_pass == 4:
        print("=> EV_TOP20 survit à la stabilité temporelle → CHALLENGER SÉRIEUX.")
    else:
        print("=> EV_TOP20 échoue : l'avantage est instable / limité à 2023 → SIGNAL HISTORIQUE NON STABLE.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df12.to_parquet(OUT, index=False)
    df18.to_parquet(str(OUT).replace(".parquet", "_18m.parquet"), index=False)
    print(f"\npersisted: {OUT} (+ _18m)")


if __name__ == "__main__":
    main()
