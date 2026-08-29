#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T0 vs T1 — dip_quality tiebreaker (campagne Q4, 2026-08-28).

Compare la sélection baseline (Q0 = artifacts/backtesting/q0, politique none) à
la sélection tiebreaker (T1 = artifacts/backtesting/q_tie, politique tiebreak)
sur le vrai moteur PROD-parity (2023-2025).

Métriques calculées depuis trades.csv (pipeline phase3->phase7) — PAS report.json
(le report.json est issu du pipeline legacy closed_trades_df, byte-identique pour
les runs dip_quality, donc non discriminant).

Critère de GO (strict) :
  - n substitutions faible ;
  - PnL marginal des substitutions > 0 ;
  - PF >= baseline ; Sharpe >= baseline ; Return >= baseline ou quasi identique ;
  - aucune hausse significative du DD.
Si plat ou négatif → fermer définitivement dip_quality.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, "F:/projets")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path("artifacts/backtesting")
INITIAL = 4000.0


def metrics_from_trades(df: pd.DataFrame) -> dict:
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
    daily = closed.groupby(closed["exit_date"])["pnl"].sum()
    sharpe = 0.0
    if len(daily) > 1 and daily.std(ddof=1) > 0:
        r = (INITIAL + daily.cumsum()) / (INITIAL + daily.cumsum().shift(1).fillna(0)) - 1
        sharpe = r.mean() / r.std(ddof=1) * np.sqrt(252)
    return {
        "n_signaux": len(df), "n_closed": len(closed), "n_open": len(df[df["trade_status"] == "open"]),
        "win_rate_pct": (len(wins) / len(closed) * 100) if len(closed) else 0,
        "pnl_net": pnl.sum(),
        "total_return_pct": pnl.sum() / INITIAL * 100.0,
        "profit_factor": (gp / gl) if gl > 0 else float("inf"),
        "avg_ret_pct": ret.mean() if len(ret) else 0,
        "avg_holding_j": holding.mean() if len(holding) else 0,
        "avg_entrees_jour": len(closed) / 723 if len(closed) else 0,
        "sharpe_approx": sharpe,
    }


def main() -> None:
    q0 = pd.read_csv(ROOT / "q0" / "trades.csv")
    t1 = pd.read_csv(ROOT / "q_tie" / "trades.csv")

    print("=" * 66)
    print("T0 (baseline none)  vs  T1 (tiebreak) — 2023-2025 PROD-parity")
    print("=" * 66)
    m0, m1 = metrics_from_trades(q0), metrics_from_trades(t1)
    keys = ["n_signaux", "n_closed", "n_open", "win_rate_pct", "pnl_net",
            "total_return_pct", "profit_factor", "avg_ret_pct", "avg_holding_j",
            "avg_entrees_jour", "sharpe_approx"]
    print(f"{'métrique':<20}{'T0':>14}{'T1':>14}")
    for k in keys:
        print(f"{k:<20}{m0[k]:>14,.2f}{m1[k]:>14,.2f}")

    # Substitutions (par signal_date+symbol)
    q0 = q0.copy(); t1 = t1.copy()
    q0["key"] = pd.to_datetime(q0["signal_date"]).dt.strftime("%Y-%m-%d") + "|" + q0["symbol"]
    t1["key"] = pd.to_datetime(t1["signal_date"]).dt.strftime("%Y-%m-%d") + "|" + t1["symbol"]
    k0, k1 = set(q0["key"]), set(t1["key"])
    added = t1[~t1["key"].isin(k0)]
    removed = q0[~q0["key"].isin(k1)]
    pa = added["pnl"].sum(); pr = removed["pnl"].sum()
    print("\n--- Substitutions T0 -> T1 ---")
    print(f"ajoutés={len(added)} (PnL {pa:,.0f}, win {100*(added['pnl']>0).mean():.1f}%)")
    print(f"retirés={len(removed)} (PnL {pr:,.0f}, win {100*(removed['pnl']>0).mean():.1f}%)")
    print(f"substitution nette = {pa-pr:,.0f}")

    print("\n--- Critères GO (strict) ---")
    print(f"PnL net T1-T0 = {m1['pnl_net']-m0['pnl_net']:,.2f}  (doit être > 0)")
    print(f"PF  T1 vs T0  = {m1['profit_factor']:.3f} vs {m0['profit_factor']:.3f}  (T1 >= T0 ?)")
    print(f"Shp T1 vs T0  = {m1['sharpe_approx']:.3f} vs {m0['sharpe_approx']:.3f}  (T1 >= T0 ?)")
    print(f"Ret T1 vs T0  = {m1['total_return_pct']:.2f}% vs {m0['total_return_pct']:.2f}%  (T1 >= T0 ?)")
    print(f"n substitutions = {len(added)+len(removed)}")


if __name__ == "__main__":
    main()
