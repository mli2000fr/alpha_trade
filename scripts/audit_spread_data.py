# -*- coding: utf-8 -*-
"""Audit données de spread : corruption + spread au jour du trade."""
from sqlalchemy import create_engine, text

ENGINE = create_engine("mysql+pymysql://root:root@localhost/alpha_trade", future=True)

with ENGINE.connect() as c:
    # Taux de données corrompues (>300 bps = filtrées par MAX_REALISTIC_SPREAD_BPS)
    total = c.execute(text("SELECT COUNT(1) FROM stock_quote_snapshots WHERE spread_bps IS NOT NULL AND spread_bps >= 0")).scalar()
    n300 = c.execute(text("SELECT COUNT(1) FROM stock_quote_snapshots WHERE spread_bps > 300")).scalar()
    n100 = c.execute(text("SELECT COUNT(1) FROM stock_quote_snapshots WHERE spread_bps > 100 AND spread_bps <= 300")).scalar()
    print(f"snapshots total={total}")
    print(f"  >300 bps (filtrées→fallback 5) : {n300} ({n300/total*100:.1f}%)")
    print(f"  100-300 bps (appliquées, aberrantes) : {n100} ({n100/total*100:.1f}%)")

    # Spread CLX au jour exact du trade (2026-01-21)
    r = c.execute(text(
        "SELECT quote_date, spread_bps FROM stock_quote_snapshots "
        "WHERE symbol='CLX' AND quote_date IN ('2026-01-21','2026-01-22','2026-01-20') ORDER BY quote_date"
    )).fetchall()
    print("CLX spreads autour du 21/01 (jour entrée):", [(str(x[0])[:10], float(x[1])) for x in r])

    # Spread FMC au jour du trade (entrée 2026-01-05, sortie 2026-01-29)
    r = c.execute(text(
        "SELECT quote_date, spread_bps FROM stock_quote_snapshots "
        "WHERE symbol='FMC' AND quote_date IN ('2026-01-05','2026-01-06','2026-01-29') ORDER BY quote_date"
    )).fetchall()
    print("FMC spreads (entrée 01-05, sortie 01-29):", [(str(x[0])[:10], float(x[1])) for x in r])

    # Médiane globale en excluant les >300
    r = c.execute(text(
        "SELECT COUNT(1) FROM stock_quote_snapshots WHERE spread_bps <= 300 AND spread_bps >= 0"
    )).scalar()
    print(f"snapshots <=300 bps (données 'saines') : {r}")
