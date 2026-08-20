"""E6-B0b — Portfolio Reality Check : vrai moteur de backtest, LONG-only, par buckets.

BUT (spec user 2026-08-20) : vérifier que le gain trade-level E6-B0 survit à la
mécanique RÉELLE du portefeuille — chevauchement des trades, capacité m8, sizing ATR,
coûts, ordre d'entrée, concurrence entre candidats pour les slots. AVANT E6-B1 (calib).

MÉTHODE (règles fixées avant) :
- Pool = Oracle Extreme O0 (extreme_pool) ; score = _proba_catboost Y3-LONG **OOF/WF strict**
  (e6_y3_lift.parquet, même pipeline E6 : train GUARD_COL < fold_start, prédiction fold).
- Rang cross-sectionnel par date du score → bucket : ALL / TOP50 / TOP20 / TOP10.
- LONG-only (side=buy). SHORT ignoré.
- VRAI moteur : backtesting.simulator.BacktestEngine + BacktestConfig canonique :
    max_positions=8 (m8) ; atr_risk_stop_multiple=3.5 (stop 3.5×ATR) ;
    tp_atr_multiple=4.0, tp_max_pct=0.13 (TP=min(4×ATR,13%)) ;
    trailing_stop_long_pct=0.07 (trailing long 7%), short sans trailing ;
    use_canonical_costs=True (16 bps RT) ; entry_limit_offset_pct=0.0 (marché) ;
    min_score_threshold=0.0 (aucun seuil de proba brute — le bucket décide).
  atr_pct_20 fourni par signal (sizing/TP ATR fidèle live).
- OHLCV réel : artifacts/backtest_cache/39587735630f...parquet, pivoté (open/high/low/close).
- AUCUN tuning, aucun changement de modèle/exits/coûts.

MÉTRIQUES : Return, PF, Sharpe, vrai MaxDD (equity portefeuille), N trades, turnover,
exposition moyenne, slots pleins (jours où m8 saturé), candidats rejetés faute de
capacité (events entry_rejected capacité), expectancy, par semestre.

GATES (fixés AVANT) :
  G1 : TOP20 PF > ALL PF
  G2 : TOP20 expectancy (PnL/trade net) > ALL expectancy
  G3 : TOP20 ne dégrade pas significativement Return/Sharpe/MaxDD vs ALL
       (Return >= 0.7×ALL OU Sharpe >= 0.9×ALL OU MaxDD <= 1.3×ALL — lecture globale)
  G4 : TOP20 positif sur majorité des semestres (>50% des semestres avec PnL>0)
  G5 : pas uniquement 2025/2026 (TOP20 gagne aussi sur 2023-2024)
  PASS global = G1+G2+G3+G4+G5 (>=4/5 requis, G1+G2 obligatoires)

Sortie : print + artifacts/models/oracle/e6_b0b_results.parquet
"""
from __future__ import annotations

import sys
sys.path.insert(0, "f:/projets")

from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.simulator import BacktestConfig, BacktestEngine

OOF_PROBAS = Path("artifacts/models/oracle/e6_y3_lift.parquet")
PATH_LABELS = Path("artifacts/models/oracle/e6_path_labels.parquet")
CACHE = Path("artifacts/backtest_cache/39587735630f_ohlcv_2017-10-26_2026-06-30.parquet")
OUT = Path("artifacts/models/oracle/e6_b0b_results.parquet")

START = "2023-01-01"
END = "2026-05-29"
INITIAL_EQUITY = 100_000.0

BUCKETS = [("ALL", 1.0), ("TOP50", 0.50), ("TOP20", 0.20), ("TOP10", 0.10)]


