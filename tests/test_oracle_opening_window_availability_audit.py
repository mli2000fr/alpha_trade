from __future__ import annotations

from pathlib import Path

import pandas as pd

from modelFactory.oracle_opening_window_availability_audit import (
    E20AConfig,
    attach_next_oracle_session,
    build_report,
    build_symbol_session_coverage,
)


def test_attach_next_oracle_session_uses_next_observed_trading_date() -> None:
    events = pd.DataFrame({
        "date": pd.to_datetime(["2026-09-11", "2026-09-14", "2026-09-14", "2026-09-15"]),
        "symbol": ["A", "A", "B", "A"],
    })
    mapped = attach_next_oracle_session(events)
    assert mapped.loc[mapped["date"].eq(pd.Timestamp("2026-09-11")), "target_session"].iat[0] == pd.Timestamp("2026-09-14")
    assert set(mapped.loc[mapped["date"].eq(pd.Timestamp("2026-09-14")), "target_session"]) == {pd.Timestamp("2026-09-15")}


def test_symbol_session_coverage_counts_exact_open_windows() -> None:
    minutes = pd.date_range("2026-09-14 13:30", periods=30, freq="min")
    rows = pd.DataFrame({
        "session_date": pd.Timestamp("2026-09-14"), "symbol": "A",
        "bar_timestamp": minutes, "minute_of_day": range(570, 600),
        "minute_volume": 10, "trade_count": 2, "invalid_availability": False,
    })
    result = build_symbol_session_coverage(rows).iloc[0]
    assert result["bars_15m"] == 15
    assert result["bars_30m"] == 30
    assert result["bars_60m"] == 30
    assert bool(result["has_open"])
    assert result["volume_total"] == 300


def test_report_blocks_when_table_is_empty() -> None:
    events = pd.DataFrame({
        "date": [pd.Timestamp("2026-09-11")],
        "target_session": [pd.Timestamp("2026-09-14")], "symbol": ["A"],
    })
    report, _, _ = build_report(
        events=events, coverage=build_symbol_session_coverage(pd.DataFrame()),
        global_summary={"exists": True, "rows_count": 0, "by_contract": []},
        recent_runs=[], oracle_path=Path("unused"),
        config=E20AConfig(),
    )
    assert report["verdict"] == "BLOCKED_NO_OPENING_WINDOW_DATA"
    assert not report["rules_experiment_authorized"]
    assert not report["model_experiment_authorized"]


def test_report_authorizes_rules_and_model_after_all_gates() -> None:
    config = E20AConfig(
        minimum_rule_dates=1, minimum_rule_events=1,
        minimum_model_dates=1, minimum_model_events=1, minimum_semesters=1,
        minimum_any_open_coverage=0.5, minimum_30m_coverage=0.5,
        minimum_30m_bars=24,
    )
    events = pd.DataFrame({
        "date": [pd.Timestamp("2026-09-11")],
        "target_session": [pd.Timestamp("2026-09-14")], "symbol": ["A"],
    })
    coverage = pd.DataFrame({
        "session_date": [pd.Timestamp("2026-09-14")], "symbol": ["A"],
        "bars_total": [30], "bars_pre": [0], "bars_open": [30],
        "bars_15m": [15], "bars_30m": [30], "bars_60m": [30],
        "has_pre": [False], "has_open": [True], "has_15m": [True],
        "has_30m": [True], "has_60m": [True], "volume_total": [100],
        "trades_total": [20], "invalid_availability_rows": [0],
    })
    report, _, _ = build_report(
        events=events, coverage=coverage,
        global_summary={"rows_count": 30, "by_contract": [{
            "provider": "alpaca", "feed": "sip", "adjustment_mode": "raw",
        }]}, recent_runs=[], oracle_path=Path("oracle.parquet"),
        config=config,
    )
    assert report["verdict"] == "DATA_READY_FOR_RULES_AND_MODEL"
    assert report["rules_experiment_authorized"]
    assert report["model_experiment_authorized"]
