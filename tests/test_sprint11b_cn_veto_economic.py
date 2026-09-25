"""Les blocages d'exécution ne doivent jamais devenir des profits implicites."""

from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.cn_veto_economic_replay import (
    DEFAULT_CONFIG,
    classify_feasibility,
    load_protocol,
    merge_labels,
    policy_summary,
    proxy_returns,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "session_date": pd.to_datetime(["2023-06-01", "2023-06-01"]),
        "instrument_id": [1, 2],
        "market_code": ["CN_A", "CN_A"],
        "board_code": ["SH_MAIN", "SH_MAIN"],
        "target_quality_valid": [True, True],
        "oracle_decile": [1, 10],
        "future_return": [0.10, -0.10],
        "execution_data_eligible": [True, True],
        "entry_open": [10.0, 10.0],
        "exit_close": [11.0, 9.0],
        "exit_date": pd.to_datetime(["2023-06-08", "2023-06-08"]),
        "path_factor_event": [False, False],
        "entry_limit_locked": [False, False],
        "exit_limit_locked": [False, False],
    })


def test_protocol_research_only_and_costs_are_explicit() -> None:
    config = load_protocol(DEFAULT_CONFIG)
    assert not config["serving_enabled"]
    assert not config["backtest_enabled"]
    assert config["decision_gate"].startswith("none_")
    assert config["cost_scenarios"]["base_proxy"]["bps_per_side"] == 10


def test_proxy_returns_apply_lot_minimum_fees_and_roundtrip() -> None:
    result = proxy_returns(_frame(), load_protocol(DEFAULT_CONFIG))
    assert result["feasibility"].eq("FILLABLE_PROXY").all()
    assert result["quantity_proxy"].tolist() == [1000.0, 1000.0]
    expected = (11000 - 11 - 10000 - 10) / (10000 + 10)
    assert result["net_return_base_proxy"].iloc[0] == pytest.approx(expected)
    assert result["net_return_base_proxy"].iloc[0] < result["future_return"].iloc[0]


def test_locked_exit_is_unresolved_not_zero_pnl() -> None:
    frame = _frame()
    frame.loc[0, "exit_limit_locked"] = True
    result = proxy_returns(frame, load_protocol(DEFAULT_CONFIG))
    assert result["feasibility"].iloc[0] == "EXIT_LOCKED_OR_UNKNOWN"
    assert pd.isna(result["net_return_base_proxy"].iloc[0])
    summary = policy_summary(
        result, pd.Series(True, index=result.index), load_protocol(DEFAULT_CONFIG),
    )
    assert summary["selected"] == 2
    assert summary["fillable_proxy"] == 1
    assert summary["blockers"]["EXIT_LOCKED_OR_UNKNOWN"] == 1


def test_same_day_exit_is_rejected_even_with_positive_price_return() -> None:
    frame = _frame()
    frame.loc[0, "exit_date"] = frame.loc[0, "session_date"]
    reasons = classify_feasibility(frame, load_protocol(DEFAULT_CONFIG))
    assert reasons.iloc[0] == "T_PLUS_ONE_VIOLATION"


def test_label_merge_refuses_future_return_divergence() -> None:
    pool = _frame().drop(columns=[
        "entry_open", "exit_close", "exit_date", "path_factor_event",
        "entry_limit_locked", "exit_limit_locked",
    ])
    labels = _frame().copy()
    labels.loc[0, "future_return"] = 0.12
    with pytest.raises(RuntimeError, match="future_return"):
        merge_labels(pool, labels)
