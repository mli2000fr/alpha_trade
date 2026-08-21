"""Compte les symboles uniques par date dans les jeux de données utilisés."""
from __future__ import annotations

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

# 1. OOS predictions Oracle Extreme (run gelé)
oos = pd.read_parquet("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
oos["date"] = pd.to_datetime(oos["date"])
print("=== OOS Oracle Extreme (oracle-wf-20260819034014) ===")
print(f"  lignes={len(oos):,} | symboles uniques={oos['symbol'].nunique()}")
print(f"  symboles/date: median={oos.groupby('date')['symbol'].nunique().median():.0f} "
      f"min={oos.groupby('date')['symbol'].nunique().min()} max={oos.groupby('date')['symbol'].nunique().max()}")

# 2. OOS Oracle TOP d'origine (utilisé dans D1/D1b/D1d)
for run in ["oracle-wf-20260818021140", "oracle-wf-20260818035339"]:
    df = pd.read_parquet(f"artifacts/models/oracle/{run}/oos_predictions.parquet")
    df["date"] = pd.to_datetime(df["date"])
    print(f"=== {run} ===")
    print(f"  lignes={len(df):,} | symboles uniques={df['symbol'].nunique()}")
    print(f"  symboles/date: median={df.groupby('date')['symbol'].nunique().median():.0f} "
          f"max={df.groupby('date')['symbol'].nunique().max()}")

# 3. global_oracle_labels (labels complets)
eng = get_sqlalchemy_engine()
with eng.connect() as c:
    n = c.execute(text("SELECT COUNT(DISTINCT symbol) FROM global_oracle_labels")).scalar()
    per_date = c.execute(text(
        "SELECT AVG(cnt), MIN(cnt), MAX(cnt) FROM (SELECT prediction_date, COUNT(DISTINCT symbol) AS cnt "
        "FROM global_oracle_labels GROUP BY prediction_date) t"
    )).fetchone()
    print("=== global_oracle_labels (labels complets) ===")
    print(f"  symboles uniques={n}")
    print(f"  symboles/date: mean={per_date[0]:.0f} min={per_date[1]} max={per_date[2]}")

# 4. stock_scores_history (utilisé D1b/D1d)
with eng.connect() as c:
    n = c.execute(text("SELECT COUNT(DISTINCT symbol) FROM stock_scores_history")).scalar()
    per_date = c.execute(text(
        "SELECT AVG(cnt), MIN(cnt), MAX(cnt) FROM (SELECT snapshot_date, COUNT(DISTINCT symbol) AS cnt "
        "FROM stock_scores_history GROUP BY snapshot_date) t"
    )).fetchone()
    print("=== stock_scores_history ===")
    print(f"  symboles uniques={n}")
    print(f"  symboles/snapshot: mean={per_date[0]:.0f} min={per_date[1]} max={per_date[2]}")
