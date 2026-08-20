import json
from pathlib import Path

ROOT = Path("artifacts/backtesting")
for name in ["cmp_b25_h20_2025_postfix_tp_m8", "cmp_b25_h20_2026_postfix_tp_m8"]:
    rp = ROOT / name / "report.json"
    j = json.loads(rp.read_text(encoding="utf-8"))
    s = j.get("summary", {})
    p = j.get("params", {})
    m = j.get("run_metadata", {})
    print(f"### {name}")
    print(f"  git={m.get('git_commit_sha','')[:10]}  period={p.get('start')}->{p.get('end')}")
    for k in ["total_return_pct", "profit_factor", "sharpe_ratio", "sortino_ratio",
              "max_drawdown_pct", "total_trades", "win_rate_pct", "long_trades",
              "short_trades", "long_pnl_total", "short_pnl_total", "pnl_net",
              "avg_trade_duration_days", "gross_exposure_avg_pct", "net_exposure_avg_pct",
              "turnover_pct"]:
        if k in s:
            print(f"  {k} = {s[k]}")
    print()
