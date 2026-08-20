"""E4-B2B — construction des features Short Interest FINRA (PIT, univers 400).

À partir de short_interest_400.parquet (settlement_date, publication_date, ...),
construit un DataFrame (date, symbol, features) ALIGNÉ sur les dates du pool
Oracle Extreme via un merge_asof STRICT sur publication_date :
  pour chaque (date D, symbol), on prend la DERNIÈRE publication dont
  publication_date <= D. => zéro look-ahead (la position n'est connue du
  modèle qu'à sa publication, ~7 jours ouvrés après la settlement date).

Features (PIT) :
  short_interest_raw           = current_short_position (stock)
  short_interest_change_abs    = current - previous (variation de cycle ~15j)
  short_interest_change_pct    = change_percent (fourni par FINRA)
  short_interest_dtc           = days_to_cover (fourni par FINRA)
  short_interest_accel_abs     = change_abs - change_abs du cycle précédent
  short_interest_ratio_float   = current / shares_outstanding (float PIT ffill)
  short_interest_ratio_advol   = current / average_daily_volume
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

SI = Path("artifacts/finra_short_volume/short_interest_400.parquet")
OUT = Path("artifacts/models/oracle/e4b2b_short_interest_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")


def main() -> None:
    si = pd.read_parquet(SI)
    si["settlement_date"] = pd.to_datetime(si["settlement_date"]).dt.normalize()
    si["publication_date"] = pd.to_datetime(si["publication_date"]).dt.normalize()
    si["symbol"] = si["symbol"].astype(str).str.upper()
    si = si.sort_values(["symbol", "settlement_date"]).reset_index(drop=True)
    print(f"short interest: {len(si):,} lignes | {si['settlement_date'].min().date()} -> {si['settlement_date'].max().date()} | sym {si['symbol'].nunique()}")

    # --- features par symbole (sur la série bimensuelle) ---
    g = si.groupby("symbol", sort=False)
    si["short_interest_change_abs"] = si["current_short_position"] - si["previous_short_position"]
    si["short_interest_change_pct"] = si["change_percent"]
    si["short_interest_dtc"] = si["days_to_cover"]
    si["short_interest_accel_abs"] = si["short_interest_change_abs"] - g["short_interest_change_abs"].transform(lambda x: x.shift(1))
    # ratio / volume quotidien moyen (cycle précédent) — robuste au split ?
    si["short_interest_ratio_advol"] = si["current_short_position"] / si["average_daily_volume"].clip(lower=1)

    # --- float PIT : shares_outstanding (stock_fundamentals_daily, ~1 valeur/trimestre) ---
    eng = get_sqlalchemy_engine()
    fund = pd.read_sql(
        text("SELECT symbol, trade_date, shares_outstanding FROM stock_fundamentals_daily "
             "WHERE trade_date BETWEEN '2021-06-01' AND '2026-06-30'"),
        eng)
    fund["trade_date"] = pd.to_datetime(fund["trade_date"]).dt.normalize()
    fund["symbol"] = fund["symbol"].astype(str).str.upper()
    fund = fund.dropna(subset=["shares_outstanding"]).drop_duplicates(["symbol", "trade_date"]).sort_values(["symbol", "trade_date"])
    # float PIT : dernière valeur connue <= settlement_date
    si = pd.merge_asof(
        si.sort_values("settlement_date"),
        fund.rename(columns={"trade_date": "settlement_date", "shares_outstanding": "float_pit"}).sort_values("settlement_date"),
        on="settlement_date", by="symbol", direction="backward")
    si["short_interest_ratio_float"] = si["current_short_position"] / si["float_pit"].clip(lower=1)
    print(f"float_pit couverture: {si['float_pit'].notna().mean()*100:.1f}%")

    feats = ["short_interest_raw", "short_interest_change_abs", "short_interest_change_pct",
             "short_interest_dtc", "short_interest_accel_abs",
             "short_interest_ratio_float", "short_interest_ratio_advol"]
    si["short_interest_raw"] = si["current_short_position"]

    # --- aligner sur le pool Oracle (dates de trading O1) via publication_date ---
    ds = pd.read_parquet(DATA, columns=["date", "symbol"])
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    ds["symbol"] = ds["symbol"].astype(str).str.upper()
    # grille (date, symbol) = les (date, symbol) du dataset O1 >= 2022
    grid = ds[ds["date"] >= "2022-01-01"][["date", "symbol"]].drop_duplicates().sort_values(["date", "symbol"])
    # merge_asof : pour chaque date de trading, dernière publication <= date
    si_pub = si[["symbol", "publication_date"] + feats].dropna(subset=["publication_date"]).rename(
        columns={"publication_date": "date"})
    grid = pd.merge_asof(
        grid.sort_values("date"),
        si_pub.sort_values("date"),
        on="date", by="symbol", direction="backward")
    grid.to_parquet(OUT, index=False)
    print(f"features pool: {len(grid):,} lignes | {grid['date'].min().date()} -> {grid['date'].max().date()} | sym {grid['symbol'].nunique()} | {OUT}")
    for f in feats:
        print(f"  {f}: non-null {grid[f].notna().mean()*100:.1f}%")


if __name__ == "__main__":
    main()
