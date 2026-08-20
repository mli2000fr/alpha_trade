"""Vérifie la couverture par semestre du nouveau parquet OOS O0 (H2 inclus)."""
import sys
sys.path.insert(0, "f:/projets")
import pandas as pd
from pathlib import Path

OOS = Path("artifacts/models/oracle/oracle-wf-20260820025255/oos_predictions.parquet")
df = pd.read_parquet(OOS, columns=["date", "symbol"])
df["date"] = pd.to_datetime(df["date"]).dt.normalize()
df["sem"] = df["date"].dt.year.astype(str) + "H" + ((df["date"].dt.month > 6).astype(int) + 1).astype(str)
g = df.groupby("sem").agg(n=("symbol", "size"), nsym=("symbol", "nunique"))
print(f"total rows: {len(df):,} | symbols: {df['symbol'].nunique()}")
print("couverture par semestre:")
for sem, r in g.iterrows():
    print(f"  {sem}: n={r.n:>8,} symbols={r.nsym}")