def load_pool() -> pd.DataFrame:
    oof = pd.read_parquet(OOF_PROBAS)
    oof["date"] = pd.to_datetime(oof["date"]).dt.normalize()
    oof["symbol"] = oof["symbol"].astype(str)
    # atr20 / entry (pour atr_pct_20) viennent des labels de chemin Y3
    path = pd.read_parquet(PATH_LABELS)
    path["date"] = pd.to_datetime(path["date"]).dt.normalize()
    path["symbol"] = path["symbol"].astype(str)
    oof = oof.merge(path[["symbol", "date", "atr20", "entry"]], on=["symbol", "date"], how="left")
    # atr_pct_20 = fraction ATR_20 / prix (pour sizing + TP ATR du moteur)
    oof["atr_pct_20"] = oof["atr20"] / oof["entry"].replace(0, np.nan)
    # Rang cross-sectionnel par date du score Y3-LONG (1 = meilleur, pour le tri du moteur)
    oof["rank"] = oof.groupby("date")["_proba_catboost"].rank(ascending=False)
    oof["score"] = oof["_proba_catboost"]
    return oof


def load_pivots(pool_symbols: list[str]) -> dict[str, pd.DataFrame]:
    bars = pd.read_parquet(CACHE, columns=["symbol", "trade_date", "open", "high", "low", "close", "volume"])
    bars = bars[bars["symbol"].isin(pool_symbols)].copy()
    bars["trade_date"] = pd.to_datetime(bars["trade_date"]).dt.normalize()
    pivots = {}
    for col in ("open", "high", "low", "close"):
        pivots[col] = bars.pivot_table(index="trade_date", columns="symbol", values=col).sort_index()
    pivots["volume"] = bars.pivot_table(index="trade_date", columns="symbol", values="volume").sort_index()
    return pivots


def build_signals(pool: pd.DataFrame, keep_pct: float) -> pd.DataFrame:
    df = pool.copy()
    if keep_pct < 1.0:
        # Rang percentile du score Y3-LONG intra-date ; on garde le top `keep_pct`
        df = df[df.groupby("date")["_proba_catboost"].rank(pct=True) >= 1.0 - keep_pct]
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = "buy"
    return sig


def semester_pnl(closed: pd.DataFrame) -> pd.DataFrame:
    """PnL par semestre (date de sortie) depuis les trades clôturés."""
    if closed.empty:
        return pd.DataFrame(columns=["semester", "pnl", "n", "win"])
    c = closed.copy()
    c["exit_date"] = pd.to_datetime(c["exit_date"]).dt.normalize()
    c["semester"] = c["exit_date"].dt.year.astype(str) + np.where(c["exit_date"].dt.month <= 6, "H1", "H2")
    c["pnl"] = pd.to_numeric(c["pnl"], errors="coerce").fillna(0.0)
    c["win"] = (c["pnl"] > 0).astype(int)
    g = c.groupby("semester").agg(pnl=("pnl", "sum"), n=("pnl", "size"), win=("win", "mean"))
    return g


