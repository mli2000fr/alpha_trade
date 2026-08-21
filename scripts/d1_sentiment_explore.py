"""D1 — exploration sentiment (ticker_daily_sentiment_features) sur le pool Oracle.

Vérifie : schéma réel, couverture temporelle, disponibilité PIT sur les (date, symbol)
du pool Oracle extrême (TOP/BOTTOM WF causal).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from database.connection import get_sqlalchemy_engine

ROOT = Path(__file__).resolve().parents[1]
TOP_PQ = ROOT / "artifacts" / "models" / "oracle" / "oracle-wf-20260818021140" / "oos_predictions.parquet"


def main() -> None:
    eng = get_sqlalchemy_engine()
    with eng.connect() as c:
        cols = c.execute(text(
            "SELECT COLUMN_NAME, DATA_TYPE FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME='ticker_daily_sentiment_features' "
            "ORDER BY ORDINAL_POSITION"
        )).fetchall()
        print("=== colonnes ===")
        for r in cols:
            print(f"  {r[0]} ({r[1]})")

        cnt = c.execute(text(
            "SELECT COUNT(*), MIN(trade_date), MAX(trade_date) FROM ticker_daily_sentiment_features"
        )).fetchone()
        print(f"=== volume: {cnt[0]:,} lignes | {cnt[1]} -> {cnt[2]}")

        # couverture par an (dans la fenêtre du pool Oracle)
        cnt_by_year = c.execute(text(
            "SELECT YEAR(trade_date), COUNT(*), COUNT(DISTINCT symbol) "
            "FROM ticker_daily_sentiment_features "
            "WHERE trade_date BETWEEN '2021-12-01' AND '2026-06-30' GROUP BY YEAR(trade_date) ORDER BY 1"
        )).fetchall()
        print("=== lignes/symboles par an ===")
        for r in cnt_by_year:
            print(f"  {r[0]}: {r[1]:,} lignes, {r[2]} symboles")

        # colonnes non-null par an (exemple sentiment_net_mean_1d, major_event_flag)
        nn = c.execute(text(
            "SELECT YEAR(trade_date), COUNT(*), "
            "SUM(sentiment_net_mean_1d IS NOT NULL), SUM(major_event_flag IS NOT NULL), "
            "SUM(news_count_1d IS NOT NULL) "
            "FROM ticker_daily_sentiment_features "
            "WHERE trade_date BETWEEN '2021-12-01' AND '2026-06-30' GROUP BY YEAR(trade_date) ORDER BY 1"
        )).fetchall()
        print("=== non-null par an (net_1d, major_event, news_1d) ===")
        for r in nn:
            print(f"  {r[0]}: total={r[1]:,} net_1d={r[2]:,} major_event={r[3]:,} news_1d={r[4]:,}")


if __name__ == "__main__":
    main()
