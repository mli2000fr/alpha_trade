import os, json
from pathlib import Path

d = Path("artifacts/backtesting")
for r in ["cmp_b25_h20_2025_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_p23_m8",
          "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8"]:
    p = d / r / "report.json"
    st = os.stat(p)
    import datetime
    ts = datetime.datetime.fromtimestamp(st.st_mtime)
    j = json.loads(p.read_text(encoding="utf-8"))
    meta = j.get("run_metadata", {})
    print(f"### {r}")
    print(f"  report mtime: {ts}  size: {st.st_size}")
    print(f"  run_metadata keys: {sorted(meta.keys()) if isinstance(meta, dict) else type(meta)}")
    if isinstance(meta, dict):
        for k in ["created_at", "started_at", "command", "argv", "args", "seed", "run_id", "fingerprint"]:
            if k in meta:
                print(f"    {k} = {json.dumps(meta[k], default=str)[:200]}")
print()

# defauts P14 dans le code
cfg = Path("execution_engine/config.py")
print("=== execution_engine/config.py (defauts P17/P14) ===")
if cfg.exists():
    txt = cfg.read_text(encoding="utf-8", errors="replace")
    for line in txt.splitlines():
        ls = line.strip()
        if any(k in ls for k in ["trailing_activation_r_multiple", "trailing_pct_long_override",
                                  "trailing_pct_short_override", "trailing_pct_override",
                                  "atr_risk_stop", "tp_atr", "tp_max"]):
            print("  ", ls[:140])