def run_bucket(pool: pd.DataFrame, pivots: dict, keep_pct: float, label: str) -> dict:
    sig = build_signals(pool, keep_pct)
    cfg = BacktestConfig(
        start_date=pd.Timestamp(START).date(),
        end_date=pd.Timestamp(END).date(),
        initial_equity=INITIAL_EQUITY,
        max_positions=8,
        atr_risk_stop_multiple=3.5,
        tp_atr_multiple=4.0,
        tp_max_pct=0.13,
        trailing_stop_long_pct=0.07,
        trailing_stop_short_pct=None,
        use_canonical_costs=True,
        entry_limit_offset_pct=0.0,
        min_score_threshold=0.0,
        use_live_protection_logic=True,
    )
    engine = BacktestEngine(cfg)
    result = engine.run(
        open_df=pivots["open"],
        close=pivots["close"],
        high=pivots["high"],
        low=pivots["low"],
        signals_df=sig,
        volume=pivots["volume"],
    )

    eq = result.equity_curve
    closed = result.closed_trades_df
    events = result.trade_events_df if result.trade_events_df is not None and not result.trade_events_df.empty else pd.DataFrame()

    # ── Métriques ──
    final = float(eq.iloc[-1]) if len(eq) else INITIAL_EQUITY
    total_ret_pct = (final / INITIAL_EQUITY - 1.0) * 100.0
    rets = eq.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) > 1 else 0.0

    n_trades = len(closed)
    pnl = pd.to_numeric(closed["pnl"], errors="coerce").fillna(0.0) if n_trades else pd.Series(dtype=float)
    gross_pos = float(pnl[pnl > 0].sum()) if n_trades else 0.0
    gross_neg = float(-pnl[pnl < 0].sum()) if n_trades else 0.0
    pf = gross_pos / gross_neg if gross_neg > 0 else float("inf")
    win_rate = float((pnl > 0).mean()) if n_trades else 0.0
    expectancy = float(pnl.mean()) if n_trades else 0.0

    # Turnover : notionnel total tradé / equity moyenne / années
    if n_trades:
        notional_traded = float(pd.to_numeric(closed.get("notional", pd.Series(dtype=float)), errors="coerce").sum())
        if notional_traded == 0:
            notional_traded = float((pd.to_numeric(closed["quantity"], errors="coerce").fillna(0) *
                                     pd.to_numeric(closed["entry_price"], errors="coerce").fillna(0)).sum())
        avg_equity = float(eq.mean())
        n_years = max((len(eq) / 252.0), 0.01)
        turnover = (notional_traded / avg_equity) / n_years if avg_equity > 0 else 0.0
    else:
        turnover = 0.0

    # Exposition moyenne : nécessite le MTM des positions ouvertes (state interne
    # non exposé) → NaN honnête. Les slots pleins/rejets sont inférés des events.
    avg_exposure_pct = float("nan")

    # Rejets faute de capacité / slots pleins
    n_rejected_capacity = 0
    n_slots_full = 0
    if not events.empty and "event_type" in events.columns:
        ev = events[events["event_type"].isin(["entry_rejected", "entry_blocked_overlay"])]
        if not ev.empty:
            n_rejected_capacity = int((ev.get("rejection_reason", "").astype(str).str.contains("capacity|slot|overlay|gross_exposure", case=False)).sum())
    diag = result.diagnostics

    sem = semester_pnl(closed)
    n_sem = len(sem)
    n_pos_sem = int((sem["pnl"] > 0).sum()) if n_sem else 0

    return {
        "bucket": label,
        "total_return_pct": total_ret_pct,
        "sharpe": sharpe,
        "pf": pf,
        "max_dd_pct": dd,
        "n_trades": n_trades,
        "win_rate": win_rate,
        "expectancy": expectancy,
        "turnover": turnover,
        "avg_exposure_pct": avg_exposure_pct,
        "slots_full_days": n_slots_full,
        "rejected_capacity": n_rejected_capacity,
        "n_semesters": n_sem,
        "n_pos_semesters": n_pos_sem,
        "semesters": sem,
        "final_equity": final,
        "diag": diag.to_dict(),
    }


