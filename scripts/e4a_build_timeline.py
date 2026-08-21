"""E4-A étape 1 — Construit la matrice temporelle complète des features O1 (toutes dates).

Pour E4-A (temporal pre-crash signature), on a besoin des features à D-60..D,
pas seulement à D. On reconstruit build_feature_matrix sur toute la fenêtre et
on persiste la matrice temporelle (date, symbol, features) pour extraire les lags.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from database.connection import get_sqlalchemy_engine
from modelFactory.oracle.dataset import build_feature_matrix
from modelFactory.oracle.train import get_universe_symbols

BATCH = "model-factory-20260811223551-ef2cd0"
OUT = Path("artifacts/models/oracle/e4a_timeline_features.parquet")


def main() -> None:
    engine = get_sqlalchemy_engine()
    symbols = get_universe_symbols(engine, BATCH, horizon=20)
    print(f"universe: {len(symbols)} symbols — building full timeline features...")
    feats = build_feature_matrix(
        engine, symbols,
        start_date="2021-06-01", end_date="2026-05-29",  # D-60 couvert dès 2021
    )
    if feats.empty:
        raise SystemExit("matrice vide")
    feats["date"] = pd.to_datetime(feats["date"]).dt.normalize()
    feats["symbol"] = feats["symbol"].astype(str)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    feats.to_parquet(OUT, index=False)
    print(f"persisted: {OUT} | {len(feats):,} lignes | {feats['date'].min().date()} -> {feats['date'].max().date()} "
          f"| {len(feats.columns)} colonnes | {feats['symbol'].nunique()} symboles")


if __name__ == "__main__":
    main()
