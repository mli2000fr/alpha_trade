import json
from pathlib import Path

# 1. params COMPLETS du run 2026 original (toutes les cles, pas de filtre)
d = Path("artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8/report.json")
j = json.loads(d.read_text(encoding="utf-8"))
p = j.get("params", {})
print("=== TOUTES les cles params (2026 original) ===")
for k in sorted(p.keys()):
    print(f"  {k} = {json.dumps(p[k], default=str)[:160]}")
print()
# 2. run_metadata
print("=== run_metadata ===")
print(json.dumps(j.get("run_metadata", {}), indent=1, default=str)[:1200])
