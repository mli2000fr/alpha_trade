from __future__ import annotations

import pandas as pd

from modelFactory.oracle_rolling_lifecycle import (
    LifecycleConfig,
    build_delayed_candidates,
    prepare_bars,
    simulate_trade,
)


def _bars() -> pd.DataFrame:
    rows = []
    for index, date in enumerate(pd.bdate_range("2024-01-02", periods=100)):
        close = 100.0 + 0.15 * index
        rows.append({
            "symbol": "AAA", "date": date, "open": close,
            "high": close + 0.20, "low": close - 0.20,
            "close": close, "adj_close": close,
        })
    return prepare_bars(pd.DataFrame(rows))


def _h5_rank(bars: pd.DataFrame, value: float = 0.90) -> dict[tuple[pd.Timestamp, str], float]:
    return {(pd.Timestamp(date), "AAA"): value for date in bars["date"]}


def test_delayed_candidate_requires_price_and_oracle_confirmation() -> None:
    events = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"]),
        "symbol": ["AAA"] * 3, "mh0": [True, True, True],
        "px_close": [100.0] * 3, "cp5_close": [101.0, 99.0, 102.0],
        "cp5_date": pd.to_datetime(["2024-01-09"] * 3),
        "cp5_exit_open": [101.0] * 3,
        "cp5_oracle_confirmed": [True, True, False],
    })
    candidates = build_delayed_candidates(events)
    assert len(candidates) == 1
    assert candidates.iloc[0]["decision_date"] == pd.Timestamp("2024-01-09")


def test_rolling_policy_exits_when_h5_is_not_confirmed() -> None:
    bars = _bars()
    config = LifecycleConfig(tp_atr_multiple=100.0, tp_max_pct=0.50)
    ranks = _h5_rank(bars)
    entry_index = bars.index[bars["date"].gt(pd.Timestamp("2024-02-01"))][0]
    checkpoint_date = pd.Timestamp(bars.iloc[entry_index + 4]["date"])
    ranks[(checkpoint_date, "AAA")] = 0.50
    result = simulate_trade(
        bars, signal_date=pd.Timestamp("2024-01-25"),
        decision_date=pd.Timestamp("2024-02-01"), policy="rolling_h5_60",
        h5_rank=ranks, config=config,
    )
    assert result is not None
    assert result["exit_reason"] == "rolling_h5_not_confirmed"
    assert result["holding_sessions"] == 5


def test_fixed_h20_exits_after_twenty_sessions_without_tp() -> None:
    bars = _bars()
    config = LifecycleConfig(tp_atr_multiple=100.0, tp_max_pct=0.50)
    result = simulate_trade(
        bars, signal_date=pd.Timestamp("2024-01-25"),
        decision_date=pd.Timestamp("2024-02-01"), policy="fixed_h20",
        h5_rank=_h5_rank(bars), config=config,
    )
    assert result is not None
    assert result["exit_reason"] == "fixed_h20"
    assert result["holding_sessions"] == 20


def test_missing_future_h5_window_is_rejected_not_treated_as_negative_signal() -> None:
    bars = _bars()
    config = LifecycleConfig(tp_atr_multiple=100.0, tp_max_pct=0.50)
    result = simulate_trade(
        bars, signal_date=pd.Timestamp("2024-01-25"),
        decision_date=pd.Timestamp("2024-02-01"), policy="rolling_h5_60",
        h5_rank={}, config=config,
    )
    assert result is None
