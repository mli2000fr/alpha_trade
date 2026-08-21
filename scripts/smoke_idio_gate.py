# -*- coding: utf-8 -*-
"""Smoke test du gate idio_vol60 de backtesting.cli._impl._apply_idio_gate."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import create_engine

from backtesting.cli._impl import _apply_idio_gate
from backtesting.data_loader import load_ohlcv

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

# fenêtre d'essai : 3 séances de janvier 2025
bars = load_ohlcv(ENGINE, date(2024, 6, 1), date(2025, 1, 10))
dates = sorted(bars["trade_date"].dropna().unique())[-3:]
symbols = sorted(bars["symbol"].unique())[:40]
print("symboles test:", len(symbols), "dates:", [d.date() for d in dates])

rows = []
for d in dates:
    for s in symbols:
        rows.append({"symbol": s, "trade_date": d, "predicted_side": "long",
                     "proba_long": 0.7, "proba_short": 0.0})
preds = pd.DataFrame(rows)
print("avant :", len(preds), "lignes")

for gate in ("p70", "p80", "random70"):
    out = _apply_idio_gate(
        ENGINE, preds.copy(), gate, 42,
        start_date=dates[0].date(), end_date=dates[-1].date(),
    )
    n_flat = int((out["predicted_side"] == "flat").sum())
    n_kept = int((out["predicted_side"] != "flat").sum())
    print(f"{gate}: flat={n_flat} kept={n_kept} (attendu ~30%/20% flat)")
