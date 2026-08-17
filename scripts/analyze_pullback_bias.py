# -*- coding: utf-8 -*-
"""Analyse du biais pullback : comparaison avec/sans pullback (2026-08-17)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts" / "backtesting"

RUNS = ["pb_ctl_2026", "pb0_2026", "ihm2526_ctl", "ihm2526_pb0"]


def get(n):
    p = BASE / n / "report.json"
    if not p.exists():
        return None
    return json.load(open(p, encoding="utf-8"))["summary"]


lines = []
w = lines.append
w("=" * 88)
w("MESURE DU BIAIS PULLBACK (entry_limit_offset_pct 0.01 vs 0)")
w("=" * 88)
hdr = f"{'run':<14}{'offset':>7}{'ret':>9}{'DD':>8}{'PF':>7}{'trades':>7}{'L':>4}{'S':>4}{'win':>7}"
w(hdr)
w("-" * 88)
for n in RUNS:
    s = get(n)
    if s is None:
        w(f"{n:<14}  PAS DE RAPPORT")
        continue
    off = "0.01" if "ctl" in n else "0"
    w(f"{n:<14}{off:>7}{s['total_return_pct']:>8.2f}%{s['max_drawdown_pct']:>7.2f}%"
      f"{s['profit_factor']:>7.3f}{s['total_trades']:>7}{s['long_trades']:>4}"
      f"{s['short_trades']:>4}{s['win_rate_pct']:>6.1f}%")

# Impact
w("")
pairs = [("2026 pile gelée", "pb_ctl_2026", "pb0_2026"),
         ("2025-2026 TP12/TS7", "ihm2526_ctl", "ihm2526_pb0")]
for label, a, b in pairs:
    sa, sb = get(a), get(b)
    if sa and sb:
        d = sa["total_return_pct"] - sb["total_return_pct"]
        w(f"IMPACT PULLBACK {label} : {sa['total_return_pct']:.2f}% → {sb['total_return_pct']:.2f}% = -{d:.2f} pts")

text = "\n".join(lines)
(ROOT / "logs" / "pullback_bias_results.txt").write_text(text, encoding="utf-8")
print(text)
