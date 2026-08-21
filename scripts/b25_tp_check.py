"""TP check : distribution du replay_take_profit_price vs entrée.
Production P14 : TP = min(ATR*3, 7%). Si le TP rejoué dépasse 7% -> divergence.
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
    tr["tp_dist_pct"] = np.where(
        tr["side"] == "buy",
        (tr["replay_take_profit_price"] / tr["entry_price"] - 1) * 100,
        (1 - tr["replay_take_profit_price"] / tr["entry_price"]) * 100,
    )
    print(f"\n{'='*100}\n### {year} : TP rejoué vs entrée (N={len(tr)})\n{'='*100}")
    print("stats distance TP (%):")
    print(tr["tp_dist_pct"].describe().to_string())
    over = tr[tr["tp_dist_pct"] > 7.01]
    print(f"\nTP > 7.01% (cap production P14 min(ATR*3,7%)) : {len(over)} / {len(tr)}")
    if len(over):
        print(over[["symbol", "side", "entry_price", "replay_take_profit_price", "tp_dist_pct",
                    "replay_initial_stop_price"]].sort_values("tp_dist_pct", ascending=False).head(15).to_string(index=False))
    # sous 7% mais sous 3% ?
    print(f"\nTP < 3% : {(tr['tp_dist_pct'] < 3).sum()}   |   TP 3-7% : {((tr['tp_dist_pct']>=3)&(tr['tp_dist_pct']<=7)).sum()}")
