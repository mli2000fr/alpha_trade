import pandas as pd

base = "artifacts/benchmarks/OOS2026_B25_P14_m8_v1/"
tr = pd.read_csv(base + "trades.csv")
print("=== trades.csv ===")
print("n trades:", len(tr))
print("cols:", list(tr.columns))
print()
print(tr.head(10).to_string())
