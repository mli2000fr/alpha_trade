"""E6-C — Robustesse du bucket Y3 : RANK_TOP20 vs RANK_TOP10 (+ tranche 10-20%).

CONTEXTE (spec user 2026-08-20) : la branche EV est terminée (E6-B4 : EV = NO-GO,
ranking Y3 seul suffit). Il reste à départager la profondeur de sélection :
TOP20 vs TOP10. AUCUN autre seuil testé (pas de TOP5/15/25).

MÉTHODE :
- Même moteur (m8, coûts canoniques, exits gelés, LONG-only, Oracle O0, CatBoost Y3-LONG OOF).
- Fenêtres glissantes 12m (offset 3m) et 18m (offset 6m) — mêmes points de départ que B3.
- Par fenêtre : Return, PF, Sharpe, MaxDD, expectancy/trade, N trades, turnover.
  (Return/Sharpe/MaxDD issus de l'equity curve réelle tranchée sur la fenêtre ;
   trades = entrées dans la fenêtre.)
- DIAGNOSTIC CLÉ (candidat-level OOF) : tranche TOP 0-10% vs RANK 10-20%
  (score Y3 percentile). PF/expectancy/PnL/stabilité par semestre et rolling.
  TOP20 = TOP10 + tranche 10-20% → si 10-20% est durablement faible/négatif,
  TOP10 a une justification économique claire ; s'il est positif et diversifiant,
  TOP20 peut être préférable.

GATES (fixés AVANT de regarder les résultats) :
  G1 : expectancy(TOP10) >= expectancy(TOP20) dans majorité des fenêtres 12m
  G2 : expectancy(TOP10) >= expectancy(TOP20) dans majorité des fenêtres 18m
  G3 : pas de longue séquence temporelle où TOP10 < TOP20 (<= 2 fenêtres 12m
       consécutives négatives en fin)
  G4 : MaxDD(TOP10) pas structurellement pire (<= ~1.1× MaxDD TOP20 consolidé)
  G5 : avantage TOP10 pas limité à 2025/2026 (≥1 fenêtre 2023-2024 avec
       expectancy TOP10 >= TOP20) et pas dépendant de quelques gros trades
       (Top5 <= 50% du PnL)
  G6 (diagnostic tranche) : expectancy(tranche 0-10%) >= expectancy(tranche 10-20%)
       sur majorité des fenêtres → TOP10 économiquement justifié

VERDICT : si TOP10 passe les gates → architecture simple : Oracle O0 → pool Extreme
→ CatBoost Y3-LONG → TOP10 → moteur m8. Sinon TOP20 si sa tranche 10-20% apporte
réellement de la diversification.

Sortie : print + artifacts/models/oracle/e6_c_results.parquet
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

OUT = Path("artifacts/models/oracle/e6_c_results.parquet")
INITIAL_EQUITY = 100_000.0
COST_RT = 0.0016


def build_signals_y3(pool: pd.DataFrame, variant: str) -> pd.DataFrame:
    """Signaux ranking Y3 pur (sans colonnes EV — le moteur n'en a pas besoin)."""
    df = pool.copy()
    df["_score_rank_pct"] = df.groupby("date")["_proba_catboost"].rank(pct=True)
    if variant == "RANK_TOP20":
        df = df[df["_score_rank_pct"] >= 0.80]
    elif variant == "RANK_TOP10":
        df = df[df["_score_rank_pct"] >= 0.90]
    else:
        raise ValueError(f"variante non supportée: {variant}")
    sig = df[["date", "symbol", "rank", "score", "atr_pct_20"]].copy()
    sig = sig.rename(columns={"date": "trade_date"})
    sig["selected"] = True
    sig["side"] = "buy"
    return sig


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


def run_bt_full(sig: pd.DataFrame, pivots: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Retourne (equity_curve, closed_trades)."""
    res = make_engine().run(
        open_df=pivots["open"], close=pivots["close"],
        high=pivots["high"], low=pivots["low"],
        signals_df=sig, volume=pivots["volume"],
    )
    eq = res.equity_curve.copy()
    trades = res.closed_trades_df.copy()
    trades["entry_date"] = pd.to_datetime(trades["entry_date"]).dt.normalize()
    trades["exit_date"] = pd.to_datetime(trades["exit_date"]).dt.normalize()
    return eq, trades


def window_metrics_full(eq: pd.Series, trades: pd.DataFrame,
                        w_start: pd.Timestamp, w_end: pd.Timestamp) -> dict:
    """Métriques fenêtre : Return/Sharpe/MaxDD de l'equity tranchée + trades entrés."""
    eq_w = eq.loc[(eq.index >= w_start) & (eq.index <= w_end)]
    ret = float(eq_w.iloc[-1] / eq_w.iloc[0] - 1.0) * 100.0 if len(eq_w) > 1 else 0.0
    rets = eq_w.pct_change().dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252.0)) if len(rets) > 1 and rets.std() > 0 else 0.0
    dd = float(((eq_w / eq_w.cummax()) - 1.0).min() * 100.0) if len(eq_w) > 1 else 0.0

    t = trades[(trades["entry_date"] >= w_start) & (trades["entry_date"] <= w_end)]
    pnl = pd.to_numeric(t["pnl"], errors="coerce").fillna(0.0)
    n = len(pnl)
    gp = float(pnl[pnl > 0].sum()); gn = float(-pnl[pnl < 0].sum())
    pf = gp / gn if gn > 0 else float("inf")
    expect = float(pnl.mean()) if n else 0.0
    # Turnover : notionnel entré / equity moyenne / années
    avg_eq = float(eq_w.mean()) if len(eq_w) else INITIAL_EQUITY
    notional = float((pd.to_numeric(t.get("quantity", pd.Series(dtype=float)), errors="coerce").fillna(0) *
                      pd.to_numeric(t.get("entry_price", pd.Series(dtype=float)), errors="coerce").fillna(0)).sum()) if n else 0.0
    n_years = max((len(eq_w) / 252.0), 0.01)
    turnover = (notional / avg_eq) / n_years if avg_eq > 0 else 0.0
    return {
        "window": f"{w_start.date()}→{w_end.date()}",
        "n": n, "return_pct": ret, "pf": pf, "sharpe": sharpe, "max_dd_pct": dd,
        "expectancy": expect, "turnover": turnover, "pnl": float(pnl.sum()),
    }


