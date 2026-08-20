import pandas as pd

# inspecter trades 2025 + colonnes exit_reason / side
tr25 = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
print("=== trades 2025 ===")
print("n:", len(tr25))
print("exit_reason:", tr25["exit_reason"].value_counts().to_dict())
print("side:", tr25["side"].value_counts().to_dict())
print("cols:", list(tr25.columns))
print()

# trades 2026
tr26 = pd.read_csv("artifacts/benchmarks/OOS2026_B25_P14_m8_v1/trades.csv")
print("=== trades 2026 ===")
print("n:", len(tr26))
print("exit_reason:", tr26["exit_reason"].value_counts().to_dict())
print("side:", tr26["side"].value_counts().to_dict())
print()
print("2025 cols same as 2026?", list(tr25.columns) == list(tr26.columns))
