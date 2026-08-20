import json
from pathlib import Path

d = Path("artifacts/backtesting")

def load(r):
    return json.loads((d / r / "report.json").read_text(encoding="utf-8")).get("params", {})

p25 = load("cmp_b25_h20_2025_prodparity_p23_m8")
p26 = load("cmp_b25_h20_2026_prodparity_p23_m8")
p26r = load("cmp_b25_h20_2026_prodparity_repro_h20cfg_m8")

# Nettoyer les phases: garder seulement la config (enabled, mode + sous-clés non-statistiques)
EXEC_KEYS = {"risk_bridge", "execution_bridge", "execution_tca", "execution_replay",
             "protection_replay", "watcher_replay", "exit_lifecycle_replay"}

def clean(p):
    q = {}
    for k, v in p.items():
        if k in ("phase2", "phase3", "phase4", "phase5", "phase7"):
            vv = {sk: sv for sk, sv in v.items() if sk not in EXEC_KEYS}
            q[k] = vv
        elif k in ("start", "end", "phase2", "phase3", "phase4", "phase5", "phase7"):
            q[k] = v
        else:
            q[k] = v
    return q

c25, c26, c26r = clean(p25), clean(p26), clean(p26r)

def diff(a, b, la, lb):
    out = []
    for k in sorted(set(a) | set(b)):
        if k in ("start", "end"):
            continue
        if a.get(k) != b.get(k):
            out.append((k, a.get(k), b.get(k)))
    return out

print("=== CONFIG-ONLY DIFF 2025 vs 2026 p23_m8 ===")
dl = diff(c25, c26, "2025", "2026")
if not dl:
    print("  AUCUNE DIFFERENCE DE CONFIG -> production parity OK")
for k, va, vb in dl:
    print(f"  [{k}] 2025={json.dumps(va, default=str)[:200]}")
    print(f"         2026={json.dumps(vb, default=str)[:200]}")
print()

print("=== CONFIG-ONLY DIFF 2026 p23_m8 vs repro_h20cfg ===")
dl = diff(c26, c26r, "p23", "repro")
if not dl:
    print("  AUCUNE DIFFERENCE DE CONFIG -> repro OK")
for k, va, vb in dl:
    print(f"  [{k}] p23={json.dumps(va, default=str)[:200]}")
    print(f"       repro={json.dumps(vb, default=str)[:200]}")
