from pathlib import Path

for name in ["artifacts/backtesting/b25_2025_rankw",
             "artifacts/backtesting/b25_2025_rankw_sector",
             "artifacts/backtesting/b25_2025_equal",
             "artifacts/backtesting/b25_oos2026_ab_baseline"]:
    p = Path(name)
    print(f"=== {name} ===")
    if p.exists():
        for f in sorted(p.iterdir()):
            print("  ", f.name, "(dir)" if f.is_dir() else f.stat().st_size)
    else:
        print("  ABSENT")
    print()
