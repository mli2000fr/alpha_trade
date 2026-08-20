import pandas as pd
from pathlib import Path

d = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8"]:
    p = d / r / "trade_audit_log.csv"
    print(f"=== {r} ===")
    if not p.exists():
        print("  absent")
        continue
    df = pd.read_csv(p)
    print(f"  shape: {df.shape}")
    print(f"  cols: {list(df.columns)}")
    print()
    # afficher 3 lignes exemple
    print(df.head(3).to_string()[:3000])
    print()
    print("="*80)