def tranche_metrics(pool: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Tranches OOF TOP 0-10% vs RANK 10-20% (candidat-level, ret réalisé − coûts)."""
    df = pool.copy()
    df["_rank_pct"] = df.groupby("date")["_proba_catboost"].rank(pct=True)
    df["_net_ret"] = df["y3_long_ret"] - COST_RT
    df["_tranche"] = np.where(df["_rank_pct"] >= 0.90, "TOP0-10",
                              np.where((df["_rank_pct"] >= 0.80) & (df["_rank_pct"] < 0.90), "RANK10-20", None))

    # Par semestre
    df["semester"] = df["date"].dt.year.astype(str) + np.where(df["date"].dt.month <= 6, "H1", "H2")
    rows_sem = []
    for (tr, sem), sub in df[df["_tranche"].notna()].groupby(["_tranche", "semester"]):
        ret = sub["_net_ret"]
        gp = float(ret[ret > 0].sum()); gn = float(-ret[ret < 0].sum())
        rows_sem.append({
            "tranche": tr, "semester": sem, "n": len(sub), "pnl": float(ret.sum()),
            "pf": gp / gn if gn > 0 else float("inf"), "expectancy": float(ret.mean()),
        })
    sem_df = pd.DataFrame(rows_sem)

    # Par fenêtre rolling (12m)
    rows_win = []
    for tr in ("TOP0-10", "RANK10-20"):
        sub_all = df[df["_tranche"] == tr]
        for w_start, w_end in WINDOWS_12M:
            sub = sub_all[(sub_all["date"] >= w_start) & (sub_all["date"] <= w_end)]
            if sub.empty:
                continue
            ret = sub["_net_ret"]
            gp = float(ret[ret > 0].sum()); gn = float(-ret[ret < 0].sum())
            rows_win.append({
                "tranche": tr, "window": f"{w_start.date()}→{w_end.date()}",
                "n": len(sub), "pnl": float(ret.sum()),
                "pf": gp / gn if gn > 0 else float("inf"), "expectancy": float(ret.mean()),
            })
    win_df = pd.DataFrame(rows_win)
    return sem_df, win_df


def jackpot_top5(trades: pd.DataFrame) -> float:
    """Part du Top5 trades dans le PnL total (trades exécutés)."""
    pnl = pd.to_numeric(trades["pnl"], errors="coerce").fillna(0.0)
    total = float(pnl.sum())
    if total == 0:
        return float("nan")
    return float(pnl.sort_values(ascending=False).head(5).sum() / total)


def main() -> None:
    df, feature_columns = load_pool()
    pool = df[df["extreme_pool"]].copy().dropna(subset=["y3_long"])
    pool = pool[(pool["date"] >= pd.Timestamp(START)) & (pool["date"] <= pd.Timestamp(END))]
    symbols = sorted(pool["symbol"].unique())
    pivots = load_pivots(symbols)
    print(f"pool: {len(pool):,} | {pool['date'].min().date()} -> {pool['date'].max().date()} | {len(symbols)} syms")

    # Rejouer les deux buckets (une seule fois chacun)
    print("\n=== Rejeu moteur RANK_TOP20 / RANK_TOP10 ===", flush=True)
    eq20, tr20 = run_bt_full(build_signals_y3(pool, "RANK_TOP20"), pivots)
    eq10, tr10 = run_bt_full(build_signals_y3(pool, "RANK_TOP10"), pivots)
    print(f"  RANK_TOP20 : {len(tr20)} trades | PnL={pd.to_numeric(tr20['pnl'], errors='coerce').sum():.0f}$")
    print(f"  RANK_TOP10 : {len(tr10)} trades | PnL={pd.to_numeric(tr10['pnl'], errors='coerce').sum():.0f}$")

    # ── FENÊTRES 12m ──
    print("\n" + "=" * 140)
    print("FENÊTRES 12 MOIS GLISSANTS — RANK_TOP20 vs RANK_TOP10")
    print("=" * 140)
    rows = []
    for w_start, w_end in WINDOWS_12M:
        m20 = window_metrics_full(eq20, tr20, w_start, w_end)
        m10 = window_metrics_full(eq10, tr10, w_start, w_end)
        m20["bench"] = "TOP20"; m10["bench"] = "TOP10"
        delta = m10["expectancy"] - m20["expectancy"]
        m20["delta_exp"] = delta
        m10["delta_exp"] = delta
        rows.append(m20); rows.append(m10)
    df12 = pd.DataFrame(rows)
    print(f"  {'fenêtre':<24} {'bench':>6} {'n':>4} {'Ret%':>7} {'PF':>6} {'Sharpe':>7} {'MaxDD%':>8} {'expect$':>8} {'turnover':>9}")
    for r in df12.sort_values(["window", "bench"]).itertuples():
        print(f"  {r.window:<24} {r.bench:>6} {r.n:>4} {r.return_pct:>7.1f} {r.pf:>6.2f} {r.sharpe:>7.2f} "
              f"{r.max_dd_pct:>8.1f} {r.expectancy:>8.2f} {r.turnover:>9.1f}")

    # ── FENÊTRES 18m ──
    print("\n" + "=" * 140)
    print("FENÊTRES 18 MOIS GLISSANTS — RANK_TOP20 vs RANK_TOP10")
    print("=" * 140)
    rows18 = []
    for w_start, w_end in WINDOWS_18M:
        m20 = window_metrics_full(eq20, tr20, w_start, w_end)
        m10 = window_metrics_full(eq10, tr10, w_start, w_end)
        m20["bench"] = "TOP20"; m10["bench"] = "TOP10"
        delta = m10["expectancy"] - m20["expectancy"]
        m20["delta_exp"] = delta
        m10["delta_exp"] = delta
        rows18.append(m20); rows18.append(m10)
    df18 = pd.DataFrame(rows18)
    print(f"  {'fenêtre':<24} {'bench':>6} {'n':>4} {'Ret%':>7} {'PF':>6} {'Sharpe':>7} {'MaxDD%':>8} {'expect$':>8} {'turnover':>9}")
    for r in df18.sort_values(["window", "bench"]).itertuples():
        print(f"  {r.window:<24} {r.bench:>6} {r.n:>4} {r.return_pct:>7.1f} {r.pf:>6.2f} {r.sharpe:>7.2f} "
              f"{r.max_dd_pct:>8.1f} {r.expectancy:>8.2f} {r.turnover:>9.1f}")

    # ── DIAGNOSTIC TRANCHES 0-10% vs 10-20% ──
    print("\n" + "=" * 140)
    print("DIAGNOSTIC CLÉ : tranche TOP 0-10% vs RANK 10-20% (OOF, ret réalisé − coûts)")
    print("=" * 140)
    sem_t, win_t = tranche_metrics(pool)
    # Consolidé
    print("\n  CONSOLIDÉ par tranche :")
    for tr in ("TOP0-10", "RANK10-20"):
        sub = sem_t[sem_t["tranche"] == tr]
        print(f"    {tr:<10} n={sub['n'].sum():>6} PnL={sub['pnl'].sum():>9.0f} "
              f"expectancy={sub['expectancy'].mean():>7.3f}% sem+={(sub['expectancy']>0).sum()}/{len(sub)}")
    print("\n  PAR SEMESTRE :")
    print(f"  {'semester':<10} {'TOP0-10 n':>10} {'TOP0-10 exp':>12} {'TOP0-10 PF':>10} | "
          f"{'10-20 n':>8} {'10-20 exp':>10} {'10-20 PF':>9}")
    sems = sorted(sem_t["semester"].unique())
    for s in sems:
        t10 = sem_t[(sem_t["tranche"] == "TOP0-10") & (sem_t["semester"] == s)]
        t20 = sem_t[(sem_t["tranche"] == "RANK10-20") & (sem_t["semester"] == s)]
        t10e = f"{100*t10['expectancy'].iloc[0]:.2f}%" if len(t10) else "—"
        t10p = f"{t10['pf'].iloc[0]:.2f}" if len(t10) else "—"
        t20e = f"{100*t20['expectancy'].iloc[0]:.2f}%" if len(t20) else "—"
        t20p = f"{t20['pf'].iloc[0]:.2f}" if len(t20) else "—"
        print(f"  {s:<10} {t10['n'].iloc[0] if len(t10) else 0:>10} {t10e:>12} {t10p:>10} | "
              f"{t20['n'].iloc[0] if len(t20) else 0:>8} {t20e:>10} {t20p:>9}")
    print("\n  PAR FENÊTRE 12m (expectancy %) :")
    piv = win_t.pivot_table(index="window", columns="tranche", values="expectancy")
    piv["delta"] = (piv.get("TOP0-10", 0) - piv.get("RANK10-20", 0)) * 100
    print(f"  {'fenêtre':<24} {'TOP0-10%':>10} {'RANK10-20%':>12} {'Δ%':>8}")
    for w, r in piv.iterrows():
        print(f"  {w:<24} {100*r.get('TOP0-10', float('nan')):>9.2f}% {100*r.get('RANK10-20', float('nan')):>11.2f}% {r.get('delta', float('nan')):>8.2f}")

    # ── GATES ──
    print("\n" + "=" * 140)
    print("GATES (fixés avant de regarder les résultats)")
    print("=" * 140)
    # Δ expectancy TOP10−TOP20 par fenêtre
    d12 = df12[df12["bench"] == "TOP10"].set_index("window")["delta_exp"]
    d18 = df18[df18["bench"] == "TOP10"].set_index("window")["delta_exp"]
    g1 = bool((d12 >= 0).mean() >= 0.5) if len(d12) else False
    g2 = bool((d18 >= 0).mean() >= 0.5) if len(d18) else False
    # G3 : séquence négative consécutive en fin (12m)
    neg_streak = 0
    for v in reversed(d12.tolist()):
        if v < 0: neg_streak += 1
        else: break
    g3 = neg_streak <= 2
    # G4 : MaxDD consolidé TOP10 <= 1.1 × TOP20
    dd20 = float(((eq20 / eq20.cummax()) - 1.0).min())
    dd10 = float(((eq10 / eq10.cummax()) - 1.0).min())
    g4 = abs(dd10) <= 1.1 * abs(dd20) + 1e-9
    # G5 : ≥1 fenêtre 2023-2024 avec delta>=0 + jackpot
    wins_23_24 = [w for w in d12.index if w.startswith(("2023", "2024"))]
    pos_23_24 = sum(1 for w in wins_23_24 if d12.get(w, -1e18) >= 0)
    top5_10 = jackpot_top5(tr10)
    g5 = (pos_23_24 >= 1) and (not np.isnan(top5_10)) and (top5_10 <= 0.50)
    # G6 : tranche 0-10% expectancy >= 10-20% sur majorité des fenêtres 12m
    dv = piv["delta"].dropna()
    g6 = bool((dv >= 0).mean() >= 0.5) if len(dv) else False

    print(f"G1 (TOP10 expect >= TOP20, majorité 12m) : {g1}  ({(d12>=0).mean()*100:.0f}% des {len(d12)})")
    print(f"G2 (TOP10 expect >= TOP20, majorité 18m) : {g2}  ({(d18>=0).mean()*100:.0f}% des {len(d18)})")
    print(f"G3 (pas longue séquence récente inférieure) : {g3}  ({neg_streak} fen. 12m consécutives négatives en fin)")
    print(f"G4 (MaxDD TOP10 <= 1.1×TOP20)             : {g4}  ({abs(dd10)*100:.2f}% vs {abs(dd20)*100:.2f}%)")
    print(f"G5 (pas 2025/26-only + pas jackpot)       : {g5}  (2023-24: {pos_23_24}/{len(wins_23_24)}, Top5={100*top5_10:.1f}%)")
    print(f"G6 (tranche 0-10% >= 10-20%, majorité)    : {g6}  ({(dv>=0).mean()*100:.0f}% des {len(dv)} fenêtres)")

    n_pass = sum([g1, g2, g3, g4, g5, g6])
    print(f"\nGATES PASSÉS : {n_pass}/6")
    if g1 and g2 and g6 and n_pass >= 5:
        print("=> TOP10 = bucket robuste → architecture : Oracle O0 → Extreme → Y3-LONG → TOP10 → m8.")
    elif g6 and n_pass >= 4:
        print("=> TOP10 acceptable mais réserve sur certains gates ; TOP20 reste défendable si la tranche 10-20% diversifie.")
    else:
        print("=> TOP10 ne confirme pas ; TOP20 (tranche 10-20% positive/diversifiante) peut être préféré.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    df12.to_parquet(OUT, index=False)
    sem_t.to_parquet(str(OUT).replace(".parquet", "_tranches.parquet"), index=False)
    print(f"\npersisted: {OUT} (+ _tranches)")


if __name__ == "__main__":
    main()
