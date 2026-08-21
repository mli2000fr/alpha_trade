import pandas as pd

for p in ["artifacts/backtest_cache/85712967191d_ohlcv_2025-01-01_2026-06-20.parquet",
          "artifacts/backtest_cache/a4060dc97e3f_ohlcv_2025-01-02_2025-12-31.parquet",
          "artifacts/backtest_cache/2a7cecd22ad4_ohlcv_2026-01-02_2026-05-31.parquet"]:
    df = pd.read_parquet(p)
    print(f"=== {p.split('/')[-1]} ===")
    print(f"  rows={len(df):,}  cols={list(df.columns)}")
    d = pd.to_datetime(df['trade_date'] if 'trade_date' in df.columns else df['date'])
    print(f"  date: {d.min()} -> {d.max()}  syms={df['symbol'].nunique() if 'symbol' in df.columns else '?'}")
    print()
