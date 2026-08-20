"""Identifie les runs Oracle TOP vs BOTTOM dans artifacts/models/oracle."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

base = Path("artifacts/models/oracle")
for d in sorted(base.iterdir()):
    if not d.is_dir():
        continue
    pq = d / "oos_predictions.parquet"
    if not pq.exists():
        continue
    df = pd.read_parquet(pq)
    print(f"{d.name}:")
    print(f"  cols={list(df.columns)}")
    print(f"  rows={len(df):,}  dates={df['date'].min().date()} -> {df['date'].max().date()}")
    for c in df.columns:
        if c.startswith("proba"):
            print(f"  {c}: nonnull={df[c].notna().mean()*100:.1f}%")
    print()
