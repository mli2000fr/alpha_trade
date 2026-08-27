"""modelFactory/directional_data_research/news_sentiment.py — Famille news sentiment.

Priorité 2 du plan. Source : ``news_ticker_sentiment`` (FinBERT contextualisé)
JOIN ``news_raw`` pour la date de publication PIT.

Features à J (news publiées ≤ J, alignées sur ``effective_trade_date``) :
- ``news_net_1d``  : somme ``sentiment_net_score`` du jour ;
- ``news_net_5d`` / ``news_net_10d`` : somme glissante 5/10 jours ;
- ``news_count_5d`` : nombre d'articles 5 jours ;
- ``news_pos_ratio_5d`` / ``news_neg_ratio_5d`` : part positive/négative 5 jours ;
- ``news_last_net`` : ``net_score`` du dernier article connu à J (PIT).

Discipline : harnais de séparabilité AVANT tout modèle (IC décile, AUC
D1-D5 vs D6-D10, AUC D1-D3 vs D8-D10, stabilité du signe par fold, direction vs
amplitude).

Usage :
    python -m modelFactory.directional_data_research.news_sentiment --batch-id ...
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from modelFactory.directional_data_research.harness import (
    analyze_features,
    assemble_pool,
    format_report,
)
from modelFactory.global_direction.config import resolve_global_direction_batch_id

LOGGER = logging.getLogger(__name__)

_NEWS_FEATURES = [
    "news_net_1d", "news_net_5d", "news_net_10d",
    "news_count_5d", "news_pos_ratio_5d", "news_neg_ratio_5d", "news_last_net",
]


def load_sentiment_daily(engine: Any, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    """Sentiment FinBERT agrégé par (symbol, jour effectif), PIT."""
    query = text(
        """
        SELECT nts.symbol, nr.effective_trade_date AS date, nts.sentiment_net_score,
               nts.sentiment_label
        FROM news_ticker_sentiment nts
        JOIN news_raw nr ON nr.article_id = nts.article_id
        WHERE nts.symbol IN :syms
          AND nr.effective_trade_date IS NOT NULL
          AND nr.effective_trade_date >= :start AND nr.effective_trade_date <= :end
        """
    ).bindparams(bindparam("syms", expanding=True))
    with engine.connect() as conn:
        try:
            df = pd.read_sql(query, conn, params={"syms": symbols, "start": start_date, "end": end_date})
        except Exception as exc:
            LOGGER.warning("load_sentiment_daily failed: %s", exc)
            return pd.DataFrame()
    if df.empty:
        return df
    df["symbol"] = df["symbol"].astype(str).str.upper()
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
    df["sentiment_net_score"] = pd.to_numeric(df["sentiment_net_score"], errors="coerce")
    df = df.dropna(subset=["date", "symbol", "sentiment_net_score"])
    daily = df.groupby(["symbol", "date"]).agg(
        net_sum=("sentiment_net_score", "sum"),
        count=("sentiment_net_score", "size"),
        pos=("sentiment_label", lambda s: (s == "positive").sum()),
        neg=("sentiment_label", lambda s: (s == "negative").sum()),
    ).reset_index()
    return daily


def build_news_features(pool: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    """Calcule les features news (fenêtres glissantes PIT) sur l'univers du pool."""
    out = pool[["date", "symbol"]].copy()
    if daily.empty:
        for c in _NEWS_FEATURES:
            out[c] = np.nan
        return out
    merged = out.merge(daily, on=["date", "symbol"], how="left")
    merged = merged.sort_values(["symbol", "date"]).reset_index(drop=True)
    for c in ["net_sum", "count", "pos", "neg"]:
        if c not in merged.columns:
            merged[c] = 0
        merged[c] = merged.groupby("symbol")[c].fillna(0)

    grp = merged.groupby("symbol")
    merged["news_net_1d"] = merged["net_sum"]
    merged["news_net_5d"] = grp["net_sum"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    merged["news_net_10d"] = grp["net_sum"].transform(lambda s: s.rolling(10, min_periods=1).sum())
    merged["news_count_5d"] = grp["count"].transform(lambda s: s.rolling(5, min_periods=1).sum())
    cnt5 = merged["news_count_5d"].replace(0, np.nan)
    merged["news_pos_ratio_5d"] = grp["pos"].transform(lambda s: s.rolling(5, min_periods=1).sum()) / cnt5
    merged["news_neg_ratio_5d"] = grp["neg"].transform(lambda s: s.rolling(5, min_periods=1).sum()) / cnt5
    tmp = merged.copy()
    tmp["_net_if_news"] = np.where(merged["count"] > 0, merged["net_sum"], np.nan)
    merged["news_last_net"] = tmp.groupby("symbol")["_net_if_news"].ffill()
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="Séparabilité famille news sentiment (pool Oracle TOP20%).")
    parser.add_argument("--batch-id", default=None)
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument("--end-date", default="2026-05-29")
    parser.add_argument("--symbols", type=int, default=None)
    parser.add_argument("--oracle-run", default=None)
    parser.add_argument("--top-n", type=int, default=12)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    batch_id = args.batch_id or resolve_global_direction_batch_id()
    if not batch_id:
        raise SystemExit("Aucun batch_id résolu.")

    engine = get_sqlalchemy_engine()
    pool = assemble_pool(engine, batch_id, start_date=args.start_date, end_date=args.end_date,
                         oracle_run=args.oracle_run)
    if pool.empty:
        raise SystemExit("Pool Oracle vide.")
    symbols = list(pool["symbol"].unique())
    if args.symbols:
        symbols = symbols[: args.symbols]
        pool = pool[pool["symbol"].isin(symbols)]
    LOGGER.info("pool Oracle top20%% : %d lignes, %d dates, %d symboles",
                len(pool), pool["date"].nunique(), len(symbols))

    daily = load_sentiment_daily(engine, symbols, args.start_date, args.end_date)
    LOGGER.info("sentiment daily : %d lignes (sur %d symboles)",
                len(daily), daily["symbol"].nunique() if not daily.empty else 0)
    feats = build_news_features(pool, daily)
    merged = pool.merge(feats, on=["date", "symbol"], how="left")
    LOGGER.info("features news fusionnées : %d lignes", len(merged))

    avail = [c for c in _NEWS_FEATURES if c in merged.columns]
    result = analyze_features(merged, avail)
    out_path = Path("artifacts/directional_data_research_news.csv")
    result.to_csv(out_path, index=False)
    print(f"→ CSV : {out_path}")
    print(format_report(result, top_n=args.top_n))


if __name__ == "__main__":
    main()
