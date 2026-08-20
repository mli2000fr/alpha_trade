"""Diagnostic churn/TP — baseline post-fix.
1. Churn : rotation, durée, taille trades, turnover vs ancien.
2. Structure L/S par année (2025 SHORT = -12.3k : pourquoi ?).
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
RUNS = [
    ("2025 BUGGÉ", "cmp_b25_h20_2025_prodparity_p23_m8"),
    ("2025 POST-FIX", "cmp_b25_h20_2025_postfix_tp_m8"),
    ("2026 BUGGÉ", "cmp_b25_h20_2026_prodparity_p23_m8"),
    ("2026 POST-FIX", "cmp_b25_h20_2026_postfix_tp_m8"),
]

def load_trades(name):
    tal = ROOT / name / "trade_audit_log.csv"
    df = pd.read_csv(tal)
    tr = df[df["pnl"].notna()].copy()
    tr["entry_date"] = pd.to_datetime(tr["entry_date"])
    tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")
    tr["holding_days"] = (tr["replay_exit_date"] - tr["entry_date"]).dt.days
    return tr

print("=" * 110)
print("DIAGNOSTIC CHURN — rotation / durée / taille (buggé vs post-fix)")
print("=" * 110)
for label, name in RUNS:
    tr = load_trades(name)
    print(f"\n### {label} : N={len(tr)}")
    print(f"  durée (j): mean={tr['holding_days'].mean():.1f}  med={tr['holding_days'].median():.1f}  "
          f"p25={tr['holding_days'].quantile(0.25):.0f}  p75={tr['holding_days'].quantile(0.75):.0f}")
    print(f"  durée<=1j: {(tr['holding_days']<=1).mean()*100:.0f}%   <=3j: {(tr['holding_days']<=3).mean()*100:.0f}%   "
          f"<=5j: {(tr['holding_days']<=5).mean()*100:.0f}%   >=20j: {(tr['holding_days']>=20).mean()*100:.0f}%")
    print(f"  entry_price: mean={tr['entry_price'].mean():.2f}  med={tr['entry_price'].median():.2f}")
    print(f"  qty: mean={tr['quantity'].mean():.1f}  med={tr['quantity'].median():.1f}" if 'quantity' in tr.columns else "")
    print(f"  exits: {tr['replay_exit_reason'].value_counts().to_dict()}")
    print(f"  TP distance: mean={(tr['replay_take_profit_price']/tr['entry_price']-1).where(tr['side']=='buy', 1-tr['replay_take_profit_price']/tr['entry_price']).mean()*100:.1f}%")

print("\n" + "=" * 110)
print("STRUCTURE L/S PAR ANNÉE (post-fix)")
print("=" * 110)
for label, name in [("2025 POST-FIX", "cmp_b25_h20_2025_postfix_tp_m8"),
                    ("2026 POST-FIX", "cmp_b25_h20_2026_postfix_tp_m8")]:
    tr = load_trades(name)
    print(f"\n### {label}")
    for side, lab in [("buy", "LONG "), ("sell", "SHORT")]:
        sub = tr[tr["side"] == side]
        if len(sub) == 0:
            continue
        print(f"  {lab}: N={len(sub)}  PnL={sub['pnl'].sum():>9.0f}  WR={(sub['pnl']>0).mean()*100:.1f}%  "
              f"mean_ret={sub['return_pct'].mean():.2f}%  med_ret={sub['return_pct'].median():.2f}%")
        print(f"      exits: {sub['replay_exit_reason'].value_counts().to_dict()}")
        print(f"      durée moy: {sub['holding_days'].mean():.1f}j")
    # shorts perdants 2025
    if "2025" in label:
        sh = tr[tr["side"] == "sell"]
        print(f"  SHORT 2025 — pires: ")
        w = sh.nsmallest(8, "pnl")[["symbol", "entry_date", "replay_exit_date", "pnl", "return_pct", "replay_exit_reason"]]
        print(w.to_string(index=False))
