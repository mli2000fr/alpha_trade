import pandas as pd
from pathlib import Path

d = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8"]:
    p = d / r / "trade_audit_log.csv"
    df = pd.read_csv(p)
    print(f"=== {r} ===")
    print("  event_type counts:")
    print(df["event_type"].value_counts(dropna=False).to_string())
    # lignes avec pnl non-null
    trades = df[df["pnl"].notna()].copy()
    print(f"  lignes avec pnl non-null: {len(trades)}")
    if len(trades):
        print("  exit_reason counts:", trades["exit_reason"].value_counts(dropna=False).to_dict())
        print("  side counts:", trades["side"].value_counts(dropna=False).to_dict())
        print("  return_pct stats:\n", trades["return_pct"].describe().to_string())
        print("  holding_days stats:\n", trades["holding_days"].describe().to_string())
    print()
