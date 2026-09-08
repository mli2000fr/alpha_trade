from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.directional_data_research.intraday_session_path_pilot import (
    regular_session_bars, select_unique_date_events, session_features,
)


def _bar(timestamp: str, price: float, volume: float = 100.0) -> dict[str, float]:
    return {
        "t": float(pd.Timestamp(timestamp).timestamp() * 1000), "o": price, "h": price + 0.1,
        "l": price - 0.1, "c": price, "v": volume, "vw": price, "n": 10,
    }


def test_regular_session_bars_excludes_extended_hours() -> None:
    bars = pd.DataFrame([
        _bar("2025-01-02T13:00:00Z", 99.0),   # 08:00 ET
        _bar("2025-01-02T14:30:00Z", 100.0),  # 09:30 ET
        _bar("2025-01-02T20:55:00Z", 101.0),  # 15:55 ET
        _bar("2025-01-02T21:30:00Z", 102.0),  # 16:30 ET
    ])
    regular = regular_session_bars(bars)
    assert regular["c"].tolist() == [100.0, 101.0]


def test_session_features_uses_morning_and_afternoon_paths() -> None:
    start = pd.Timestamp("2025-01-02T14:30:00Z")
    bars = pd.DataFrame([
        _bar((start + pd.Timedelta(minutes=5 * index)).isoformat(), 100.0 + index * 0.1)
        for index in range(78)
    ])
    result = session_features(bars)
    assert result["feature_status"] == "complete"
    assert result["regular_bar_count"] == 78
    assert result["morning_return"] > 0
    assert result["afternoon_return"] > 0
    assert result["close_location_session"] == pytest.approx(1.0, abs=0.03)


def test_unique_date_selection_keeps_one_event_per_date() -> None:
    dates = pd.to_datetime(["2020-01-02", "2020-01-02", "2020-07-02", "2020-07-02"])
    gate = pd.DataFrame({
        "date": dates, "symbol": ["AA", "BB", "CC", "DD"],
        "directional_oracle_eligible": True, "directional_oracle_oof_available": True,
    })
    selected = select_unique_date_events(gate, start_date="2020-01-01", end_date="2020-12-31", count=10)
    assert len(selected) == 2
    assert selected["date"].nunique() == 2
