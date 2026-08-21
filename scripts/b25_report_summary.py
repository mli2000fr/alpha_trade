import json
from pathlib import Path

for name in ["artifacts/backtesting/b25_2025_rankw", "artifacts/benchmarks/OOS2026_B25_P14_m8_v1"]:
    p = Path(name) / "report.json"
    print(f"=== {name} ===")
    d = json.loads(p.read_text(encoding="utf-8"))
    # afficher les métriques clés
    def walk(o, prefix=""):
        if isinstance(o, dict):
            for k, v in list(o.items()):
                if k in ("return_pct", "profit_factor", "sharpe", "sortino", "max_drawdown", "n_trades", "win_rate", "total_return", "return", "max_drawdown_pct", "trades", "start_date", "end_date"):
                    print(f"  {prefix}{k}: {v}")
                elif isinstance(v, dict) and len(prefix) < 30:
                    walk(v, prefix + k + ".")
        elif isinstance(o, list) and len(prefix) < 30:
            if o and isinstance(o[0], dict):
                print(f"  {prefix}[0]: {str(o[0])[:200]}")
    walk(d)
    print()
