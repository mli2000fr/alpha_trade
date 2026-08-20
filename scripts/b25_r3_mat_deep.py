import pandas as pd
from pathlib import Path

ROOT = Path("artifacts/backtesting")
df = pd.read_csv(ROOT / "cmp_b25_h20_2025_prodparity_p23_m8" / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()
tr["entry_date"] = pd.to_datetime(tr["entry_date"])
tr["replay_exit_date"] = pd.to_datetime(tr["replay_exit_date"], errors="coerce")

# MAT sell TP 18.1961
t = tr[(tr["symbol"] == "MAT") & (tr["side"] == "sell") & (tr["return_pct"] > 10)].iloc[0]
print("=== MAT sell take_profit ===")
for c in ["symbol", "side", "entry_date", "replay_exit_date", "entry_price", "signal_fill_price",
          "replay_take_profit_price", "replay_initial_stop_price", "replay_trailing_stop_pct",
          "replay_trailing_activation_price", "replay_exit_price", "return_pct", "replay_exit_reason",
          "watcher_transition_effective_date", "risk_per_share"]:
    if c in t.index:
        print(f"  {c} = {t[c]}")
print("  risk_per_share dans cols?", "risk_per_share" in t.index)

# OHLC MAT autour de la periode
cache = pd.read_parquet("artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
                        columns=["symbol", "trade_date", "open", "high", "low", "close"])
cache["trade_date"] = pd.to_datetime(cache["trade_date"])
cache["symbol"] = cache["symbol"].astype(str).str.upper()
mat = cache[cache["symbol"] == "MAT"].sort_values("trade_date")
mat = mat[(mat["trade_date"] >= "2025-02-12") & (mat["trade_date"] <= "2025-04-15")]
print("\n=== OHLC MAT 2025-02-12 -> 2025-04-15 ===")
print(mat.to_string(index=False))
