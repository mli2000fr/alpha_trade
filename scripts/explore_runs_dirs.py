from pathlib import Path

for name in ["artifacts/ihm_backtesting_runs", "artifacts/backtesting", "artifacts/campaigns", "artifacts/baselines", "artifacts/backtest_cache"]:
    p = Path(name)
    print(f"=== {name} ===")
    if p.exists():
        items = sorted(p.iterdir())
        print(f"  {len(items)} éléments")
        for f in items[:40]:
            print("  ", f.name, "(dir)" if f.is_dir() else f.stat().st_size)
    else:
        print("  ABSENT")
    print()
