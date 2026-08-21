# -*- coding: utf-8 -*-
"""Vérifie les spreads réels des titres tradés (audit des coûts)."""
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

# Titres du benchmark + leurs spreads sur la période du trade
SYMBOLS = ["CLX", "FMC", "GDDY", "VRNS", "QFIN", "CAG", "BSY", "LBRDK", "VTRS", "KD", "BILL", "MNDY"]

with ENGINE.connect() as c:
    for sym in SYMBOLS:
        r = c.execute(
            text(
                "SELECT quote_date, spread_bps FROM stock_quote_snapshots "
                "WHERE symbol = :s AND quote_date BETWEEN '2026-01-02' AND '2026-05-31' "
                "ORDER BY quote_date"
            ),
            {"s": sym},
        ).fetchall()
        if not r:
            print(f"{sym:<6} : AUCUNE donnée de spread (fallback 5 bps)")
            continue
        vals = [float(x[1]) for x in r]
        dates = [str(x[0])[:10] for x in r]
        print(f"{sym:<6} : n={len(r)}  min={min(vals):.1f}  méd={sorted(vals)[len(vals)//2]:.1f}  "
              f"max={max(vals):.1f}  bps | {dates[0]}→{dates[-1]}")
        # jours où spread > 60 bps
        big = [d for d, v in zip(dates, vals) if v > 60]
        if big:
            print(f"        ⚠️  jours spread>60 bps : {big[:6]}")
