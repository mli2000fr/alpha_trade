import json
from pathlib import Path

p = Path("artifacts/backtesting/cmp_b25_h20_2026_prodparity_p23_m8/report.json")
d = json.loads(p.read_text(encoding="utf-8"))
params = d.get("params", {})

keys = sorted(params.keys())
print("=== N params:", len(keys))
for k in keys:
    v = params[k]
    if k in ("phase2", "phase3", "phase4", "phase5", "phase7", "risk_overlay", "microstructure", "time_stop", "execution_costs"):
        print(f"\n### {k} ###")
        print(json.dumps(v, indent=1, default=str)[:1800])
    else:
        print(f"{k} = {json.dumps(v, default=str)[:120]}")
