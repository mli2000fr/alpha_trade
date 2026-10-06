"""Report same-session strong sentiment inside the frozen US ATR20/Oracle pool."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

from modelFactory.us_atr_oracle_realized_audit import compare_sentiment_at_j

ROOT = Path("artifacts/research/us_atr_oracle_sentiment")


def all_articles_four_sessions(windows, news, lags=(-3, -2, -1, 0), threshold=.9):
    """Every scored article must pass; four nonempty sessions, no score carry."""
    data = windows.copy()
    calendar = data[["date", "session"]].drop_duplicates().set_index("date").session.to_dict()
    # Prior three US sessions for the first evaluated session, 2025-01-02.
    calendar.update({pd.Timestamp("2024-12-27"): 4, pd.Timestamp("2024-12-30"): 5,
                     pd.Timestamp("2024-12-31"): 6})
    if calendar.get(pd.Timestamp("2025-01-02")) != 7:
        raise ValueError("Unexpected archived session calendar")
    news = news.copy()
    news["session"] = pd.to_datetime(news.date).map(calendar)
    for side in ("positive", "negative"):
        news["passes"] = news[f"{side}_score"].gt(threshold).fillna(False)
        daily = news.groupby(["symbol", "session"]).passes.all()
        eligible = set(daily[daily].index)
        data[f"{side}_lag0"] = [all((symbol, int(session)+lag) in eligible for lag in lags)
                                  for symbol, session in zip(data.symbol, data.session, strict=True)]
    return data


def top_daily(windows, news, count=10):
    """Rank qualified intersection members by minimum article score; symbol breaks ties."""
    data = windows.copy()
    news = news.copy()
    news["date"] = pd.to_datetime(news.date)
    for side in ("positive", "negative"):
        daily = news.groupby(["date", "symbol"])[f"{side}_score"].min()
        keys = pd.MultiIndex.from_frame(data[["date", "symbol"]])
        data[f"{side}_daily_min"] = daily.reindex(keys).to_numpy()
        selected = data[data.intersection & data[f"{side}_lag0"]].sort_values(
            ["date", f"{side}_daily_min", "symbol"], ascending=[True, False, True])
        chosen = selected.groupby("date").head(count).index
        data[f"{side}_lag0"] = data.index.isin(chosen)
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--consecutive", action="store_true", help="Require strong sentiment on every session J-3 through J")
    parser.add_argument("--all-articles", action="store_true", help="Require every scored article on every session J-3 through J")
    parser.add_argument("--same-day-only", action="store_true", help="With --all-articles, evaluate session J only")
    parser.add_argument("--threshold", type=float, default=.9)
    parser.add_argument("--top-per-day", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.same_day_only and (not args.all_articles or args.consecutive):
        parser.error("--same-day-only requires --all-articles and excludes --consecutive")
    if not 0 <= args.threshold < 1 or args.top_per_day < 0:
        parser.error("Invalid threshold or top-per-day")
    if (args.threshold != .9 or args.top_per_day) and not (args.all_articles and args.same_day_only):
        parser.error("Custom threshold/ranking requires --all-articles --same-day-only")
    paths = {"windows": ROOT / "audit-20261004-v1/symbol_day_windows.parquet",
             "labels": ROOT / "intersection-realized-20261004-v1/native_realized_labels.parquet"}
    windows = pd.read_parquet(paths["windows"])
    labels = pd.read_parquet(paths["labels"])
    labels["prediction_date"] = pd.to_datetime(labels.prediction_date)
    if args.all_articles:
        paths["news"] = ROOT / "audit-20261004-v1/news_observations.parquet"
        windows = all_articles_four_sessions(windows, pd.read_parquet(paths["news"]),
                                            lags=(0,) if args.same_day_only else (-3, -2, -1, 0), threshold=args.threshold)
        if args.top_per_day:
            windows = top_daily(windows, pd.read_parquet(paths["news"]), args.top_per_day)
    elif args.consecutive:
        for side in ("positive", "negative"):
            windows[f"{side}_lag0"] = windows[[f"{side}_lag{lag}" for lag in range(-3, 1)]].fillna(False).all(axis=1)
    report = compare_sentiment_at_j(windows, labels)
    report["sentiment_sessions_required"] = [-3, -2, -1, 0] if (args.consecutive or args.all_articles) and not args.same_day_only else [0]
    report["article_rule"] = "ALL_SCORED_ARTICLES" if args.all_articles else "DAILY_MAXIMUM"
    report.update(year=2025, atr_period=20, oracle_horizon=20, sentiment_threshold_strict=args.threshold,
                  top_per_day=args.top_per_day, ranking="daily minimum score descending, symbol ascending for ties",
                  sources={k: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                           for k, path in paths.items()},
                  notes=["Positive and negative are maxima across articles per effective session; missing sessions fail",
                         "Groups overlap when both positive and negative strong articles occur",
                         "All archived 2025 sentiment observations have created_at after 2025; retrospective only",
                         "Deciles belong to the full daily universe, not recomputed in selected groups"],
                  sql_writes=False, models_refit=False)
    if args.all_articles:
        report["notes"][0] = "Every successfully scored article must exceed 0.9 on each of four nonempty sessions; missing scores fail. Unscored raw articles not represented in archive."
        if args.same_day_only:
            report["notes"][0] = f"Every successfully scored article at J must exceed {args.threshold}; empty sessions and missing scores fail. Unscored raw articles not represented in archive."
    output = ROOT / ("intersection-sentiment-jminus3-j-20261004-v1" if args.consecutive else "intersection-sentiment-j-20261004-v1")
    if args.all_articles:
        output = ROOT / "intersection-sentiment-all-articles-jminus3-j-20261004-v1"
        if args.same_day_only:
            output = ROOT / "intersection-sentiment-all-articles-j-20261004-v1"
    if args.output:
        output = args.output
    elif args.threshold != .9 or args.top_per_day:
        parser.error("Provide --output for a new threshold/ranking")
    output.mkdir(parents=True, exist_ok=False)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
