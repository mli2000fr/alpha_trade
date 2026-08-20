"""Étape A3 — Comparaison baseline buggée (cceb808f) vs post-fix TP (HEAD).
Tableau canonique : Return, PF, Sharpe, DD, trades, WR, PnL L/S, exits TP/trailing/time.
"""
import json
import pandas as pd
from pathlib import Path

ROOT = Path("artifacts/backtesting")
RUNS = [
    ("2026 buggé", "cmp_b25_h20_2026_prodparity_p23_m8"),
    ("2026 post-fix", "cmp_b25_h20_2026_postfix_tp_m8"),
    ("2025 buggé", "cmp_b25_h20_2025_prodparity_p23_m8"),
    ("2025 post-fix", "cmp_b25_h20_2025_postfix_tp_m8"),
]

def load_summary(name):
    rp = ROOT / name / "report.json"
    if not rp.exists():
        return None
    j = json.loads(rp.read_text(encoding="utf-8"))
    return j.get("summary", {}), j.get("params", {}), j.get("run_metadata", {})

print("=" * 120)
print("TABLEAU CANONIQUE — baseline buggée vs post-fix TP")
print("=" * 120)
hdr = (f"{'run':24} {'Ret%':>8} {'PF':>6} {'Sharpe':>7} {'DD%':>7} {'N':>4} {'Win%':>6} "
       f"{'L_pnl':>9} {'S_pnl':>9} {'net':>9} {'git':>10}")
print(hdr)
print("-" * 120)
rows = []
for label, name in RUNS:
    res = load_summary(name)
    if res is None:
        print(f"{label:24} — report.json ABSENT (run pas terminé)")
        continue
    s, p, m = res
    rows.append({"label": label, "name": name, "s": s, "p": p, "m": m})
    print(f"{label:24} {s.get('total_return_pct',0):>8.2f} {s.get('profit_factor',0):>6.2f} "
          f"{s.get('sharpe_ratio',0):>7.2f} {s.get('max_drawdown_pct',0):>7.2f} "
          f"{s.get('total_trades',0):>4} {s.get('win_rate_pct',0):>6.1f} "
          f"{s.get('long_pnl_total',0):>9.0f} {s.get('short_pnl_total',0):>9.0f} "
          f"{s.get('pnl_net',0):>9.0f} {(m or {}).get('git_commit_sha','?')[:8]:>10}")

# Répartition des exits + TP distance
print("\n" + "=" * 120)
print("EXITS + TP distance")
print("=" * 120)
for label, name in RUNS:
    tal = ROOT / name / "trade_audit_log.csv"
    if not tal.exists():
        print(f"\n### {label} — pas de trade_audit_log")
        continue
    df = pd.read_csv(tal)
    tr = df[df["pnl"].notna()]
    if len(tr) == 0:
        print(f"\n### {label} — 0 trades")
        continue
    tp_dist = (tr["replay_take_profit_price"] / tr["entry_price"] - 1) * 100
    tp_dist = tp_dist.where(tr["side"] == "buy", -tp_dist)
    print(f"\n### {label} : N={len(tr)}")
    print(f"  TP distance: mean={tp_dist.mean():.1f}%  med={tp_dist.median():.1f}%  min={tp_dist.min():.1f}%  max={tp_dist.max():.1f}%")
    print(f"  exits: {tr['replay_exit_reason'].value_counts().to_dict()}")
    print(f"  L={tr[tr['side']=='buy']['pnl'].sum():.0f}  S={tr[tr['side']=='sell']['pnl'].sum():.0f}")
