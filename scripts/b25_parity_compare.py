import json
from pathlib import Path

d = Path("artifacts/backtesting")
runs = [
    "cmp_b25_h20_2025_prodparity_p23_m8",
    "cmp_b25_h20_2026_prodparity_p23_m8",
    "cmp_b25_h20_2026_prodparity_repro_h20cfg_m8",
]
for r in runs:
    p = d / r / "report.json"
    print(f"### {r}: exists={p.exists()}")
    if p.exists():
        j = json.loads(p.read_text(encoding="utf-8"))
        s = j.get("summary", {})
        print(f"   return {s.get('total_return_pct'):.2f}%  PF {s.get('profit_factor'):.3f}  DD {s.get('max_drawdown_pct'):.2f}%  trades {s.get('total_trades')}  L {s.get('long_trades')}/S {s.get('short_trades')}")
        print(f"   long_pnl {s.get('long_pnl_total'):.0f}  short_pnl {s.get('short_pnl_total'):.0f}  net {s.get('pnl_net'):.0f}")
print()

# Comparaison bit-for-bit des params (hors start/end)
p25 = json.loads((d/"cmp_b25_h20_2025_prodparity_p23_m8/report.json").read_text(encoding="utf-8")).get("params", {})
p26 = json.loads((d/"cmp_b25_h20_2026_prodparity_p23_m8/report.json").read_text(encoding="utf-8")).get("params", {})
p26r = json.loads((d/"cmp_b25_h20_2026_prodparity_repro_h20cfg_m8/report.json").read_text(encoding="utf-8")).get("params", {})

def diff(a, b, la, lb):
    out = []
    for k in sorted(set(a) | set(b)):
        if k in ("start", "end"):
            continue
        if a.get(k) != b.get(k):
            out.append((k, a.get(k), b.get(k)))
    return out

print("=== DIFF 2025 p23_m8 vs 2026 p23_m8 (hors start/end) ===")
for k, va, vb in diff(p25, p26, "2025", "2026"):
    print(f"  [{k}] 2025={json.dumps(va, default=str)[:150]}")
    print(f"         2026={json.dumps(vb, default=str)[:150]}")
print()

print("=== DIFF 2026 p23_m8 vs 2026 repro_h20cfg (hors start/end) ===")
for k, va, vb in diff(p26, p26r, "p23", "repro"):
    print(f"  [{k}] p23={json.dumps(va, default=str)[:150]}")
    print(f"         repro={json.dumps(vb, default=str)[:150]}")
print()

print("=== DIFF 2025 p23_m8 vs 2026 repro_h20cfg (hors start/end) ===")
for k, va, vb in diff(p25, p26r, "2025", "repro26"):
    print(f"  [{k}] 2025={json.dumps(va, default=str)[:150]}")
    print(f"         repro={json.dumps(vb, default=str)[:150]}")
print("(fin)")
