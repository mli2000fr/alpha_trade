import pandas as pd

from modelFactory.us_atr_oracle_realized_audit import compare, compare_sentiment_at_j


def test_deciles_are_not_recomputed_inside_selection_and_invalid_rows_preserved():
    day = pd.Timestamp("2025-01-02")
    panel = pd.DataFrame({"date": [day]*10, "symbol": list("ABCDEFGHIJ"),
                          "proba_extreme": range(10), "atr": range(10)})
    labels = pd.DataFrame({"prediction_date": [day]*10, "symbol": list("ABCDEFGHIJ"),
                           "target_quality_valid": [1]*9+[0], "oracle_decile": list(range(1,10))+[None],
                           "oracle_extreme10": [1]+[0]*8+[None]})
    result = compare(panel, labels, "atr")
    intersection = result["INTERSECTION"]
    assert intersection["selected"] == 3
    assert intersection["unknown_or_invalid_labels"] == 1
    assert intersection["decile_counts"]["8"] == 1
    assert intersection["decile_counts"]["9"] == 1
    assert intersection["d1_or_d10_percent"] == 0


def test_sentiment_precision_recall_and_conflicting_news_are_distinct():
    day = pd.Timestamp("2025-01-02")
    windows = pd.DataFrame({"date": [day]*4, "symbol": list("ABCD"),
                            "intersection": [True, True, True, False],
                            "positive_lag0": [True, True, False, True],
                            "negative_lag0": [False, True, True, False]})
    labels = pd.DataFrame({"prediction_date": [day]*4, "symbol": list("ABCD"),
                           "target_quality_valid": [1]*4, "oracle_decile": [10, 1, 10, 10]})
    result = compare_sentiment_at_j(windows, labels)["groups"]
    assert result["POSITIVE_AT_J"]["selected"] == 2
    assert result["POSITIVE_AT_J"]["decile_percent"]["10"] == 50
    assert result["POSITIVE_AT_J"]["coverage_of_intersection_decile_pct"]["10"] == 50
    assert result["NEGATIVE_AT_J"]["coverage_of_intersection_decile_pct"]["1"] == 100
    assert result["BOTH_AT_J"]["selected"] == 1
    assert result["POSITIVE_ONLY_AT_J"]["selected"] == 1
