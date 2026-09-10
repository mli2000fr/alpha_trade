from __future__ import annotations

import pandas as pd

from modelFactory.directional_data_research.close_exhaustion_confirmation import (
    exhaustion_feature, select_disjoint_events,
)
from modelFactory.directional_data_research.signed_flow_pilot import _event_hash


def test_exhaustion_feature_has_prefixed_contrarian_sign() -> None:
    trades = pd.DataFrame({
        "sip_timestamp": [1_700_000_000_000_000_000, 1_700_000_001_000_000_000],
        "price": [100.0, 98.0], "size": [10, 10],
    })
    result = exhaustion_feature(trades)
    assert result["return_5m"] < 0
    assert result["exhaustion_score"] > 0


def test_select_disjoint_events_excludes_all_discovery_dates() -> None:
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    gate = pd.DataFrame({
        "date": dates, "symbol": ["AA", "BB", "CC"],
        "directional_oracle_eligible": True, "directional_oracle_oof_available": True,
    })
    excluded = pd.DataFrame({"date": [dates[0]], "symbol": ["ZZ"]})
    selected = select_disjoint_events(gate, excluded, start_date="2024-01-01", end_date="2024-12-31", count=10)
    assert set(selected["date"]) == {dates[1], dates[2]}


def test_select_disjoint_events_uses_hash_not_first_symbol() -> None:
    date = pd.Timestamp("2024-02-01")
    symbols = ["AA", "ZZ"]
    gate = pd.DataFrame({
        "date": [date, date], "symbol": symbols,
        "directional_oracle_eligible": True, "directional_oracle_oof_available": True,
    })
    selected = select_disjoint_events(
        gate, pd.DataFrame({"date": pd.to_datetime([]), "symbol": []}),
        start_date="2024-01-01", end_date="2024-12-31", count=1,
    )
    expected = min(symbols, key=lambda symbol: _event_hash(date, symbol))
    assert selected.iloc[0]["symbol"] == expected
