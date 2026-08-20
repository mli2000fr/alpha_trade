from pathlib import Path

c = Path("artifacts/backtest_cache")
for f in sorted(c.glob("*ohlcv*")):
    print(f.name, f.stat().st_size)
