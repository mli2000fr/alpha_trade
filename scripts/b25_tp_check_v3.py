"""TP check v3 : confirmer la theorie max(12%, 2R) vs TP ATR min(3*ATR, 7%).
Le replay_take_profit_price doit correspondre au fallback max(12%, 2R) si bug present.
2R = entry +/- 2*risk_per_share ; risk_per_share = |entry - initial_stop|.
"""
import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8"]:
    year = "2025" if "2025" in r else "2026"
    df = pd.read_csv(ROOT / r / "trade_audit_log.csv")
    tr = df[df["pnl"].notna()].copy()
    tr["risk_ps"] = (tr["entry_price"] - tr["replay_initial_stop_price"]).abs()
    is_buy = tr["side"] == "buy"
    # TP fallback : max(12% fixe, 2R)
    tr["tp_12"] = tr["entry_price"] * np.where(is_buy, 1.12, 0.88)
    tr["tp_2r"] = tr["entry_price"] + np.where(is_buy, 2 * tr["risk_ps"], -2 * tr["risk_ps"])
    tr["tp_legacy"] = np.where(is_buy,
                               tr[["tp_12", "tp_2r"]].max(axis=1),
                               tr[["tp_12", "tp_2r"]].min(axis=1))
    tr["err_legacy"] = (tr["replay_take_profit_price"] - tr["tp_legacy"]).abs() / tr["entry_price"]
    tr["err_12"] = (tr["replay_take_profit_price"] - tr["tp_12"]).abs() / tr["entry_price"]
    tr["err_2r"] = (tr["replay_take_profit_price"] - tr["tp_2r"]).abs() / tr["entry_price"]

    print(f"\n### {year} : TP rejoué vs hypothèses (N={len(tr)})")
    print(f"  match fallback max(12%,2R)  (err<1%): {(tr['err_legacy']<0.01).sum()}/{len(tr)}  median err={tr['err_legacy'].median()*100:.2f}%")
    print(f"  match TP 12% fixe           (err<1%): {(tr['err_12']<0.01).sum()}/{len(tr)}  median err={tr['err_12'].median()*100:.2f}%")
    print(f"  match TP 2R                 (err<1%): {(tr['err_2r']<0.01).sum()}/{len(tr)}  median err={tr['err_2r'].median()*100:.2f}%")
    print("\n  3 exemples :")
    ex = tr.head(3)[["symbol", "side", "entry_price", "replay_take_profit_price",
                     "tp_12", "tp_2r", "tp_legacy", "replay_initial_stop_price"]]
    print(ex.to_string(index=False))
