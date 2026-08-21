import json
from pathlib import Path

for name in ["ihm2526_p14_atrfix", "ihm2526_p14_h20risk", "oos2026_p14_h20risk",
             "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8"]:
    rp = Path("artifacts/backtesting") / name / "report.json"
    if not rp.exists():
        print(f"### {name}: absent")
        continue
    j = json.loads(rp.read_text(encoding="utf-8"))
    p = j.get("params", {})
    meta = j.get("run_metadata", {})
    print(f"\n### {name}")
    print(f"  git_commit: {meta.get('git_commit_sha')}  dirty={meta.get('git_dirty')}  gen={meta.get('generated_at_utc')}")
    print(f"  engine_mode: {p.get('engine_mode')}  start={p.get('start')} end={p.get('end')}")
    for k in sorted(p.keys()):
        if any(s in k for s in ["tp_atr", "tp_max", "atr_risk", "trailing_pct_long", "best_horizon", "horizon", "atr_trailing"]):
            print(f"    {k} = {p[k]}")
