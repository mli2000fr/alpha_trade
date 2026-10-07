from __future__ import annotations

import pandas as pd
import pytest

from service.market.cn_dragon_tiger_coverage_15d4 import (
    assign_availability, join_coverage, resolve_events, summarize,
)


def test_historical_mapping_and_unmapped_are_explicit():
    rows = pd.DataFrame([
        {"trade_date": "2024-01-02", "market": "SH", "security_code": "600001"},
        {"trade_date": "2024-01-03", "market": "SH", "security_code": "600001"},
    ])
    mapping = pd.DataFrame([
        {"provider_symbol": "sh.600001", "instrument_id": 7,
         "valid_from": "2024-01-03", "valid_to": None},
    ])
    events, stats = resolve_events(rows, mapping)
    assert stats["mapped_events"] == 1
    assert stats["unmapped_events"] == 1
    assert events.iloc[0]["trade_date"] == pd.Timestamp("2024-01-03")


def test_same_day_forbidden_and_jplus1_jplus2():
    sessions = pd.DatetimeIndex(pd.to_datetime(
        ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]))
    events = pd.DataFrame([{"trade_date": pd.Timestamp("2024-01-02"),
                            "instrument_id": 7}])
    with pytest.raises(ValueError, match="Same-day"):
        assign_availability(events, sessions, 0)
    top = pd.DataFrame([
        {"session_date": day, "instrument_id": 7, "semester": "2024H1",
         "board_code": "MAIN", "oracle_decile": 10}
        for day in sessions])
    j1 = join_coverage(top, events, sessions, 1)
    j2 = join_coverage(top, events, sessions, 2)
    assert pd.isna(j1.iloc[0]["age_sessions"])
    assert j1["age_sessions"].tolist()[1:] == [1.0, 2.0, 3.0]
    assert pd.isna(j2.iloc[1]["age_sessions"])
    assert j2.iloc[2]["age_sessions"] == 2
    assert summarize(j1, 1)["overall"]["event_within_5_sessions"] == 3
    assert summarize(j2, 2)["overall"]["event_within_5_sessions"] == 2
