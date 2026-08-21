import json
from pathlib import Path

p = Path("artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8/report.json")
print("exists:", p.exists())
if p.exists():
    d = json.loads(p.read_text(encoding="utf-8"))
    params = d.get("params", {})
    print("=== params prodparity 2026 ===")
    print(json.dumps(params, indent=1, default=str)[:5000])
else:
    # lister les dossiers cmp_*
    for f in sorted(Path("artifacts/backtesting").iterdir()):
        if f.name.startswith("cmp"):
            print("  ", f.name)
