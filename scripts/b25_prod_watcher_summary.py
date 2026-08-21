import json
from pathlib import Path
import re

ROOT = Path("artifacts/backtesting")
r = "cmp_b25_h20_2026_prodparity_p23_m8"

# 1. phase5 watcher summary : y a-t-il des time_stop ?
for f in ["phase5_watcher_replay_summary.json", "phase5_watcher_replay_events.csv",
          "phase7_exit_lifecycle_replay_summary.json"]:
    p = ROOT / r / f
    print(f"=== {f} ===")
    if p.exists():
        txt = p.read_text(encoding="utf-8", errors="replace")
        if f.endswith(".json"):
            try:
                d = json.loads(txt)
                s = json.dumps(d, indent=1, default=str)
                # afficher tout (court)
                print(s[:2500])
            except Exception as e:
                print("  JSON err:", e, txt[:500])
        else:
            # chercher time_stop
            hits = [ln for ln in txt.splitlines() if "time" in ln.lower()]
            print("  lignes avec 'time':", len(hits))
            for h in hits[:15]:
                print("   ", h[:200])
    else:
        print("  absent")
    print()
