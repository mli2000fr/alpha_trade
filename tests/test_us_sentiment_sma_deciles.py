import pandas as pd

from scripts.research.us_sentiment_sma_deciles import moving_average_flags


def test_all_five_means_strict_and_warmup():
    dates = pd.bdate_range("2024-01-01", periods=110)
    bars = pd.concat([pd.DataFrame({"symbol": name, "date": dates, "close": values,
                                   "adj_close": values})
                      for name, values in [("UP", range(1, 111)), ("DOWN", range(110, 0, -1)),
                                           ("FLAT", [50] * 110)]], ignore_index=True)
    data = moving_average_flags(bars)
    last = data.groupby("symbol").tail(1).set_index("symbol")
    assert bool(last.loc["UP", "above_all"])
    assert bool(last.loc["DOWN", "below_all"])
    assert not bool(last.loc["FLAT", "above_all"])
    assert not bool(last.loc["FLAT", "below_all"])
    assert not data.groupby("symbol").head(99).sma_valid.any()