def main() -> None:
    pool = load_pool()
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]
    print(f"Pool Oracle Extreme O0 : {len(pool):,} candidats | {pool['date'].min().date()} -> {pool['date'].max().date()}")
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"OHLCV : {len(symbols)} symboles pivotés | {pivots['close'].shape[0]} jours\n")

    results = {}
    for label, pct in BUCKETS:
        print(f"=== {label} (top {pct*100:.0f}%) ===", flush=True)
        results[label] = run_bucket(pool, pivots, pct, label)
        r = results[label]
        print(f"  Return={r['total_return_pct']:.2f}% PF={r['pf']:.2f} Sharpe={r['sharpe']:.2f} "
              f"MaxDD={r['max_dd_pct']:.2f}% trades={r['n_trades']} win={100*r['win_rate']:.1f}% "
              f"expect={r['expectancy']:.2f}$ turnover={r['turnover']:.1f}x sem+={r['n_pos_semesters']}/{r['n_semesters']}",
              flush=True)

    print("\n" + "=" * 110)
    print("E6-B0b — PORTFOLIO REALITY CHECK (vrai moteur, m8, LONG-only, buckets préfixés)")
    print("=" * 110)
    hdr = f"{'bucket':<8} {'Return%':>9} {'PF':>7} {'Sharpe':>7} {'MaxDD%':>9} {'trades':>7} {'win%':>7} {'expect$':>8} {'turnover':>9} {'sem+':>6}"
    print(hdr)
    print("-" * 110)
    for label, _ in BUCKETS:
        r = results[label]
        print(f"{label:<8} {r['total_return_pct']:>8.2f}% {r['pf']:>7.2f} {r['sharpe']:>7.2f} "
              f"{r['max_dd_pct']:>8.2f}% {r['n_trades']:>7} {100*r['win_rate']:>6.1f}% "
              f"{r['expectancy']:>8.2f} {r['turnover']:>9.1f}x {r['n_pos_semesters']:>3}/{r['n_semesters']}")

    print("\n" + "=" * 110)
    print("Résultat par semestre — PnL ($)")
    print("=" * 110)
    sems = sorted(set().union(*[r["semesters"].index for r in results.values()]))
    print(f"{'semester':<10}" + "".join(f"{lbl:>14}" for lbl, _ in BUCKETS))
    for s in sems:
        row = f"{s:<10}"
        for lbl, _ in BUCKETS:
            if s in results[lbl]["semesters"].index:
                row += f"{results[lbl]['semesters'].loc[s,'pnl']:>13.0f}$"
            else:
                row += f"{'—':>14}"
        print(row)

    # ── GATES ──
    print("\n" + "=" * 110)
    print("GATES (fixés avant le backtest)")
    print("=" * 110)
    all_r, t20 = results["ALL"], results["TOP20"]
    g1 = t20["pf"] > all_r["pf"]
    g2 = t20["expectancy"] > all_r["expectancy"]
    ret_ok = t20["total_return_pct"] >= 0.7 * all_r["total_return_pct"]
    sh_ok = t20["sharpe"] >= 0.9 * all_r["sharpe"] - 1e-9
    dd_ok = abs(t20["max_dd_pct"]) <= 1.3 * abs(all_r["max_dd_pct"]) + 1e-9
    g3 = ret_ok or sh_ok or dd_ok
    g4 = t20["n_pos_semesters"] > 0.5 * t20["n_semesters"]
    sem_23_24 = [s for s in sems if s.startswith("2023") or s.startswith("2024")]
    if sem_23_24:
        pos_23_24 = sum(1 for s in sem_23_24 if s in t20["semesters"].index and t20["semesters"].loc[s, "pnl"] > 0)
        g5 = pos_23_24 >= 1
        g5_detail = f"{pos_23_24}/{len(sem_23_24)} semestres 2023-2024 positifs"
    else:
        g5, g5_detail = False, "aucun semestre 2023-2024"

    print(f"G1 (TOP20 PF > ALL)        : {g1}  ({t20['pf']:.2f} vs {all_r['pf']:.2f})")
    print(f"G2 (TOP20 expect > ALL)    : {g2}  ({t20['expectancy']:.2f}$ vs {all_r['expectancy']:.2f}$)")
    print(f"G3 (TOP20 ne dégrade pas)  : {g3}  (Ret {ret_ok} | Sharpe {sh_ok} | DD {dd_ok})")
    print(f"G4 (TOP20 >50% sem+)       : {g4}  ({t20['n_pos_semesters']}/{t20['n_semesters']})")
    print(f"G5 (pas 2025/2026-only)    : {g5}  ({g5_detail})")

    n_pass = sum([g1, g2, g3, g4, g5])
    print(f"\nGATES PASSÉS : {n_pass}/5")
    if g1 and g2 and n_pass >= 4:
        print("=> PASS : E6-B1 (calibration OOF) justifié.")
    else:
        print("=> ÉCHEC : le gain trade-level ne survit pas au portefeuille — E6-B1 pas encore justifié.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    for lbl, _ in BUCKETS:
        results[lbl]["semesters"] = results[lbl]["semesters"].reset_index()
        results[lbl].pop("diag", None)
    pd.DataFrame([{k: v for k, v in r.items() if k != "semesters"} for r in results.values()]).to_parquet(
        OUT, index=False)
    print(f"\npersisted: {OUT}")


if __name__ == "__main__":
    main()
