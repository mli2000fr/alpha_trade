"""Investigue relative_strength_index : distribution réelle + cohérence avec la formule."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

eng = get_sqlalchemy_engine()
with eng.connect() as c:
    stats = c.execute(text(
        "SELECT COUNT(*), COUNT(relative_strength_index), "
        "MIN(relative_strength_index), MAX(relative_strength_index), "
        "AVG(relative_strength_index) "
        "FROM stock_scores_history"
    )).fetchone()
    print(f"N={stats[0]:,} | non-null={stats[1]:,}")
    print(f"min={stats[2]:.1f} max={stats[3]:.1f} mean={stats[4]:.1f}")

    # distribution par buckets
    buckets = c.execute(text(
        "SELECT CASE "
        "  WHEN relative_strength_index < 0 THEN '<0' "
        "  WHEN relative_strength_index < 50 THEN '0-50' "
        "  WHEN relative_strength_index < 90 THEN '50-90' "
        "  WHEN relative_strength_index < 100 THEN '90-100' "
        "  WHEN relative_strength_index < 110 THEN '100-110' "
        "  WHEN relative_strength_index < 130 THEN '110-130' "
        "  WHEN relative_strength_index < 150 THEN '130-150' "
        "  WHEN relative_strength_index < 200 THEN '150-200' "
        "  ELSE '>=200' END AS bucket, COUNT(*), MIN(relative_strength_index), MAX(relative_strength_index) "
        "FROM stock_scores_history WHERE relative_strength_index IS NOT NULL "
        "GROUP BY bucket ORDER BY MIN(relative_strength_index)"
    )).fetchall()
    print("\nDistribution :")
    for b in buckets:
        print(f"  {b[0]:<8}: N={b[1]:>6,}  min={b[2]:8.1f}  max={b[3]:8.1f}")

    # échantillon de valeurs typiques
    samp = c.execute(text(
        "SELECT symbol, snapshot_date, relative_strength_index, total_score "
        "FROM stock_scores_history WHERE relative_strength_index IS NOT NULL "
        "ORDER BY snapshot_date DESC, relative_strength_index DESC LIMIT 8"
    )).fetchall()
    print("\nÉchantillon (valeurs hautes récentes) :")
    for r in samp:
        print(f"  {r[0]:<8} {r[1]}  rsi={r[2]:8.1f}  total={r[3]:.1f}")
