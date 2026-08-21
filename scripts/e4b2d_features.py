"""E4-B2D — construction des features fundamentals PIT (univers 400).

Source : stock_fundamentals_daily (valeurs trimestrielles ~18/symbole sur 4.5 ans).
PIT STRICT : merge_asof backward sur trade_date (dernière valeur connue <= date D
du pool). Aucun look-ahead.

Features :
  fund_pe_ratio, fund_forward_pe, fund_pb_ratio, fund_ps_ratio
  fund_eps_growth_yoy, fund_revenue_growth_yoy, fund_net_margin, fund_roe
  fund_debt_to_equity, fund_dividend_yield, fund_market_cap_log, fund_beta
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

OUT = Path("artifacts/models/oracle/e4b2d_fundamentals_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
TICKET = Path("config/ticket_recherche.txt")

FUND_COLS = ["pe_ratio", "forward_pe", "pb_ratio", "ps_ratio",
             "eps_growth_yoy", "revenue_growth_yoy", "net_margin", "roe",
             "debt_to_equity", "dividend_yield", "market_cap", "beta"]
FEATS = ["fund_" + c for c in FUND_COLS] + ["fund_market_cap_log"]


def main() -> None:
    ticket = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})
    eng = get_sqlalchemy_engine()
    f = pd.read_sql(text(
        "SELECT symbol, trade_date, " + ", ".join(FUND_COLS) +
        " FROM stock_fundamentals_daily WHERE trade_date BETWEEN '2021-06-01' AND '2026-06-30'"),
        eng)
    f["trade_date"] = pd.to_datetime(f["trade_date"]).dt.normalize()
    f["symbol"] = f["symbol"].astype(str).str.upper()
    f = f[f["symbol"].isin(set(ticket))].reset_index(drop=True)
    print(f"fundamentals: {len(f):,} lignes | {f['trade_date'].min().date()} -> {f['trade_date'].max().date()} | sym {f['symbol'].nunique()}")

    # market_cap log
    f["market_cap_log"] = np.log1p(f["market_cap"].clip(lower=0))
    f = f.rename(columns={c: "fund_" + c for c in FUND_COLS} | {"market_cap_log": "fund_market_cap_log"})
    f = f[["symbol", "trade_date"] + FEATS]

    # grille du pool (date, symbol) >= 2022
    ds = pd.read_parquet(DATA, columns=["date", "symbol"])
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    ds["symbol"] = ds["symbol"].astype(str).str.upper()
    grid = ds[ds["date"] >= "2022-01-01"][["date", "symbol"]].drop_duplicates().reset_index(drop=True)

    # PIT : dernière valeur connue <= date
    out = pd.merge_asof(
        grid.sort_values("date"),
        f.rename(columns={"trade_date": "date"}).sort_values("date"),
        on="date", by="symbol", direction="backward")
    out.to_parquet(OUT, index=False)
    print(f"features pool: {len(out):,} lignes | {out['date'].min().date()} -> {out['date'].max().date()} | sym {out['symbol'].nunique()} | {OUT}")
    for c in FEATS:
        print(f"  {c}: non-null {out[c].notna().mean()*100:.1f}%")


if __name__ == "__main__":
    main()
