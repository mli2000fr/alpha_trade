import json, re
from pathlib import Path

ROOT = Path("artifacts/backtesting")

def load(name):
    rp = ROOT / name / "report.json"
    if rp.exists():
        j = json.loads(rp.read_text(encoding="utf-8"))
        return j.get("summary", {})
    return None

# 2025 post-fix report maintenant disponible
s25 = load("cmp_b25_h20_2025_postfix_tp_m8")
s26 = load("cmp_b25_h20_2026_postfix_tp_m8")
s25b = load("cmp_b25_h20_2025_prodparity_p23_m8")
s26b = load("cmp_b25_h20_2026_prodparity_p23_m8")

def row(label, s):
    if not s:
        print(f"{label:28} report absent")
        return
    print(f"{label:28} {s.get('total_return_pct',0):>9.2f} {s.get('profit_factor',0):>6.2f} "
          f"{s.get('sharpe_ratio',0):>7.2f} {s.get('max_drawdown_pct',0):>7.2f} "
          f"{s.get('total_trades',0):>4} {s.get('win_rate_pct',0):>6.1f} "
          f"{s.get('long_pnl_total',0):>9.0f} {s.get('short_pnl_total',0):>9.0f} "
          f"{s.get('pnl_net',0):>9.0f}")

print("ÉTAPE A — TABLEAU CANONIQUE (post-fix TP vs buggé)")
print(f"{'run':28} {'Ret%':>9} {'PF':>6} {'Sharpe':>7} {'DD%':>7} {'N':>4} {'Win%':>6} {'L_pnl':>9} {'S_pnl':>9} {'net':>9}")
print("-" * 105)
row("2025 BUGGÉ (cceb808f)", s25b)
row("2025 POST-FIX (HEAD)", s25)
print()
row("2026 BUGGÉ (cceb808f)", s26b)
row("2026 POST-FIX (HEAD)", s26)
