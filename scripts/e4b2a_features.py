"""E4-B2A — construction des features FINRA short sale volume (PIT, univers 400).

À partir du cache short_sale_volume_400.parquet, construit un DataFrame
(date, symbol, features short volume) aligné sur les dates du dataset O1
(pool Oracle Extreme) pour le diagnostic UP/DOWN.

Features (PIT, uniquement l'info disponible au jour D) :
  short_volume_ratio_1d/5d/20d      = short / total volume (moyennes glissantes)
  short_volume_zscore_20/60         = zscore du short_volume_ratio sur 20j/60j
  short_pressure_change_5d/20d      = ratio_5d/20d - ratio_5d/20d d'il y a 5j/20j
  short_ratio_trend_10d             = moyenne 10j / moyenne 60j (accélération)
  short_share                       = short_volume symbole / somme short_volume univers (jour D)
  ret5_x_short_ratio                = (cumul return 5j) x short_volume_ratio_5d
  rel_short_pressure_sector         = short_volume_ratio_5d - mediane sectorielle du jour
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

CACHE = Path("artifacts/finra_short_volume/short_sale_volume_400.parquet")
OUT = Path("artifacts/models/oracle/e4b2a_short_volume_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
SECTOR = Path("artifacts/models/oracle/e4b2a_symbol_sector.parquet")


def _roll_mean(g, col, w, minp):
    return g[col].transform(lambda x: x.rolling(w, min_periods=minp).mean())


def _roll_std(g, col, w, minp):
    return g[col].transform(lambda x: x.rolling(w, min_periods=minp).std())


def main() -> None:
    sv = pd.read_parquet(CACHE)
    sv["date"] = pd.to_datetime(sv["date"]).dt.normalize()
    sv["symbol"] = sv["symbol"].astype(str).str.upper()
    # ratio short / total (total > 0)
    sv = sv[sv["total_volume"] > 0].copy()
    sv["short_ratio"] = sv["short_volume"] / sv["total_volume"]
    sv = sv.sort_values(["symbol", "date"]).reset_index(drop=True)
    print(f"cache FINRA: {len(sv):,} lignes | {sv['date'].min().date()} -> {sv['date'].max().date()} | sym {sv['symbol'].nunique()}")

    g = sv.groupby("symbol", sort=False)
    # --- moyennes / zscores PIT par symbole ---
    sv["short_volume_ratio_1d"] = sv["short_ratio"]
    sv["short_volume_ratio_5d"] = _roll_mean(g, "short_ratio", 5, 3)
    sv["short_volume_ratio_20d"] = _roll_mean(g, "short_ratio", 20, 10)
    mu20 = _roll_mean(g, "short_ratio", 20, 10)
    sd20 = _roll_std(g, "short_ratio", 20, 10)
    mu60 = _roll_mean(g, "short_ratio", 60, 30)
    sd60 = _roll_std(g, "short_ratio", 60, 30)
    sv["short_volume_zscore_20"] = (sv["short_ratio"] - mu20) / sd20.clip(lower=1e-12)
    sv["short_volume_zscore_60"] = (sv["short_ratio"] - mu60) / sd60.clip(lower=1e-12)
    # --- changements PIT : ratio moyen maintenant vs il y a w jours ---
    sv["short_pressure_change_5d"] = sv["short_volume_ratio_5d"] - g["short_volume_ratio_5d"].transform(lambda x: x.shift(5))
    sv["short_pressure_change_20d"] = sv["short_volume_ratio_20d"] - g["short_volume_ratio_20d"].transform(lambda x: x.shift(20))
    # --- tendance : moyenne 10j / moyenne 60j ---
    sv["short_ratio_trend_10d"] = _roll_mean(g, "short_ratio", 10, 5) / _roll_mean(g, "short_ratio", 60, 30)
    # --- part de marché du short dans l'univers (jour D) ---
    sv["short_share"] = sv["short_volume"] / sv.groupby("date")["short_volume"].transform("sum")

    # --- interaction prix x pression : cumul return 5j (PIT depuis e2) ---
    ds = pd.read_parquet(DATA, columns=["date", "symbol", "daily_return"])
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    ds["symbol"] = ds["symbol"].astype(str).str.upper()
    ds = ds.drop_duplicates(["date", "symbol"])
    ds = ds.sort_values(["symbol", "date"])
    gg = ds.groupby("symbol", sort=False)
    ds["ret5"] = gg["daily_return"].transform(lambda x: x.rolling(5, min_periods=3).sum())
    sv = sv.merge(ds[["date", "symbol", "ret5"]], on=["date", "symbol"], how="left")
    sv["ret5_x_short_ratio"] = sv["ret5"] * sv["short_volume_ratio_5d"]

    # --- relatif sectoriel : ratio_5d - mediane sectorielle du jour ---
    sec = pd.read_parquet(SECTOR)
    sec["symbol"] = sec["symbol"].astype(str).str.upper()
    sv = sv.merge(sec, on="symbol", how="left")
    sv["rel_short_pressure_sector"] = (
        sv["short_volume_ratio_5d"] - sv.groupby(["date", "sector"])["short_volume_ratio_5d"].transform("median"))

    feats = ["short_volume_ratio_1d", "short_volume_ratio_5d", "short_volume_ratio_20d",
             "short_volume_zscore_20", "short_volume_zscore_60",
             "short_pressure_change_5d", "short_pressure_change_20d", "short_ratio_trend_10d",
             "short_share", "ret5_x_short_ratio", "rel_short_pressure_sector"]
    out = sv[["date", "symbol"] + feats].copy()

    # aligner sur les dates du dataset O1
    ds2 = pd.read_parquet(DATA, columns=["date"])
    ds2["date"] = pd.to_datetime(ds2["date"]).dt.normalize()
    dates = pd.DatetimeIndex(sorted(ds2["date"].unique()))
    out = out[out["date"].isin(dates)].reset_index(drop=True)
    out.to_parquet(OUT, index=False)
    print(f"features: {len(out):,} lignes | {out['date'].min().date()} -> {out['date'].max().date()} | sym {out['symbol'].nunique()} | {OUT}")
    for f in feats:
        print(f"  {f}: non-null {out[f].notna().mean()*100:.1f}% | mean {out[f].mean():.4f} | std {out[f].std():.4f}")


if __name__ == "__main__":
    main()
