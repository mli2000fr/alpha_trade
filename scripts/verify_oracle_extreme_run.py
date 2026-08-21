"""Vérifie le parquet du nouveau run Oracle Extreme (proba_extreme)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

run = Path("artifacts/models/oracle/oracle-wf-20260819034014/oos_predictions.parquet")
df = pd.read_parquet(run)
print(f"run: {run}")
print(f"cols={list(df.columns)}")
print(f"rows={len(df):,} | dates={df['date'].min().date()} -> {df['date'].max().date()}")
for c in df.columns:
    if "proba" in c or "oracle" in c or "extreme" in c:
        print(f"  {c}: nonnull={df[c].notna().mean()*100:.1f}%  mean={df[c].mean() if df[c].notna().any() else 'NA':.4f}" if df[c].notna().any() else f"  {c}: nonnull=0%")
