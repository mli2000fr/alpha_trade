"""Read-only 2025 all-article sentiment plus five moving-average conditions."""
import hashlib
import json
from pathlib import Path

import pandas as pd
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine
from modelFactory.features import _build_adjusted_price_frame
from modelFactory.us_atr_oracle_realized_audit import compare_sentiment_at_j
from scripts.research.us_intersection_sentiment_deciles import ROOT, all_articles_four_sessions


def moving_average_flags(bars):
    if bars.duplicated(["symbol", "date"]).any():
        raise ValueError("Multiple bars per symbol/date")
    data = bars.sort_values(["symbol", "date"]).reset_index(drop=True).copy()
    data["price"] = _build_adjusted_price_frame(data)["close"]
    columns = []
    for period in (5, 10, 20, 50, 100):
        name = f"sma{period}"
        columns.append(name)
        data[name] = data.groupby("symbol").price.transform(lambda x: x.rolling(period, min_periods=period).mean())
    data["sma_valid"] = data[columns].notna().all(axis=1) & data.price.gt(0)
    data["above_all"] = data[columns].lt(data.price, axis=0).all(axis=1) & data.sma_valid
    data["below_all"] = data[columns].gt(data.price, axis=0).all(axis=1) & data.sma_valid
    return data


def main():
    sources = {"windows": ROOT / "audit-20261004-v1/symbol_day_windows.parquet",
               "news": ROOT / "audit-20261004-v1/news_observations.parquet",
               "labels": ROOT / "intersection-realized-20261004-v1/native_realized_labels.parquet"}
    windows = pd.read_parquet(sources["windows"])
    news = pd.read_parquet(sources["news"])
    labels = pd.read_parquet(sources["labels"])
    labels["prediction_date"] = pd.to_datetime(labels.prediction_date)
    symbols = sorted(windows.loc[windows.intersection, "symbol"].unique())
    engine = get_sqlalchemy_engine()
    query = text("SELECT symbol,date,close,adj_close,data_source AS source FROM stock_bars_daily "
                 "WHERE symbol IN :symbols AND date BETWEEN '2024-01-01' AND '2025-12-31'").bindparams(bindparam("symbols", expanding=True))
    parts = []
    with engine.connect() as conn:
        if conn.execute(text("SELECT DATABASE()")).scalar() != "alpha_trade":
            raise ValueError("US database required")
        for offset in range(0, len(symbols), 300):
            parts.append(pd.read_sql(query, conn, params={"symbols": symbols[offset:offset+300]}))
    bars = pd.concat(parts, ignore_index=True)
    if set(bars.source.unique()) != {"eodhd_eod"}:
        raise ValueError("Unexpected price source")
    bars["date"] = pd.to_datetime(bars.date)
    features = moving_average_flags(bars)
    selected = all_articles_four_sessions(windows, news, lags=(0,)).merge(
        features[["symbol", "date", "price", "sma5", "sma10", "sma20", "sma50", "sma100",
                  "sma_valid", "above_all", "below_all"]], on=["symbol", "date"], how="left", validate="one_to_one")
    sentiment_only = compare_sentiment_at_j(selected, labels)
    selected["positive_lag0"] &= selected.above_all.eq(True)
    selected["negative_lag0"] &= selected.below_all.eq(True)
    result = compare_sentiment_at_j(selected, labels)
    result.update(year=2025, horizon=20, threshold_strict=.9, periods=[5, 10, 20, 50, 100],
                  positive_condition="price > every SMA", negative_condition="price < every SMA",
                  sma_includes_j=True, sql_writes=False, models_refit=False,
                  intersection_missing_sma=int((selected.intersection & ~selected.sma_valid.eq(True)).sum()),
                  sentiment_only=sentiment_only["groups"],
                  sources={key: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                           for key, path in sources.items()},
                  notes=["All successfully scored articles at J >0.9; unscored articles not in archive",
                         "Adjusted close and simple rolling means including J; strict inequalities",
                         "Deciles from full daily universe; retrospective sentiment PIT not certified",
                         "Correlated symbol/day observations, not independent trades; no economic replay"])
    output = ROOT / "intersection-all-j-09-sma5to100-20261004-v1"
    output.mkdir(parents=True, exist_ok=False)
    selected.to_parquet(output / "selection_panel.parquet", index=False)
    result["selection_sha256"] = hashlib.sha256((output / "selection_panel.parquet").read_bytes()).hexdigest()
    (output / "report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("sentiment_only", "sources")}))


if __name__ == "__main__":
    main()
