"""E4-B4-A — features insider Form 4 (PIT) + validation de l'échantillon 20.

À partir de form4_20symbols.parquet, construit un DataFrame (date, symbol,
features insider) aligné sur le pool Oracle Extreme via merge_asof backward
sur filing_date (PIT strict : une transaction n'est connue qu'au dépôt SEC).

Features (PIT) :
  insider_net_purchase_5d/20d/60d   = somme (shares signés) sur fenêtres glissantes
  insider_buy_ratio_20d             = nb achats / (achats+ventes) sur 20j
  insider_tx_count_20d              = nb de transactions sur 20j
  insider_net_purchase_value_20d    = somme (shares*prix signés) sur 20j

Signe : transactionCode P (achat)=+1, S (vente)=-1 ; codes M/C/A (exercice/
attribution) neutralisés (non discrétionnaires). acquisitionDisposedCode:
A=+1, D=-1 en secours.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

FORM4 = Path("artifacts/sec_cache/form4_20symbols.parquet")
OUT = Path("artifacts/models/oracle/e4b4_insider_features_20.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")

# codes discrétionnaires : P=purchase, S=sale. M=exercise, C=conversion, A=grant -> neutre
_BUY_CODES = {"P"}
_SELL_CODES = {"S"}


def main() -> None:
    f4 = pd.read_parquet(FORM4)
    f4["filing_date"] = pd.to_datetime(f4["filing_date"]).dt.normalize()
    f4["symbol"] = f4["symbol"].astype(str).str.upper()
    print(f"form4: {len(f4):,} transactions | {f4['symbol'].nunique()} symboles | {f4['filing_date'].min().date()} -> {f4['filing_date'].max().date()}")

    # signe des transactions
    f4["sign"] = 0.0
    f4.loc[f4["transaction_code"].isin(_BUY_CODES), "sign"] = 1.0
    f4.loc[f4["transaction_code"].isin(_SELL_CODES), "sign"] = -1.0
    # valeur (shares * prix) signée
    f4["signed_value"] = f4["sign"] * f4["shares"].fillna(0) * f4["price_per_share"].fillna(0)
    f4["signed_shares"] = f4["sign"] * f4["shares"].fillna(0)
    # une ligne par (symbol, filing_date) : agréger les tx du même jour
    agg = f4.groupby(["symbol", "filing_date"]).agg(
        net_shares=("signed_shares", "sum"),
        net_value=("signed_value", "sum"),
        n_buy=("sign", lambda s: int((s == 1).sum())),
        n_sell=("sign", lambda s: int((s == -1).sum())),
        n_tx=("sign", "count"),
    ).reset_index()
    agg = agg.sort_values(["symbol", "filing_date"])

    g = agg.groupby("symbol", sort=False)
    agg["insider_net_purchase_5d"] = g["net_shares"].transform(lambda x: x.rolling(5, min_periods=1).sum())
    agg["insider_net_purchase_20d"] = g["net_shares"].transform(lambda x: x.rolling(20, min_periods=1).sum())
    agg["insider_net_purchase_60d"] = g["net_shares"].transform(lambda x: x.rolling(60, min_periods=1).sum())
    agg["insider_net_value_20d"] = g["net_value"].transform(lambda x: x.rolling(20, min_periods=1).sum())
    agg["insider_tx_count_20d"] = g["n_tx"].transform(lambda x: x.rolling(20, min_periods=1).sum())
    agg["insider_buy_ratio_20d"] = (
        g["n_buy"].transform(lambda x: x.rolling(20, min_periods=1).sum()) /
        (g["n_buy"].transform(lambda x: x.rolling(20, min_periods=1).sum()) +
         g["n_sell"].transform(lambda x: x.rolling(20, min_periods=1).sum())).clip(lower=1))

    feats = ["insider_net_purchase_5d", "insider_net_purchase_20d", "insider_net_purchase_60d",
             "insider_net_value_20d", "insider_tx_count_20d", "insider_buy_ratio_20d"]
    si = agg[["symbol", "filing_date"] + feats].rename(columns={"filing_date": "date"})

    # grille du pool Oracle (date, symbol) >= 2022
    ds = pd.read_parquet(DATA, columns=["date", "symbol"])
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    ds["symbol"] = ds["symbol"].astype(str).str.upper()
    grid = ds[ds["date"] >= "2022-01-01"][["date", "symbol"]].drop_duplicates().reset_index(drop=True)

    # PIT : dernière valeur connue <= date (merge_asof backward)
    out = pd.merge_asof(
        grid.sort_values("date"),
        si.sort_values("date"),
        on="date", by="symbol", direction="backward")
    out.to_parquet(OUT, index=False)
    print(f"features pool: {len(out):,} lignes | {out['date'].min().date()} -> {out['date'].max().date()} | sym {out['symbol'].nunique()} | {OUT}")
    for f in feats:
        print(f"  {f}: non-null {out[f].notna().mean()*100:.1f}% | mean {out[f].mean():.4f} | std {out[f].std():.4f}")


if __name__ == "__main__":
    main()
