import pandas as pd
import numpy as np
from pathlib import Path

tr = pd.read_csv("artifacts/backtesting/b25_2025_rankw/trades.csv")
ts = tr[tr["exit_reason"] == "trailing_stop"].copy()
ts["is_loss"] = ts["return_pct"] < 0
ts["entry_date"] = pd.to_datetime(ts["entry_date"])
ts["exit_date"] = pd.to_datetime(ts["exit_date"])

# charger le cache OHLCV 2025 complet
cache = pd.read_parquet("artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet")
print("cache 2025 cols:", list(cache.columns)[:12], "rows:", len(cache))
print(cache.head(2).to_string())
