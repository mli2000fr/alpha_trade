"""Compare les métriques report.json de plusieurs runs backtest (A/B ablation).

Usage:
    python compare_ablation.py <run_dir_1> [<run_dir_2> ...]

Chaque run_dir pointe vers le dossier contenant report.json + trades.csv.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


def load_run(run_dir: Path) -> dict:
    rep = json.loads((run_dir / "report.json").read_text())
    s = rep["summary"]
    trades = pd.read_csv(run_dir / "trades.csv", low_memory=False)
    trades["side"] = trades["side"].map({"buy": "long", "sell": "short"})
    closed = trades[trades["trade_status"] == "closed"]
    g = closed.groupby("side").agg(
        n=("pnl", "size"),
        pnl=("pnl", "sum"),
        wins=("pnl", lambda x: int((x > 0).sum())),
    )
    rec = {
        "run": run_dir.name,
        "total_return_pct": s.get("total_return_pct"),
        "max_drawdown_pct": s.get("max_drawdown_pct"),
        "profit_factor": s.get("profit_factor"),
        "sharpe_ratio": s.get("sharpe_ratio"),
        "win_rate_pct": s.get("win_rate_pct"),
        "legacy_trades": s.get("total_trades"),
        "legacy_long": s.get("long_trades"),
        "legacy_short": s.get("short_trades"),
        "legacy_long_pnl": s.get("long_pnl_total"),
        "legacy_short_pnl": s.get("short_pnl_total"),
        "pipeline_closed": len(closed),
        "pipeline_long": int(g.loc["long", "n"]) if "long" in g.index else 0,
        "pipeline_short": int(g.loc["short", "n"]) if "short" in g.index else 0,
        "pipeline_long_pnl": float(g.loc["long", "pnl"]) if "long" in g.index else 0.0,
        "pipeline_short_pnl": float(g.loc["short", "pnl"]) if "short" in g.index else 0.0,
    }
    return rec


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    runs = [Path(a) for a in sys.argv[1:]]
    rows = [load_run(r) for r in runs]
    df = pd.DataFrame(rows)
    cols = [
        "run", "total_return_pct", "max_drawdown_pct", "profit_factor", "sharpe_ratio",
        "win_rate_pct", "legacy_trades", "legacy_long", "legacy_short",
        "legacy_long_pnl", "legacy_short_pnl",
        "pipeline_closed", "pipeline_long", "pipeline_short",
        "pipeline_long_pnl", "pipeline_short_pnl",
    ]
    with pd.option_context("display.width", 250, "display.max_columns", None):
        print(df[cols].to_string(index=False))


if __name__ == "__main__":
    main()
