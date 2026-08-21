"""Construit et persiste le dataset O1 Oracle Extreme (features + target) pour E2-C/D.

Reproduit EXACTEMENT le pipeline du walk_forward (build_dataset + ablation O1) :
- features expert + xs_ranks + global_rank_20 + drawdown_20 + high_low_position_20 ;
- target oracle_extreme10, future_return, oracle_decile, oracle_pct_rank ;
- garde anti-leakage (oracle_available_date > date).

⚠️ RESTREINT à l'univers du modèle : on ne garde que les (date, symbol) présents
dans le parquet OOS gelé oracle-wf-20260819034014 (les ~400 symboles évalués,
2022→2026, 326 273 lignes) — PAS les labels 2018-2021 hors OOS.

Sortie : artifacts/models/oracle/e2_feature_dataset.parquet (utilisé par e2_feature_drift
et e2_conditional_performance — PAS de retraining).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import (
    GUARD_COL,
    TARGET_COL,
    ablation_features,
    build_dataset,
)
from modelFactory.oracle.train import get_universe_symbols

BATCH = "model-factory-20260811223551-ef2cd0"
OOS = Path("artifacts/models/oracle/oracle-wf-20260820025255/oos_predictions.parquet")
OUT = Path("artifacts/models/oracle/e2_feature_dataset.parquet")


def main() -> None:
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, BATCH, horizon=20)
    print(f"universe: {len(symbols)} symbols — building dataset O1...")
    dataset, feature_columns = build_dataset(
        engine, BATCH, symbols,
        start_date="2020-01-01", end_date="2026-05-29", horizon=20,
    )
    if dataset.empty:
        raise SystemExit("dataset vide")
    print(f"dataset brut: {len(dataset):,} lignes | {dataset['date'].min().date()} -> {dataset['date'].max().date()}")

    # ── Restreindre à l'univers du modèle (parquet OOS) ──
    oos = pd.read_parquet(OOS, columns=["date", "symbol"])
    oos["date"] = pd.to_datetime(oos["date"]).dt.normalize()
    oos["symbol"] = oos["symbol"].astype(str)
    keys = set(zip(oos["symbol"], oos["date"]))
    dataset["symbol"] = dataset["symbol"].astype(str)
    dataset["date"] = pd.to_datetime(dataset["date"]).dt.normalize()
    mask = [ (s, d) in keys for s, d in zip(dataset["symbol"], dataset["date"]) ]
    dataset = dataset[mask].copy()
    print(f"dataset OOS-restreint: {len(dataset):,} lignes | {len(dataset['symbol'].unique())} symboles "
          f"| {dataset['date'].min().date()} -> {dataset['date'].max().date()}")

    o1_cols = [c for c in ablation_features(feature_columns, include_global_rank=True, include_oracle_extras=True) if c in dataset.columns]
    keep = [GUARD_COL, TARGET_COL, "future_return", "oracle_decile", "oracle_pct_rank",
            "date", "symbol"] + o1_cols
    keep = [c for c in keep if c in dataset.columns]
    out = dataset[keep].copy()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT, index=False)
    print(f"persisted: {OUT} | {len(out):,} lignes | {len(o1_cols)} features O1")


if __name__ == "__main__":
    main()
