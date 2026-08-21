import json
from pathlib import Path

# 1. manifeste du benchmark OOS 2026
for name in ["artifacts/benchmarks/OOS2026_B25_P14_m8_v1/_MANIFEST.json",
             "artifacts/benchmarks/OOS2026_B25_P14_m8_v1/report.json"]:
    p = Path(name)
    print(f"=== {name} ===")
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        s = json.dumps(d, indent=1, default=str)
        print(s[:3000])
    else:
        print("  ABSENT")
    print()
