import json
from pathlib import Path
import datetime, os

d = Path("artifacts/backtesting")
# runs avec report.json, tries par mtime, montrer date + params tp
runs = []
for f in d.iterdir():
    rp = f / "report.json"
    if rp.exists():
        try:
            j = json.loads(rp.read_text(encoding="utf-8"))
            p = j.get("params", {})
            s = j.get("summary", {})
            runs.append({
                "name": f.name, "mtime": datetime.datetime.fromtimestamp(os.stat(rp).st_mtime),
                "tp_atr": p.get("tp_atr_multiple"), "tp_max": p.get("tp_max_pct"),
                "atr_risk": p.get("atr_risk_stop_multiple"),
                "trail_long": p.get("trailing_pct_long_override"),
                "ret": s.get("total_return_pct"), "trades": s.get("total_trades"),
                "start": p.get("start"), "end": p.get("end"),
            })
        except Exception:
            pass
runs.sort(key=lambda x: x["mtime"])
print("=== runs avec params TP (post-fix attendu = tp_atr present) ===")
print(f"{'date':19} {'run':42} {'tp_atr':>7} {'tp_max':>7} {'atr_risk':>8} {'ret%':>8} {'N':>4}")
for r in runs:
    if r["mtime"] >= datetime.datetime(2026, 8, 17, 22, 10):
        ret_s = f"{r['ret']:.2f}" if r['ret'] is not None else ""
        print(f"{r['mtime'].strftime('%Y-%m-%d %H:%M'):19} {r['name']:42} "
              f"{str(r['tp_atr']):>7} {str(r['tp_max']):>7} {str(r['atr_risk']):>8} "
              f"{ret_s:>8} {str(r['trades'] or ''):>4}")
print()
print("=== tous les runs >= 2026-08-17 (chronologie du fix) ===")
for r in runs:
    if r["mtime"] >= datetime.datetime(2026, 8, 17, 12, 0):
        print(f"{r['mtime'].strftime('%Y-%m-%d %H:%M'):19} {r['name']:46} tp_atr={str(r['tp_atr']):>6} tp_max={str(r['tp_max']):>6} ret={r['ret']}")
