# -*- coding: utf-8 -*-
"""Comparaison : pénalité d'exécution benchmark validé vs run IHM suspect."""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

RUNS = {
    "benchmark (2026)": ROOT / "artifacts/backtesting/cmp_b25_h20_2026_prodparity_repro_h20cfg_m8/trade_audit_log.csv",
    "run IHM suspect": ROOT / "artifacts/ihm_backtesting_runs/run/20260817_165433_2785da86/artifacts/trade_audit_log.csv",
}

for label, path in RUNS.items():
    df = pd.read_csv(path)
    entries = df[df["event_type"] == "entry_opened"].copy()
    entries["exec_date"] = pd.to_datetime(entries["execution_date"]).dt.date
    sample = entries.head(10)
    diffs = []
    with ENGINE.connect() as c:
        for _, r in sample.iterrows():
            q = c.execute(
                text("SELECT open FROM stock_bars_daily WHERE symbol=:s AND date=:d"),
                {"s": str(r["symbol"]).strip(), "d": r["exec_date"]},
            ).fetchone()
            if q is None:
                continue
            diff = (float(r["entry_price"]) / float(q[0]) - 1.0) * 10000
            diffs.append((str(r["symbol"]).strip(), str(r["side"]).strip(), round(diff, 2)))
    print(f"=== {label} ===")
    print("  (symbol, side, diff_bps)")
    for d in diffs:
        print("   ", d)
    if diffs:
        print(f"   diff moyen: {sum(x[2] for x in diffs)/len(diffs):.2f} bps")
    print()
