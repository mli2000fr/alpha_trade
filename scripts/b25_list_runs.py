from pathlib import Path
import json

d = Path("artifacts/backtesting")
runs = sorted(f.name for f in d.iterdir() if f.name.startswith("cmp_b25"))
print(f"=== {len(runs)} runs cmp_b25_* ===")
for r in runs:
    rp = d / r / "report.json"
    if rp.exists():
        try:
            j = json.loads(rp.read_text(encoding="utf-8"))
            s = j.get("summary", {})
            params = j.get("params", {})
            print(f"\n### {r}")
            print(f"  period: {params.get('start')} -> {params.get('end')}")
            print(f"  max_pos: {params.get('max_positions')}")
            print(f"  return: {s.get('total_return_pct'):.2f}%  PF: {s.get('profit_factor')}  DD: {s.get('max_drawdown_pct'):.2f}%  trades: {s.get('total_trades')}  win: {s.get('win_rate_pct'):.1f}%")
            print(f"  long: {s.get('long_pnl_total'):.0f}  short: {s.get('short_pnl_total'):.0f}  net: {s.get('pnl_net'):.0f}")
            print(f"  L/S trades: {s.get('long_trades')}/{s.get('short_trades')}")
        except Exception as e:
            print(f"\n### {r}  ERREUR: {e}")
    else:
        print(f"\n### {r}  (pas de report.json)")
