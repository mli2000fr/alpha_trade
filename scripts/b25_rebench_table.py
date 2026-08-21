"""Tableau canonique final A3 — depuis report.json (2026) + log (2025).
2025 post-fix : report.json pas encore écrit -> parse le log console.
"""
import json, re
from pathlib import Path

ROOT = Path("artifacts/backtesting")

def get_summary(name):
    rp = ROOT / name / "report.json"
    if rp.exists():
        j = json.loads(rp.read_text(encoding="utf-8"))
        return j.get("summary", {})
    return None

def parse_log_2025(name):
    """Parse le log console 2025 (report pas encore ecrit)."""
    log = (ROOT / name / f"{name.split('/')[-1]}.log")
    # le log est a la racine artifacts/backtesting/
    log = ROOT / f"{name}.log"
    txt = log.read_text(encoding="utf-8", errors="replace")
    d = {}
    def grab(pat):
        m = re.search(pat, txt)
        return float(m.group(1).replace(",", "").replace("$", "")) if m else None
    d["ret_pnl"] = grab(r"PnL Net\s+\$([\d,\.\-]+)")
    d["pf"] = grab(r"Profit Factor\s+([\d\.]+)")
    d["dd"] = grab(r"Max Drawdown\s+([\d\.]+)")
    d["trades"] = int(grab(r"Nombre de trades\s+([\d]+)") or 0)
    d["win"] = grab(r"Win Rate\s+([\d\.]+)")
    d["long_pnl"] = grab(r"Trades Long\s+\d+\s+\(WR: [\d\.]+\%, PnL: \$([\d,\.\-]+)")
    d["short_pnl"] = grab(r"Trades Short\s+\d+\s+\(WR: [\d\.]+\%, PnL: \$([\d,\.\-]+)")
    return d

print("=" * 110)
print("ÉTAPE A — TABLEAU CANONIQUE baseline buggée vs post-fix TP")
print("=" * 110)
hdr = (f"{'run':30} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'DD%':>7} {'N':>4} {'Win%':>6} "
       f"{'L_pnl':>9} {'S_pnl':>9} {'net':>9}")
print(hdr)
print("-" * 110)

# 2026
for label, name in [("2026 BUGGÉ", "cmp_b25_h20_2026_prodparity_p23_m8"),
                    ("2026 POST-FIX", "cmp_b25_h20_2026_postfix_tp_m8")]:
    s = get_summary(name)
    if s:
        print(f"{label:30} {s.get('total_return_pct',0):>8.2f} {s.get('profit_factor',0):>6.2f} "
              f"{s.get('sharpe_ratio',0):>7.2f} {s.get('max_drawdown_pct',0):>7.2f} "
              f"{s.get('total_trades',0):>4} {s.get('win_rate_pct',0):>6.1f} "
              f"{s.get('long_pnl_total',0):>9.0f} {s.get('short_pnl_total',0):>9.0f} "
              f"{s.get('pnl_net',0):>9.0f}")
    else:
        print(f"{label:30} report absent")

# 2025
for label, name in [("2025 BUGGÉ", "cmp_b25_h20_2025_prodparity_p23_m8"),
                    ("2025 POST-FIX", "cmp_b25_h20_2025_postfix_tp_m8")]:
    s = get_summary(name)
    if s:
        print(f"{label:30} {s.get('total_return_pct',0):>8.2f} {s.get('profit_factor',0):>6.2f} "
              f"{s.get('sharpe_ratio',0):>7.2f} {s.get('max_drawdown_pct',0):>7.2f} "
              f"{s.get('total_trades',0):>4} {s.get('win_rate_pct',0):>6.1f} "
              f"{s.get('long_pnl_total',0):>9.0f} {s.get('short_pnl_total',0):>9.0f} "
              f"{s.get('pnl_net',0):>9.0f}")
    else:
        d = parse_log_2025(name)
        ret = d.get("ret_pnl", 0) / 100000 * 100
        print(f"{label:30} {ret:>8.2f} {d.get('pf',0):>6.2f} {'N/A':>7} {d.get('dd',0):>7.2f} "
              f"{d.get('trades',0):>4} {d.get('win',0):>6.1f} "
              f"{d.get('long_pnl',0):>9.0f} {d.get('short_pnl',0):>9.0f} "
              f"{d.get('ret_pnl',0):>9.0f}")
