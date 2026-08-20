"""E4-B2C — construction des features news structurelles (PIT, univers 400).

Source : ticker_daily_sentiment_features (pré-agrégée par (symbol, trade_date)).
trade_date = effective_trade_date (PIT via TradingCalendarAligner : pre_market ->
jour même ; regular/post_market -> jour de trading suivant ; weekend -> prochain
jour de trading). => zéro look-ahead garanti par construction.

La table ne contient QUE les jours avec >= 1 article (news_count_1d=0 absent).
=> LEFT JOIN du pool + remplissage NaN -> 0 (pas de news ce jour-là).

Features structurelles (le sentiment net est EXCLU — condamné en D1) :
  news_count_1d/3d/5d/10d/20d         = burst (nb articles, fenêtres)
  major_event_flag, major_event_day_count_3d/5d/10d/20d
  source_diversity_count
  after_close_news_count, pre_market_news_count
  relevance_weight_sum_1d/3d/5d/20d
Dérivées :
  news_accel_1_5   = news_count_1d - news_count_5d/5   (accélération courte)
  news_burst_ratio = news_count_1d / (news_count_20d/20) (ratio vs base 20j)
  major_recent_5d  = major_event_day_count_5d
  prepost_ratio    = (pre_market+after_close) / max(news_count_1d,1)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

OUT = Path("artifacts/models/oracle/e4b2c_news_features.parquet")
DATA = Path("artifacts/models/oracle/e2_feature_dataset.parquet")
TICKET = Path("config/ticket_recherche.txt")

BASE_COLS = [
    "news_count_1d", "news_count_3d", "news_count_5d", "news_count_10d", "news_count_20d",
    "major_event_flag", "major_event_day_count_3d", "major_event_day_count_5d",
    "major_event_day_count_10d", "major_event_day_count_20d",
    "source_diversity_count", "after_close_news_count", "pre_market_news_count",
    "relevance_weight_sum_1d", "relevance_weight_sum_3d", "relevance_weight_sum_5d",
    "relevance_weight_sum_20d",
]

FEATS = BASE_COLS + [
    "news_accel_1_5", "news_burst_ratio", "major_recent_5d", "prepost_ratio",
]


def main() -> None:
    ticket = sorted({s.strip().upper() for s in TICKET.read_text(encoding="utf-8").split(",") if s.strip()})
    eng = get_sqlalchemy_engine()
    nws = pd.read_sql(
        text("SELECT symbol, trade_date, " + ", ".join(BASE_COLS) +
             " FROM ticker_daily_sentiment_features "
             "WHERE trade_date BETWEEN '2021-11-01' AND '2026-06-30'"),
        eng)
    nws["trade_date"] = pd.to_datetime(nws["trade_date"]).dt.normalize()
    nws["symbol"] = nws["symbol"].astype(str).str.upper()
    nws = nws[nws["symbol"].isin(set(ticket))].reset_index(drop=True)
    print(f"news table: {len(nws):,} lignes | {nws['trade_date'].min().date()} -> {nws['trade_date'].max().date()} | sym {nws['symbol'].nunique()}")

    # dérivées
    nws["news_accel_1_5"] = nws["news_count_1d"] - nws["news_count_5d"] / 5.0
    nws["news_burst_ratio"] = nws["news_count_1d"] / (nws["news_count_20d"] / 20.0).clip(lower=1e-9)
    nws["major_recent_5d"] = nws["major_event_day_count_5d"]
    nws["prepost_ratio"] = (nws["pre_market_news_count"] + nws["after_close_news_count"]) / nws["news_count_1d"].clip(lower=1)
    nws = nws.rename(columns={"trade_date": "date"})

    # grille du pool Oracle (date, symbol) >= 2022
    ds = pd.read_parquet(DATA, columns=["date", "symbol"])
    ds["date"] = pd.to_datetime(ds["date"]).dt.normalize()
    ds["symbol"] = ds["symbol"].astype(str).str.upper()
    grid = ds[ds["date"] >= "2022-01-01"][["date", "symbol"]].drop_duplicates().reset_index(drop=True)

    # LEFT JOIN : jours sans news -> NaN -> 0
    out = grid.merge(nws[["date", "symbol"] + FEATS], on=["date", "symbol"], how="left")
    for f in FEATS:
        out[f] = out[f].fillna(0.0).astype(float)
    out.to_parquet(OUT, index=False)
    print(f"features pool: {len(out):,} lignes | {out['date'].min().date()} -> {out['date'].max().date()} | sym {out['symbol'].nunique()} | {OUT}")
    for f in FEATS:
        nz = (out[f] != 0).mean() * 100
        print(f"  {f}: non-zero {nz:.1f}% | mean {out[f].mean():.3f} | std {out[f].std():.3f}")


if __name__ == "__main__":
    main()
