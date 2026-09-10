from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.directional_data_research.tick_price_liquidity_audit import event_features


def test_event_features_builds_price_and_liquidity_family() -> None:
    base = pd.Timestamp("2025-01-02T20:30:00Z")
    ts = [int((base + pd.Timedelta(minutes=value)).value) for value in (0, 25, 29)]
    trades = pd.DataFrame({"sip_timestamp": ts, "price": [100.0, 101.0, 102.0], "size": [10, 20, 30]})
    quotes = pd.DataFrame({
        "sip_timestamp": ts, "bid_price": [99.9, 100.9, 101.9], "ask_price": [100.1, 101.1, 102.1],
    })
    result = event_features(trades, quotes)
    assert result["feature_status"] == "complete"
    assert result["return_30m"] == pytest.approx(0.02)
    assert result["return_5m"] == pytest.approx(102.0 / 101.0 - 1.0)
    assert result["close_location_30m"] == 1.0
    assert result["range_30m"] == pytest.approx(0.02)
    assert result["median_spread_bps"] > 0


def test_event_features_fails_closed_without_quotes() -> None:
    trades = pd.DataFrame({"sip_timestamp": [1], "price": [100.0], "size": [10]})
    result = event_features(trades, pd.DataFrame())
    assert result == {"feature_status": "insufficient", "trade_count": 1, "quote_count": 0}
