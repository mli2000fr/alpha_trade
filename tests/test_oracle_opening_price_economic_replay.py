from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from modelFactory.oracle_opening_price_economic_replay import (
    E20DConfig,
    schedule_capacity,
    select_price_confirmed,
    simulate_delayed_trade,
)


def test_price_confirmation_is_symmetric_and_strict() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01"] * 4),
        "target_session": pd.to_datetime(["2026-01-02"] * 4),
        "symbol": ["A", "B", "C", "D"], "price_30m": 100.0,
        "opening_price": 100.0, "return_30m": [0.006, -0.006, 0.005, -0.005],
        "directional_oracle_proba_extreme": 0.8, "oracle_decile": [10, 1, 10, 1],
    })
    selected = select_price_confirmed(frame, E20DConfig())
    assert selected[["symbol", "direction"]].values.tolist() == [["A", 1], ["B", -1]]


def _bars() -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-02", periods=23)
    return pd.DataFrame({
        "date": dates, "symbol": "AAA", "open": 100.0, "high": 101.0,
        "low": 99.0, "close": 100.0, "px_open": 100.0, "px_high": 101.0,
        "px_low": 99.0, "px_close": 100.0, "previous_close": 100.0,
        "entry_atr20": 2.0, "adv20": 2_000_000.0,
    })


def test_delayed_long_uses_adjusted_checkpoint_and_costs() -> None:
    event = SimpleNamespace(
        target_session=pd.Timestamp("2026-01-02"), price_30m=100.0,
        opening_price=100.0, direction=1,
    )
    result = simulate_delayed_trade(
        _bars(), event, policy="next_session_protection", config=E20DConfig()
    )
    assert result is not None and not result["rejected"]
    assert result["entry_price"] == 100.0
    assert np.isclose(result["net_return"], -0.0006)
    assert np.isclose(result["delayed_fixed_h20_net"], -0.0006)
    assert np.isclose(result["next_open_fixed_h20_net"], -0.0006)
    assert np.isclose(result["delay_impact_fixed_h20"], 0.0)


def test_opening_gap_rejects_before_delayed_entry() -> None:
    event = SimpleNamespace(
        target_session=pd.Timestamp("2026-01-02"), price_30m=105.0,
        opening_price=104.0, direction=1,
    )
    result = simulate_delayed_trade(
        _bars(), event, policy="full_day_conservative", config=E20DConfig()
    )
    assert result == {"rejected": True, "rejection_reason": "opening_gap"}


def test_capacity_is_shared_between_long_and_short() -> None:
    frame = pd.DataFrame({
        "entry_date": pd.to_datetime(["2026-01-02"] * 3),
        "exit_date": pd.to_datetime(["2026-01-05"] * 3),
        "symbol": ["A", "B", "C"], "side": ["LONG", "SHORT", "LONG"],
        "oracle_score": [0.9, 0.8, 0.7],
    })
    selected = schedule_capacity(frame, 2)
    assert selected["symbol"].tolist() == ["A", "B"]
