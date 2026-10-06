import pandas as pd

from scripts.research.us_intersection_sentiment_deciles import all_articles_four_sessions, top_daily


def test_all_articles_and_four_nonempty_sessions_required():
    windows = pd.DataFrame({"date": pd.to_datetime(["2025-01-02"] * 3),
                            "session": [7] * 3, "symbol": ["PASS", "LOW", "MISSING"]})
    rows = []
    for symbol in windows.symbol:
        for day in ["2024-12-27", "2024-12-30", "2024-12-31", "2025-01-02"]:
            if symbol == "MISSING" and day == "2024-12-30":
                continue
            rows.append({"symbol": symbol, "date": pd.Timestamp(day),
                         "positive_score": .95, "negative_score": .01})
    rows.append({"symbol": "LOW", "date": pd.Timestamp("2024-12-30"),
                 "positive_score": .9, "negative_score": .01})
    result = all_articles_four_sessions(windows, pd.DataFrame(rows))
    assert result.positive_lag0.tolist() == [True, False, False]
    assert not result.negative_lag0.any()
    same_day = all_articles_four_sessions(windows, pd.DataFrame(rows), lags=(0,))
    assert same_day.positive_lag0.tolist() == [True, True, True]


def test_same_day_rejects_one_low_article_and_missing_score():
    windows = pd.DataFrame({"date": pd.to_datetime(["2025-01-02"] * 4),
                            "session": [7] * 4, "symbol": ["PASS", "LOW", "NULL", "EMPTY"]})
    news = pd.DataFrame({"symbol": ["PASS", "LOW", "LOW", "NULL"],
                         "date": pd.to_datetime(["2025-01-02"] * 4),
                         "positive_score": [.95, .99, .9, None],
                         "negative_score": [.01] * 4})
    result = all_articles_four_sessions(windows, news, lags=(0,))
    assert result.positive_lag0.tolist() == [True, False, False, False]


def test_strict_095_and_daily_top_rank_use_minimum_not_maximum():
    day = pd.Timestamp("2025-01-02")
    windows = pd.DataFrame({"date": [day] * 4, "session": [7] * 4,
                            "symbol": ["A", "B", "BOUNDARY", "OUTSIDE"],
                            "intersection": [True, True, True, False]})
    news = pd.DataFrame({"date": [day] * 5,
                         "symbol": ["A", "A", "B", "BOUNDARY", "OUTSIDE"],
                         "positive_score": [.999, .96, .98, .95, .9999],
                         "negative_score": [.001] * 5})
    qualified = all_articles_four_sessions(windows, news, lags=(0,), threshold=.95)
    assert qualified.positive_lag0.tolist() == [True, True, False, True]
    ranked = top_daily(qualified, news, count=1)
    assert ranked.positive_lag0.tolist() == [False, True, False, False]
