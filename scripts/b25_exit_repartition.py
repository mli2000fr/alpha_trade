import pandas as pd
from pathlib import Path

d = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8"]:
    p = d / r / "phase7_exit_lifecycle_replay.csv"
    print(f"=== {r} ===")
    if not p.exists():
        print("  absent")
        continue
    df = pd.read_csv(p)
    print(f"  shape: {df.shape}")
    print(f"  cols: {list(df.columns)}")
    # répartition par type d'événement / exit
    for c in df.columns:
        if df[c].dtype == object:
            vc = df[c].value_counts(dropna=False).head(12)
            print(f"\n  col[{c}] value_counts:")
            for k, v in vc.items():
                print(f"    {k}: {v}")
    print()
