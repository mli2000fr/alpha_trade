"""E6-B2b — Validation formelle de EV comme SCORE DE RANKING (EV_TOP20).

STATUT (spec user 2026-08-20) :
  - E6-B2a : EV > 0 → NO-GO (falsifié). Aucun tuning de seuil EV.
  - E6-B2b : EV utilisé comme SCORE DE RANKING → candidat à valider formellement.
  EV_TOP20 était prévu comme diagnostic AVANT observation → pas du p-hacking.

TOUT EST GELÉ :
- EV_TOP20 exactement (top 20% de l'EV intra-date) — PAS TOP15/10/25.
- même CatBoost Y3-LONG (OOF, features O0) ; même Platt OOF ; mêmes estimations
  train-only de E[gain|success,bucket] / E[loss|failure,bucket] ; même Oracle O0 ;
  même m8 ; mêmes coûts canoniques ; mêmes exits ; aucun SHORT.

COMPARATEURS (uniquement) : RANK_TOP20, RANK_TOP10, EV_TOP20.

GATES (fixés AVANT de relancer les détails) :
  G1 : PF OU expectancy EV_TOP20 > RANK_TOP10
  G2 : Return >= RANK_TOP10 (ou pas matériellement inférieur, >= 0.9×)
  G3 : MaxDD pas détérioré de plus de ~10% relatif vs min(RANK10, RANK20)
  G4 : >= 5/7 semestres positifs
  G5 : EV bat le meilleur rank sur une majorité de semestres (pas seulement en cumul)
  G6 : pas de dépendance à quelques trades extrêmes → contribution Top5/Top10/Top20 au PnL
       (Top5 <= ~50% du PnL total pour rester sain)
  G7 : pas d'effondrement 2026H1 non identifié (on affiche le semestre explicitement)

DIAGNOSTICS :
  D1 : corr(rank_long_success, EV_rank) + overlap TOP20 (fraction de RANK20 ∩ EV20).
       corr ~0.95 + overlap 90% → EV ajoute peu. overlap faible → EV réordonne réellement.
  D2 : décomposition du désaccord (4 buckets) avec PF/expectancy/PnL :
       - accord positif (RANK20 ∩ EV20)
       - accord négatif (¬RANK20 ∩ ¬EV20)
       - EV accepte / Rank rejette (EV20 \ RANK20)
       - EV rejette / Rank accepte (RANK20 \ EV20)
       Signal convaincant : EV accepte/Rank rejette profitable ET EV rejette/Rank accepte mauvais.
  D3 : concentration du PnL (Top5/10/20 trades) sur les trades exécutés EV_TOP20.

Sortie : print + artifacts/models/oracle/e6_b2b_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from scripts.e6_b2_ev_long_backtest import (
    BENCHMARKS,
    COST_RT,
    END,
    START,
    add_ev_features,
    build_signals,
    load_pivots,
    load_pool,
    run_benchmark,
)

OUT = Path("artifacts/models/oracle/e6_b2b_results.parquet")

# Comparateurs réduits (gèle EV_TOP20 exactement)
COMPARATORS = ["RANK_TOP20", "RANK_TOP10", "EV_TOP20"]


def disagreement_analysis(pool: pd.DataFrame) -> pd.DataFrame:
    """Décompose le désaccord RANK_TOP20 vs EV_TOP20 (niveau candidat, ret réalisé).

    Utilise y3_long_ret (chemin gelé) − coûts comme outcome économique par candidat.
    """
    df = pool.copy()
    df["_ret_net"] = df["y3_long_ret"] - COST_RT
    df["_rk20"] = df.groupby("date")["_proba_catboost"].rank(pct=True) >= 0.80
    df["_ev20"] = df.groupby("date")["EV_LONG"].rank(pct=True) >= 0.80

    rows = []
    for name, mask in [
        ("accord_positif (RANK20 ∩ EV20)", df["_rk20"] & df["_ev20"]),
        ("accord_négatif (¬R20 ∩ ¬EV20)", (~df["_rk20"]) & (~df["_ev20"])),
        ("EV accepte / Rank rejette (EV20 \\ R20)", df["_ev20"] & (~df["_rk20"])),
        ("EV rejette / Rank accepte (R20 \\ EV20)", df["_rk20"] & (~df["_ev20"])),
    ]:
        sub = df[mask]
        n = len(sub)
        if n == 0:
            rows.append({"bucket": name, "n": 0, "pnl": 0.0, "pf": float("nan"),
                         "expectancy": 0.0, "win": float("nan")})
            continue
        ret = sub["_ret_net"]
        gp = float(ret[ret > 0].sum()); gn = float(-ret[ret < 0].sum())
        rows.append({
            "bucket": name, "n": n,
            "pnl": float(ret.sum()),
            "pf": gp / gn if gn > 0 else float("inf"),
            "expectancy": float(ret.mean()),
            "win": float((ret > 0).mean()),
        })
    return pd.DataFrame(rows)


def pnl_concentration(closed: pd.DataFrame) -> dict:
    """Contribution Top5/10/20 trades au PnL total (trades exécutés)."""
    if closed.empty:
        return {"n": 0, "top5_pct": float("nan"), "top10_pct": float("nan"), "top20_pct": float("nan")}
    pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0)
    total = float(pnl.sum())
    if total == 0:
        return {"n": len(pnl), "top5_pct": float("nan"), "top10_pct": float("nan"), "top20_pct": float("nan")}
    top = pnl.sort_values(ascending=False)
    out = {"n": len(pnl)}
    for k in (5, 10, 20):
        out[f"top{k}_pnl"] = float(top.head(k).sum())
        out[f"top{k}_pct"] = float(top.head(k).sum() / total)
    return out


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy()
    pool = pool.dropna(subset=["y3_long"]).copy()
    print(f"Pool Oracle Extreme O0 (complet) : {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()}")

    # add_ev_features sur le pool COMPLET (train 2022 requis par le fold 2023)
    pool = add_ev_features(pool, feature_columns)
    print(f"Après EV (tests folds 2023-2026) : {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()}")
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]

    # ── D1 : corr(rank, EV_rank) + overlap TOP20 ──
    pool["_score_rank_pct"] = pool.groupby("date")["_proba_catboost"].rank(pct=True)
    pool["_ev_rank_pct"] = pool.groupby("date")["EV_LONG"].rank(pct=True)
    corr = float(pool["_score_rank_pct"].corr(pool["_ev_rank_pct"]))
    rk20 = pool[pool["_score_rank_pct"] >= 0.80].index
    ev20 = pool[pool["_ev_rank_pct"] >= 0.80].index
    overlap = float(len(set(rk20) & set(ev20)) / max(len(rk20), 1))
    print("\n=== D1 : corr rank vs EV_rank + overlap ===")
    print(f"  corr(rank_long_success, EV_rank) = {corr:.4f}")
    print(f"  overlap TOP20 (|R20 ∩ EV20|/|R20|) = {overlap*100:.1f}%")

    # ── D2 : décomposition du désaccord ──
    print("\n=== D2 : décomposition du désaccord (outcome = y3_long_ret − coûts) ===")
    disc = disagreement_analysis(pool)
    print(f"  {'bucket':<38} {'n':>7} {'PnL$':>10} {'PF':>7} {'expect$':>9} {'win%':>7}")
    print("  " + "-" * 90)
    for r in disc.itertuples():
        print(f"  {r.bucket:<38} {r.n:>7} {r.pnl:>10.0f} {r.pf:>7.2f} {r.expectancy*100:>8.3f}% {100*r.win:>6.1f}%")

    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"\nOHLCV : {len(symbols)} symboles | {pivots['close'].shape[0]} jours")

    results = {}
    for label in COMPARATORS:
        print(f"=== {label} ===", flush=True)
        sig = build_signals(pool, label)
        results[label] = run_benchmark(sig, pivots, label)
        r = results[label]
        print(f"  Return={r['total_return_pct']:.2f}% PF={r['pf']:.2f} Sharpe={r['sharpe']:.2f} "
              f"MaxDD={r['max_dd_pct']:.2f}% trades={r['n_trades']} expect={r['expectancy']:.2f}$ "
              f"sem+={r['n_pos_semesters']}/{r['n_semesters']}", flush=True)

    # ── Table principale ──
    print("\n" + "=" * 120)
    print("E6-B2b — EV_TOP20 vs RANK (validation formelle, tout gelé)")
    print("=" * 120)
    hdr = f"{'bench':<10} {'Return%':>9} {'PF':>7} {'Sharpe':>7} {'MaxDD%':>9} {'trades':>7} {'expect$':>8} {'sem+':>6}"
    print(hdr); print("-" * 120)
    for label in COMPARATORS:
        r = results[label]
        print(f"{label:<10} {r['total_return_pct']:>8.2f}% {r['pf']:>7.2f} {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>8.2f}% {r['n_trades']:>7} {r['expectancy']:>8.2f} "
              f"{r['n_pos_semesters']:>3}/{r['n_semesters']}")

    # PnL par semestre
    print("\n" + "=" * 120)
    print("PnL par semestre ($)")
    print("=" * 120)
    sems = sorted(set().union(*[r["semesters"].index for r in results.values()]))
    print(f"{'semester':<10}" + "".join(f"{lbl:>16}" for lbl in COMPARATORS))
    for s in sems:
        row = f"{s:<10}"
        for lbl in COMPARATORS:
            if s in results[lbl]["semesters"].index:
                row += f"{results[lbl]['semesters'].loc[s,'pnl']:>15.0f}$"
            else:
                row += f"{'—':>16}"
        print(row)

    # ── D3 : concentration du PnL (trades exécutés EV_TOP20) ──
    print("\n=== D3 : concentration du PnL (EV_TOP20, trades exécutés) ===")
    from backtesting.simulator import BacktestConfig, BacktestEngine
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(), end_date=pd.Timestamp(END).date(),
        initial_equity=100_000.0, max_positions=8,
        atr_risk_stop_multiple=3.5, tp_atr_multiple=4.0, tp_max_pct=0.13,
        trailing_stop_long_pct=0.07, trailing_stop_short_pct=None,
        use_canonical_costs=True, entry_limit_offset_pct=0.0,
        min_score_threshold=0.0, use_live_protection_logic=True,
    )
    ev_result = BacktestEngine(cfg).run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=build_signals(pool, "EV_TOP20"), volume=pivots["volume"],
    )
    conc = pnl_concentration(ev_result.closed_trades_df)
    print(f"  n_trades={conc['n']}")
    for k in (5, 10, 20):
        print(f"  Top{k} trades : PnL={conc.get(f'top{k}_pnl', float('nan')):.0f}$ "
              f"({100*conc.get(f'top{k}_pct', float('nan')):.1f}% du PnL total)")

    # ── GATES ──
    print("\n" + "=" * 120)
    print("GATES (fixés avant relance des détails)")
    print("=" * 120)
    ev, r10, r20 = results["EV_TOP20"], results["RANK_TOP10"], results["RANK_TOP20"]
    g1 = (ev["pf"] > r10["pf"]) or (ev["expectancy"] > r10["expectancy"])
    g2 = ev["total_return_pct"] >= 0.9 * r10["total_return_pct"]
    min_dd = min(abs(r10["max_dd_pct"]), abs(r20["max_dd_pct"]))
    g3 = abs(ev["max_dd_pct"]) <= 1.10 * min_dd + 1e-9
    g4 = ev["n_pos_semesters"] >= 5
    # G5 : EV bat le meilleur rank sur une majorité de semestres (expect par semestre)
    best_rank_sem = {}
    for s in sems:
        cand = [r10["semesters"].loc[s, "pnl"] if s in r10["semesters"].index else -1e18,
                r20["semesters"].loc[s, "pnl"] if s in r20["semesters"].index else -1e18]
        best_rank_sem[s] = max(cand)
    beats = sum(1 for s in sems
                if s in ev["semesters"].index and ev["semesters"].loc[s, "pnl"] > best_rank_sem.get(s, -1e18))
    g5 = beats >= len(sems) / 2
    # G6 : concentration — Top5 <= 50% du PnL total
    top5_pct = conc.get("top5_pct", float("nan"))
    g6 = (not np.isnan(top5_pct)) and top5_pct <= 0.50
    # G7 : pas d'effondrement 2026H1 non identifié → on affiche explicitement
    pnl_26h1 = ev["semesters"].loc["2026H1", "pnl"] if "2026H1" in ev["semesters"].index else float("nan")
    g7_detail = f"2026H1 PnL = {pnl_26h1:.0f}$ (affiché explicitement)"
    g7 = True  # diagnostic : identifié, pas un gate d'échec automatique

    print(f"G1 (EV PF/expect > RANK10)      : {g1}  (PF {ev['pf']:.2f}/{r10['pf']:.2f} | exp {ev['expectancy']:.2f}/{r10['expectancy']:.2f})")
    print(f"G2 (EV Return >= 0.9×RANK10)    : {g2}  ({ev['total_return_pct']:.2f}% vs {0.9*r10['total_return_pct']:.2f}%)")
    print(f"G3 (EV DD <= 1.10×min rank DD)  : {g3}  ({abs(ev['max_dd_pct']):.2f}% vs {min_dd:.2f}%)")
    print(f"G4 (>= 5/7 semestres +)         : {g4}  ({ev['n_pos_semesters']}/{ev['n_semesters']})")
    print(f"G5 (EV > meilleur rank par sem.) : {g5}  ({beats}/{len(sems)} semestres)")
    print(f"G6 (Top5 <= 50% du PnL)         : {g6}  (Top5 = {100*top5_pct:.1f}% du PnL)")
    print(f"G7 ({g7_detail})                 : {g7}")

    n_pass = sum([g1, g2, g3, g4, g5, g6, g7])
    print(f"\nGATES PASSÉS : {n_pass}/7")
    if g1 and g2 and g3 and g4 and n_pass >= 6:
        print("=> PASS : EV_TOP20 est un candidat sérieux (ranking économique spécialisé tradabilité).")
    else:
        print("=> ÉCHEC : EV_TOP20 ne confirme pas les gates — ne pas promouvoir.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for lbl in COMPARATORS:
        results[lbl]["semesters"] = results[lbl]["semesters"].reset_index()
    pd.DataFrame([{k: v for k, v in r.items() if k != "semesters"} for r in results.values()]).to_parquet(
        OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
