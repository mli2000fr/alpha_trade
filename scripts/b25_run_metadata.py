import json
from pathlib import Path

d = Path("artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8")
print("=== fichiers du run ===")
for f in sorted(d.iterdir()):
    print("  ", f.name)
print()
for name in ["run_metadata.json", "_MANIFEST.json", "params.json"]:
    p = d / name
    print(f"=== {name} ===")
    if p.exists():
        txt = p.read_text(encoding="utf-8", errors="replace")
        print(txt[:3000])
    else:
        print("  absent")
    print()
