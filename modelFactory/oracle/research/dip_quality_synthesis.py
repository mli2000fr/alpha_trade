#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Audit final dip_quality (campagne Q0-Q3, 2026-08-27).

Verdict (NO_GO) : le score dip_quality est prédictif en coupe transversale
(corr≈0.13, spread top/bottom quintile ≈2.8pp sur Q0) mais dès qu'il REMPLACE
le rank ML dans la sélection (rank/top50/top25) il fait pire que la baseline :
substitution nette Q0->Q1/Q2/Q3 = -1317 / -1422 / -1559 (trades retirés meilleurs
que les ajoutés). Il n'a été ni déployé en ranking, filtre, sizing ni veto.

Métriques calculées depuis trades.csv (pipeline phase3->phase7) — PAS report.json
(le report.json Q1/Q2/Q3 est byte-identique : summary/equity issus du pipeline
legacy closed_trades_df qui ne consomme pas la politique dip_quality).
"""

"""Temp — synthèse finale fiable basée sur trades.csv (pipeline), pas report.json."""
import sys
sys.path.insert(0, "F:/projets")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from pathlib import Path

import pandas as pd
import numpy as np

ROOT = Path("artifacts/backtesting")
INITIAL = 4000.0

def metrics_from_trades(df):
    df = df.copy()
    df["entry_date"] = pd.to_datetime(df["signal_date"], errors="coerce").fillna(
        pd.to_datetime(df["trade_date"], errors="coerce"))
    df["exit_date"] = pd.to_datetime(df["exit_date"], errors="coerce")
    closed = df[df["trade_status"] == "closed"].copy()
    pnl = closed["pnl"].astype(float)
    ret = closed["return_pct"].astype(float)
    wins = closed[ret > 0]
    losses = closed[ret <= 0]
    gp = wins["pnl"].sum() if len(wins) else 0.0
    gl = -losses["pnl"].sum() if len(losses) else 0.0
    holding = (closed["exit_date"] - closed["entry_date"]).dt.days
    # courbe PnL cumulée (approximation simple, comparable entre runs)
    closed = closed.sort_values("exit_date")
    cum = closed["pnl"].astype(float).cumsum()
    total_ret = pnl.sum() / INITIAL * 100.0
    # Sharpe approximatif sur rendements quotidiens du portefeuille PnL cumulé
    daily = closed.groupby("exit_date")["pnl"].sum()
    if len(daily) > 1:
        r = (INITIAL + daily.cumsum()) / (INITIAL + daily.cumsum().shift(1).fillna(0)) - 1
        sharpe = r.mean() / (r.std(ddof=1) + 1e-12) * np.sqrt(252) if r.std(ddof=1) > 0 else 0
    else:
        sharpe = 0.0
    return {
        "n_signaux": len(df),
        "n_closed": len(closed),
        "n_open": len(df[df["trade_status"] == "open"]),
        "win_rate_pct": (len(wins) / len(closed) * 100) if len(closed) else 0,
        "pnl_net": pnl.sum(),
        "total_return_pct": total_ret,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "avg_ret_pct": ret.mean() if len(ret) else 0,
        "avg_holding_j": holding.mean() if len(holding) else 0,
        "avg_entrees_jour": len(closed) / 723 if len(closed) else 0,
        "entry_cost_total": df["entry_cost"].astype(float).sum(),
        "notional_total": (df["quantity"].astype(float) * df["entry_price"].astype(float)).sum(),
        "sharpe_approx": sharpe,
    }

print("=" * 70)
print("MÉTRIQUES depuis trades.csv (pipeline phase3->phase7) — fiable, différencié")
print("=" * 70)
hdr = f"{'métrique':<20}" + "".join(f"{r:>14}" for r in ["Q0", "Q1", "Q2", "Q3"])
print(hdr)
rows = {}
for r in ["q0", "q1", "q2", "q3"]:
    df = pd.read_csv(ROOT / r / "trades.csv")
    rows[r] = metrics_from_trades(df)

metrics_keys = ["n_signaux", "n_closed", "n_open", "win_rate_pct", "pnl_net",
                "total_return_pct", "profit_factor", "avg_ret_pct",
                "avg_holding_j", "avg_entrees_jour", "entry_cost_total",
                "notional_total", "sharpe_approx"]
for k in metrics_keys:
    line = f"{k:<20}"
    for r in ["q0", "q1", "q2", "q3"]:
        v = rows[r][k]
        if isinstance(v, float):
            line += f"{v:>14,.2f}"
        else:
            line += f"{v:>14,}"
    print(line)

# Attribution complète Q0 -> Q1/Q2/Q3 (par (date,symbol))
print("\n" + "=" * 70)
print("ATTRIBUTION par substitution (trades.csv, par signal_date+symbol)")
print("=" * 70)
q0 = pd.read_csv(ROOT / "q0" / "trades.csv")
q0["key"] = q0["signal_date"].astype(str) + "|" + q0["symbol"]
q0set = set(q0["key"])
for r in ["q1", "q2", "q3"]:
    df = pd.read_csv(ROOT / r / "trades.csv")
    df["key"] = df["signal_date"].astype(str) + "|" + df["symbol"]
    added = df[~df["key"].isin(q0set)]
    removed = q0[~q0["key"].isin(set(df["key"]))]
    pa = added["pnl"].sum()
    pr = removed["pnl"].sum()
    print(f"\n{r}: ajoutés={len(added)} (PnL {pa:,.0f}, win {100*(added['pnl']>0).mean():.1f}%) | "
          f"retirés={len(removed)} (PnL {pr:,.0f}, win {100*(removed['pnl']>0).mean():.1f}%) | "
          f"substitution nette={pa-pr:,.0f}")

# Jours contraints (jours où le nombre de candidats dip_quality dépasse les slots ?)
print("\n" + "=" * 70)
print("PARTIE C — jours contraints & qualité des trades (dip_quality)")
print("=" * 70)
dq = pd.read_csv("artifacts/dip_quality_static/dip_quality_oof_predictions.csv")
dq["key"] = pd.to_datetime(dq["signal_date"]).dt.strftime("%Y-%m-%d") + "|" + dq["symbol"]
dqmap = dict(zip(dq["key"], dq["dip_quality_score"]))
for r in ["q0", "q1", "q2", "q3"]:
    df = pd.read_csv(ROOT / r / "trades.csv")
    df["key"] = pd.to_datetime(df["signal_date"]).dt.strftime("%Y-%m-%d") + "|" + df["symbol"]
    df["dq"] = df["key"].map(dqmap)
    has = df[df["dq"].notna()]
    # corrélation dq vs return
    if len(has) > 5:
        corr = np.corrcoef(has["dq"].astype(float), has["return_pct"].astype(float))[0, 1]
    else:
        corr = float("nan")
    # top/bottom decile dq -> return
    q = has["dq"].astype(float)
    hi = has[q >= q.quantile(0.8)]
    lo = has[q <= q.quantile(0.2)]
    print(f"{r}: avec dq={len(has)} | corr(dq,ret)={corr:.3f} | "
          f"dq top20% ret moyen={hi['return_pct'].mean():.2f}% (n={len(hi)}) | "
          f"dq bottom20% ret moyen={lo['return_pct'].mean():.2f}% (n={len(lo)})")
