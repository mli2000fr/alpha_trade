import pandas as pd

from scripts.research.us_feature_combination_d10 import build_scores, pick


def test_equal_blocks_neutral_news_and_selection_ignore_labels():
    day = pd.Timestamp("2025-01-02")
    pool = pd.DataFrame({"date": [day]*3, "symbol": ["A", "B", "C"],
                         "momentum_120": [1,2,3], "rolling_volatility_60": [3,2,1],
                         "atr20_pct": [3,2,1], "oracle_decile": [10,1,5]})
    news = pd.DataFrame({"date": [day]*2, "symbol": ["A", "A"], "positive_score": [.99,.91]})
    data = build_scores(pool, news)
    assert data.loc[data.symbol.eq("A"), "positive_daily_min"].iloc[0] == .91
    assert data.loc[data.symbol.eq("B"), "S"].iloc[0] == .5
    assert (data.MVS == (data.M + data.V + data.S)/3).all()
    assert pick(data, "M", .1).symbol.tolist() == ["C"]
    changed = data.copy()
    changed["oracle_decile"] = [1,10,10]
    assert pick(changed, "M", .1).symbol.tolist() == ["C"]


def test_ceiling_and_symbol_tie_break():
    data = pd.DataFrame({"date": pd.to_datetime(["2025-01-02"]*3),
                         "symbol": ["C", "A", "B"], "M": [.5]*3})
    assert pick(data, "M", .2).symbol.tolist() == ["A"]
