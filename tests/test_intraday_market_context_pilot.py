from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.directional_data_research.intraday_market_context_pilot import (
    build_market_features, daily_asset_features,
)


def test_daily_asset_features_uses_regular_session() -> None:
    start = pd.Timestamp("2021-06-01T13:30:00Z")
    bars = pd.DataFrame({
        "t": [int((start + pd.Timedelta(minutes=5 * index)).timestamp() * 1000) for index in range(78)],
        "o": [100.0 + index * 0.1 for index in range(78)],
        "c": [100.1 + index * 0.1 for index in range(78)],
    })
    result = daily_asset_features(bars, "SPY")
    assert len(result) == 1
    assert result.iloc[0]["spy_return"] > 0
    assert result.iloc[0]["spy_bars"] == 78


def test_build_market_features_has_prefixed_risk_on_formula() -> None:
    date = pd.Timestamp("2021-06-01")
    frames = {}
    values = {"SPY": (0.01, 0.02), "QQQ": (0.02, 0.03), "IWM": (0.00, 0.04), "VXX": (-0.03, 0.05)}
    for symbol, (ret, vol) in values.items():
        frames[symbol] = pd.DataFrame({
            "date": [date], f"{symbol.lower()}_return": [ret],
            f"{symbol.lower()}_realized_vol": [vol], f"{symbol.lower()}_bars": [78],
        })
    result = build_market_features(frames).iloc[0]
    assert result["equity_equal_return"] == pytest.approx(0.01)
    assert result["risk_on_return"] == pytest.approx(0.04)
    assert result["qqq_minus_spy_return"] == pytest.approx(0.01)
