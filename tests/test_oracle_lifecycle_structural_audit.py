from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.oracle_lifecycle_structural_audit import (
    CONTRACTS,
    E15Config,
    LifecycleContract,
    paired_delta,
    schedule_contract_capacity,
    simulate_contract_long,
)
from modelFactory.oracle_monetization_bridge import E12Config, simulate_prod_long
from modelFactory.oracle_rolling_lifecycle import prepare_bars


def _bars(periods: int = 90, step: float = 0.2) -> pd.DataFrame:
    rows = []
    for index, date in enumerate(pd.bdate_range("2024-01-02", periods=periods)):
        price = 100.0 + index * step
        rows.append({
            "symbol": "AAA", "date": date, "open": price,
            "high": price + 0.4, "low": price - 0.4, "close": price,
            "adj_close": price, "volume": 1_000_000,
        })
    return pd.DataFrame(rows)


def test_prod_contract_is_bitwise_equivalent_to_e12_simulator() -> None:
    bars = prepare_bars(_bars())
    config = E12Config()
    contract = next(item for item in CONTRACTS if item.name == "prod")
    expected = simulate_prod_long(
        bars, signal_date=pd.Timestamp("2024-02-01"), config=config
    )
    actual = simulate_contract_long(
        bars, signal_date=pd.Timestamp("2024-02-01"), contract=contract, config=config
    )
    assert expected is not None and actual is not None
    for key in ("entry_date", "exit_date", "exit_reason", "holding_sessions"):
        assert actual[key] == expected[key]
    assert actual["net_return"] == pytest.approx(expected["net_return"])


def test_delayed_trailing_activation_uses_previous_completed_peak() -> None:
    bars = prepare_bars(_bars(step=0.5))
    result = simulate_contract_long(
        bars, signal_date=pd.Timestamp("2024-02-01"),
        contract=LifecycleContract("delayed", "after_0_5r", True),
        config=E12Config(tp_atr_multiple=100.0, tp_max_pct=0.90),
    )
    assert result is not None
    assert result["activation_date"] is not None
    assert result["activation_date"] > result["entry_date"]


def test_no_tp_no_trailing_reaches_fixed_h20() -> None:
    bars = prepare_bars(_bars(step=0.2))
    result = simulate_contract_long(
        bars, signal_date=pd.Timestamp("2024-02-01"),
        contract=LifecycleContract("passive", "none", False), config=E12Config(),
    )
    assert result is not None
    assert result["exit_reason"] == "fixed_h20"
    assert result["holding_sessions"] == 20


def test_tp_switch_changes_exit_on_same_path() -> None:
    bars = prepare_bars(_bars(step=0.5))
    config = E12Config(tp_atr_multiple=0.1, tp_max_pct=0.07)
    with_tp = simulate_contract_long(
        bars, signal_date=pd.Timestamp("2024-02-01"),
        contract=LifecycleContract("with", "none", True), config=config,
    )
    without_tp = simulate_contract_long(
        bars, signal_date=pd.Timestamp("2024-02-01"),
        contract=LifecycleContract("without", "none", False), config=config,
    )
    assert with_tp is not None and without_tp is not None
    assert with_tp["exit_reason"] == "take_profit"
    assert without_tp["exit_reason"] == "fixed_h20"


def test_capacity_refills_after_contract_exit() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    panel = pd.DataFrame([
        {
            "date": date, "entry_date": date + pd.offsets.BDay(1),
            "exit_date": date + pd.offsets.BDay(1), "symbol": f"S{index}",
            "directional_oracle_proba_extreme": 0.9,
        }
        for index, date in enumerate(dates)
    ])
    selected = schedule_contract_capacity(panel, 1)
    assert selected["symbol"].tolist() == ["S0", "S1", "S2"]


def test_paired_delta_uses_same_event_keys() -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    baseline = pd.DataFrame({
        "date": dates, "symbol": ["AAA", "BBB", "CCC"],
        "net_return": [0.01, 0.02, -0.01],
    })
    candidate = baseline.copy()
    candidate["net_return"] += 0.01
    result = paired_delta(
        baseline, candidate, E15Config(bootstrap_samples=10)
    )
    assert result["paired_events"] == 3
    assert result["mean_event_delta"] == pytest.approx(0.01)


def test_contract_matrix_and_primary_are_frozen() -> None:
    assert len(CONTRACTS) == 8
    assert len({contract.name for contract in CONTRACTS}) == 8
    assert E15Config().primary_contract == "trail_after_0_5r_tp"
    with pytest.raises(ValueError, match="inconnu"):
        E15Config(primary_contract="optimized_after_reading")
