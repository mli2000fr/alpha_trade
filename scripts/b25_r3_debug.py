import pandas as pd
import numpy as np
from pathlib import Path

ROOT = Path("artifacts/backtesting")
CACHE = {
    "cmp_b25_h20_2025_prodparity_p23_m8": "artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
    "cmp_b25_h20_2026_prodparity_p23_m8": "artifacts/backtest_cache/2a7cecd22ad4_ohlcv_2026-01-02_2026-05-31.parquet",
}

df = pd.read_csv(ROOT / "cmp_b25_h20_2025_prodparity_p23_m8" / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()
print("N trades 2025:", len(tr))
print("cols replay_take_profit null:", tr["replay_take_profit_price"].isna().sum(), "/", len(tr))
print("cols replay_initial_stop null:", tr["replay_initial_stop_price"].isna().sum())
print("cols replay_trailing_stop_pct null:", tr["replay_trailing_stop_pct"].isna().sum())
print("cols watcher_effective null:", tr["watcher_transition_effective_date"].isna().sum())

cache = pd.read_parquet("artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
                        columns=["symbol", "trade_date", "open", "high", "low", "close"])
cache["trade_date"] = pd.to_datetime(cache["trade_date"])
cache["symbol"] = cache["symbol"].astype(str).str.upper()
print("cache rows:", len(cache), "syms:", cache["symbol"].nunique())
# test un trade
t = tr.iloc[0]
rows = cache[(cache["symbol"] == t["symbol"]) & (cache["trade_date"] > pd.to_datetime(t["entry_date"]))].sort_values("trade_date")
print("trade 0:", t["symbol"], t["side"], t["entry_date"], "rows dispo:", len(rows))
print(t[["entry_price", "replay_take_profit_price", "replay_initial_stop_price", "replay_trailing_stop_pct", "return_pct", "replay_exit_reason"]].to_dict())
