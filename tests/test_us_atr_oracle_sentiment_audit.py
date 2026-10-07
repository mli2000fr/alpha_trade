import pandas as pd
import pytest

from modelFactory.us_atr_oracle_sentiment_audit import news_windows, overlap


def panel():
    return pd.DataFrame({"date": [pd.Timestamp("2025-01-02")]*10,
                         "symbol": list("ABCDEFGHIJ"), "atr": range(10),
                         "proba_extreme": range(10)})


def test_identical_ranks_have_full_overlap():
    _, result = overlap(panel(), "atr")
    assert result["summary"]["pooled_overlap"] == 1
    assert result["summary"]["days_at_least_90pct"] == 1


def test_reverse_ranks_do_not_overlap_and_duplicates_fail():
    values = panel()
    values["proba_extreme"] = list(reversed(range(10)))
    _, result = overlap(values, "atr")
    assert result["summary"]["shared_symbol_days"] == 0
    with pytest.raises(ValueError, match="Duplicate"):
        overlap(pd.concat([values, values]), "atr")


def test_news_lag_orientation_strict_threshold_and_article_dedup():
    data, _ = overlap(panel(), "atr")
    dates = pd.bdate_range("2024-12-30", "2025-01-08").tolist()
    news = pd.DataFrame({"symbol": ["J", "J", "A"], "article_id": ["x", "x", "y"],
                         "date": [pd.Timestamp("2025-01-03")]*3,
                         "positive_score": [.95, .95, .9], "negative_score": [.01]*3})
    enriched, results = news_windows(data, news, dates)
    after = next(x for x in results if x["side"] == "positive" and x["window"] == "after_only")
    before = next(x for x in results if x["side"] == "positive" and x["window"] == "before_only")
    assert after["symbol_days_with_strong_news"] == 1
    assert after["p_oracle_top_given_strong_news"] == 1
    assert not after["predictive_window"]
    assert before["symbol_days_with_strong_news"] == 0
    assert enriched.loc[enriched.symbol.eq("J"), "positive_lag1"].all()
