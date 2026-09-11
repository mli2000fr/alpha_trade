from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.position_keep_exit_dataset import (
    FEATURE_COLUMNS,
    TARGET_COLUMNS,
    KeepExitDatasetConfig,
    audit_univariate,
    build_position_states,
    prepare_oracle_features,
)


def _bars() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=35)
    close = np.linspace(100.0, 110.0, len(dates))
    frame = pd.DataFrame({
        "date": dates, "symbol": "AAA", "px_open": close - 0.1,
        "px_high": close + 1.0, "px_low": close - 1.0, "px_close": close,
        "entry_atr20": 2.0, "previous_close": close - 0.2,
        "volume": np.linspace(1_000, 2_000, len(dates)),
    })
    spy = frame.copy()
    spy["symbol"] = "SPY"
    spy[["px_open", "px_high", "px_low", "px_close"]] *= 4
    return pd.concat([frame, spy], ignore_index=True)


def _oracle() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=35)
    return prepare_oracle_features(pd.DataFrame({
        "date": dates, "symbol": "AAA", "pct_h5": np.linspace(0.7, 0.9, len(dates)),
        "pct_h10": 0.8, "pct_h15": 0.82, "pct_h20": 0.85,
        "consensus_mean": 0.82, "consensus_std": 0.03,
        "consensus_rank": 0.84,
    }))


def _trade() -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=35)
    return pd.DataFrame([{
        "signal_date": dates[0], "symbol": "AAA", "entry_date": dates[2],
        "entry_price": 100.5, "exit_date": dates[10], "exit_price": 104.0,
        "exit_reason": "take_profit", "net_return": 104.0 / 100.5 - 1.0 - 0.0006,
    }])


def test_position_states_respect_close_to_next_open_clock() -> None:
    states = build_position_states(
        _trade(), _bars(), _oracle(), config=KeepExitDatasetConfig(),
    )
    assert len(states) == 8
    assert (states["state_date"] < states["execution_date"]).all()
    assert (states["execution_date"] <= states["label_end_date"]).all()
    assert states["state_date"].max() < states["terminal_date"].min()
    assert states["trade_id"].nunique() == 1
    assert (states["label_end_date"] >= states["terminal_date"]).all()


def test_keep_label_compares_terminal_to_next_open() -> None:
    states = build_position_states(
        _trade(), _bars(), _oracle(), config=KeepExitDatasetConfig(),
    )
    first = states.iloc[0]
    expected = 104.0 / _bars().query("symbol == 'AAA'").iloc[3]["px_open"] - 1.0
    assert first["target_future_residual"] == pytest.approx(expected)
    assert first["label_keep"] == float(expected > 0)
    assert first["target_keep_advantage"] == pytest.approx(
        first["keep_terminal_net"] - first["immediate_exit_net"]
    )


def test_forced_h20_exit_is_not_a_keep_exit_decision() -> None:
    dates = pd.bdate_range("2024-01-02", periods=35)
    trade = _trade()
    trade.loc[0, "exit_date"] = dates[22]
    trade.loc[0, "exit_price"] = 106.0
    trade.loc[0, "exit_reason"] = "fixed_h20"
    trade.loc[0, "net_return"] = 106.0 / 100.5 - 1.0 - 0.0006
    states = build_position_states(
        trade, _bars(), _oracle(), config=KeepExitDatasetConfig(),
    )
    assert len(states) == 19
    assert not (
        (states["terminal_exit_reason"] == "fixed_h20")
        & (states["execution_date"] == states["terminal_date"])
    ).any()


def test_feature_contract_excludes_targets_and_symbol() -> None:
    assert set(FEATURE_COLUMNS).isdisjoint(TARGET_COLUMNS)
    assert "symbol" not in FEATURE_COLUMNS
    assert "terminal_exit_reason" not in FEATURE_COLUMNS


def test_duplicate_oracle_rows_are_rejected() -> None:
    frame = pd.concat([_oracle(), _oracle().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="dupliquées"):
        prepare_oracle_features(frame)


def test_univariate_audit_reports_ordered_bins() -> None:
    states = pd.DataFrame({column: np.linspace(0, 1, 200) for column in FEATURE_COLUMNS})
    states["label_keep"] = (states["current_pnl_net"] > 0.5).astype(float)
    states["target_keep_advantage"] = states["current_pnl_net"] - 0.5
    audit = audit_univariate(states, min_states=10)
    pnl = audit[audit["feature"].eq("current_pnl_net")]
    assert len(pnl) == 10
    assert pnl.iloc[-1]["keep_rate"] > pnl.iloc[0]["keep_rate"]
