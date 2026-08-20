import pandas as pd
from pathlib import Path

ROOT = Path("artifacts/backtesting")
df = pd.read_csv(ROOT / "cmp_b25_h20_2025_prodparity_p23_m8" / "trade_audit_log.csv")
tr = df[df["pnl"].notna()].copy()
tr["entry_date"] = pd.to_datetime(tr["entry_date"])

# Cas MAT sell take_profit 18.2%
t = tr[(tr["symbol"] == "MAT") & (tr["side"] == "sell")].head(3)
for _, row in t.iterrows():
    print("=== MAT sell entry", row["entry_date"].date(), "entry_price", row["entry_price"])
    print("  TP:", row["replay_take_profit_price"], " init_stop:", row["replay_initial_stop_price"],
          " ts_pct:", row["replay_trailing_stop_pct"], " ret_officiel:", row["return_pct"], row["replay_exit_reason"])
    print("  exit:", row["replay_exit_date"], row["replay_exit_price"])

# cache MAT
cache = pd.read_parquet("artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
                        columns=["symbol", "trade_date", "open", "high", "low", "close"])
cache["trade_date"] = pd.to_datetime(cache["trade_date"])
cache["symbol"] = cache["symbol"].astype(str).str.upper()
mat = cache[cache["symbol"] == "MAT"].sort_values("trade_date")
print("\nMAT rows dans cache:", len(mat))
print(mat.head(3).to_string())
print(mat.tail(3).to_string())
