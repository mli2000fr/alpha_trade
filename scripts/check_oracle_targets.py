"""Vérifie que load_oracle_targets lit oracle_extreme10 depuis la DB."""
from __future__ import annotations

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import TARGET_COL, load_oracle_targets

eng = get_sqlalchemy_engine()
batch = "model-factory-20260811223551-ef2cd0"
df = load_oracle_targets(eng, batch, horizon=20)
print(f"rows={len(df):,} | cols={list(df.columns)}")
print(f"TARGET_COL={TARGET_COL!r} présent: {TARGET_COL in df.columns}")
if TARGET_COL in df.columns:
    print(f"extreme=1: {int(df[TARGET_COL].fillna(0).sum()):,} "
          f"({df[TARGET_COL].fillna(0).mean()*100:.1f}%)")
    print(f"date range: {df['prediction_date'].min().date()} -> {df['prediction_date'].max().date()}")
    print(f"guard non-null: {df['oracle_available_date'].notna().mean()*100:.1f}%")
