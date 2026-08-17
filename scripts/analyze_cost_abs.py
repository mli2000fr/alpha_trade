# -*- coding: utf-8 -*-
"""Analyse des résultats de la série Test 1b (coût RT absolu + fallback).

Produit : logs/stress_cost_abs_results.txt
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "artifacts" / "backtesting"
OUT = ROOT / "logs" / "stress_cost_abs_results.txt"

RUNS = [
    ("cost_rt10", "10 bps RT (contrôle)"),
    ("cost_rt20", "20 bps RT"),
    ("cost_rt30", "30 bps RT"),
    ("cost_rt44", "44 bps RT (pessimiste)"),
    ("cost_rt60", "60 bps RT (extrême)"),
    ("fb10", "fallback 10 bps"),
    ("fb15", "fallback 15 bps"),
    ("fb20", "fallback 20 bps"),
]
# Référence benchmark (coût actuel ~10 bps RT)
REF = ("cmp_b25_h20_2026_prodparity_repro_h20cfg_m8", "actuel ~10 bps RT")


def _get(name):
    p = BASE / name / "report.json"
    if not p.exists():
        return None
    return json.load(open(p, encoding="utf-8"))["summary"]


lines = []
w = lines.append
w("=" * 88)
w("TEST 1b — COÛT ROUND-TRIP ABSOLU + FALLBACK (pile gelée B25 m8, 2026)")
w("=" * 88)
hdr = f"{'scénario':<26}{'ret':>9}{'DD':>8}{'PF':>7}{'trades':>7}{'L':>4}{'S':>4}{'win':>7}{'long$':>9}{'short$':>9}"
w(hdr)
w("-" * 88)


def _row(label, s):
    if s is None:
        w(f"{label:<26}  PAS DE RAPPORT")
        return
    w(f"{label:<26}{s['total_return_pct']:>8.2f}%{s['max_drawdown_pct']:>7.2f}%"
      f"{s['profit_factor']:>7.3f}{s['total_trades']:>7}{s['long_trades']:>4}"
      f"{s['short_trades']:>4}{s['win_rate_pct']:>6.1f}%"
      f"{s['long_pnl_total']:>9.0f}{s['short_pnl_total']:>9.0f}")


ref = _get(REF[0])
_row(REF[1], ref)
w("-" * 88)
for name, label in RUNS:
    _row(label, _get(name))

text = "\n".join(lines)
OUT.write_text(text, encoding="utf-8")
print(text)

# Verdict
if ref is not None:
    w("\nVerdict (44 bps RT): PF > 1.5 ET DD < 10% ?")
    s44 = _get("cost_rt44")
    if s44:
        ok = s44["profit_factor"] > 1.5 and s44["max_drawdown_pct"] < 10.0
        w(f"  PF={s44['profit_factor']:.3f}  DD={s44['max_drawdown_pct']:.2f}%  "
          f"→ {'✅ OUI — risque coûts clos' if ok else '❌ NON'}")
        OUT.write_text("\n".join(lines), encoding="utf-8")
