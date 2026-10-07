import numpy as np
import pandas as pd

from modelFactory.oracle_d10_trajectory_e23 import (
    TARGET, add_path_summaries, attach_d10_one_vs_rest,
    attach_exact_session_lags,
)


def test_d10_one_vs_rest_keeps_middle_deciles_as_negatives():
    result = attach_d10_one_vs_rest(pd.DataFrame({"oracle_decile": [1, 2, 9, 10, np.nan]}))
    assert result[TARGET].iloc[:4].tolist() == [0.0, 0.0, 0.0, 1.0]
    assert np.isnan(result[TARGET].iloc[4])


def test_exact_lags_use_global_sessions_not_sparse_pool_appearances():
    dates = pd.bdate_range("2025-01-01", periods=5)
    history = pd.DataFrame({"date": dates, "symbol": "A", "score": [1, 2, 3, 4, 5]})
    pool = history.iloc[[2, 4]][["date", "symbol"]].copy()
    result, columns = attach_exact_session_lags(
        pool, history, ["score"], max_lag=2, prefix="x",
        session_map={date: index for index, date in enumerate(dates)}, include_current=False,
    )
    assert columns == ["x_score_lag1", "x_score_lag2"]
    assert result.loc[0, "x_score_lag1"] == 2
    assert result.loc[1, "x_score_lag1"] == 4
    assert result.loc[1, "x_score_lag2"] == 3


def test_missing_news_is_zero_but_has_news_disambiguates_it():
    dates = pd.bdate_range("2025-01-01", periods=3)
    pool = pd.DataFrame({"date": dates, "symbol": "A"})
    news = pd.DataFrame({"date": [dates[1]], "symbol": ["A"], "sentiment_net_mean": [0.0], "sentiment_has_news": [1.0]})
    result, _ = attach_exact_session_lags(
        pool, news, ["sentiment_net_mean", "sentiment_has_news"], max_lag=0,
        prefix="sent", session_map={date: index for index, date in enumerate(dates)},
        include_current=True, fill_zero_columns={"sentiment_net_mean", "sentiment_has_news"},
    )
    assert result["sent_sentiment_net_mean_lag0"].tolist() == [0.0, 0.0, 0.0]
    assert result["sent_sentiment_has_news_lag0"].tolist() == [0.0, 1.0, 0.0]


def test_path_summary_respects_j_minus_2_to_j_order():
    result, names = add_path_summaries(
        pd.DataFrame({"x2": [1.0], "x1": [2.0], "x0": [4.0]}),
        source="x", ordered_columns=["x2", "x1", "x0"], prefix="p")
    assert len(names) == 5
    assert result.loc[0, "p_x_delta"] == 3.0
    assert result.loc[0, "p_x_slope"] == 1.5
