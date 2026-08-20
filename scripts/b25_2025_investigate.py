import pandas as pd
import numpy as np

tr = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
print("=== B25 OOS 2025 : vue d'ensemble ===")
print("n trades:", len(tr))
print("cols:", list(tr.columns))
print()
print("side:", tr["side"].value_counts().to_dict())
print("exit_reason:", tr["exit_reason"].value_counts().to_dict())
print("exit_source:", tr.get("exit_source", pd.Series(dtype=str)).value_counts().to_dict())
print("trade_status:", tr["trade_status"].value_counts().to_dict())

tr["is_win"] = tr["return_pct"] > 0
tr["is_loss"] = tr["return_pct"] < 0
print("\nwin rate:", tr["is_win"].mean()*100)
print("return_pct describe:", tr["return_pct"].describe().to_dict())
print("\npertes totales pnl:", tr.loc[tr["is_loss"], "pnl"].sum())
print("gains total pnl:", tr.loc[tr["is_win"], "pnl"].sum())

# par side
for side in ["buy", "sell"]:
    sub = tr[tr["side"] == side]
    print(f"\n--- {side} (n={len(sub)}) ---")
    print("  win:", sub["is_win"].mean()*100)
    print("  return moy:", sub["return_pct"].mean())
    print("  pnl sum:", sub["pnl"].sum())
    print("  exit_reason:", sub["exit_reason"].value_counts().to_dict())
