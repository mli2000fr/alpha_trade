from __future__ import annotations

import pandas as pd
import pytest

import modelFactory.oracle_monetization_bridge as bridge
from modelFactory.oracle_monetization_bridge import (
    E12Config,
    build_fixed_h20_events,
    deduplicate_non_overlapping,
    filter_by_membership,
    replay_lifecycle_with_dynamic_capacity,
    select_with_capacity,
    simulate_prod_long,
)
from modelFactory.oracle_rolling_lifecycle import prepare_bars


def _bars(symbols: tuple[str, ...] = ("AAA", "BBB"), periods: int = 90) -> pd.DataFrame:
    rows = []
    for symbol_index, symbol in enumerate(symbols):
        for index, date in enumerate(pd.bdate_range("2024-01-02", periods=periods)):
            price = 100.0 + (symbol_index + 1) * 0.1 * index
            rows.append({
                "symbol": symbol, "date": date, "open": price,
                "high": price + 0.2, "low": price - 0.2,
                "close": price, "adj_close": price, "volume": 1_000_000,
            })
    return pd.DataFrame(rows)


def _gate(symbols: tuple[str, ...] = ("AAA", "BBB"), days: int = 30) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "date": date, "symbol": symbol,
            "directional_oracle_fold_start": "2024-01-02",
            "directional_oracle_proba_extreme": 0.9 - 0.1 * symbol_index,
            "directional_oracle_eligible": True,
            "directional_oracle_oof_available": True,
        }
        for date in pd.bdate_range("2024-01-02", periods=days)
        for symbol_index, symbol in enumerate(symbols)
    ])


def test_fixed_events_use_j1_to_j21_and_costs() -> None:
    config = E12Config(random_seeds=2, bootstrap_samples=10)
    events = build_fixed_h20_events(_gate(days=1), _bars(), config)
    row = events.iloc[0]
    assert row["entry_date"] == row["date"] + pd.offsets.BDay(1)
    assert row["terminal_date"] == row["date"] + pd.offsets.BDay(21)
    assert row["net_return"] == pytest.approx(row["gross_return"] - 0.0006)


def test_only_eligible_oof_oracle_rows_are_used() -> None:
    gate = _gate(days=1)
    gate.loc[0, "directional_oracle_eligible"] = False
    gate.loc[1, "directional_oracle_oof_available"] = False
    events = build_fixed_h20_events(gate, _bars(), E12Config())
    assert events.empty


def test_non_overlap_keeps_first_then_signal_after_exit() -> None:
    events = build_fixed_h20_events(_gate(symbols=("AAA",), days=30), _bars(), E12Config())
    selected = deduplicate_non_overlapping(events)
    assert len(selected) == 2
    assert selected.iloc[1]["entry_date"] >= selected.iloc[0]["terminal_date"]


def test_capacity_never_exceeds_slots_and_oracle_priority_wins() -> None:
    symbols = tuple(f"S{i}" for i in range(5))
    bars = _bars(symbols=symbols)
    gate = _gate(symbols=symbols, days=1)
    events = build_fixed_h20_events(gate, bars, E12Config(max_positions=2))
    chosen = select_with_capacity(events, E12Config(max_positions=2), policy="oracle_score")
    assert len(chosen) == 2
    assert set(chosen["symbol"]) == {"S0", "S1"}


def test_random_capacity_is_reproducible() -> None:
    symbols = tuple(f"S{i}" for i in range(5))
    events = build_fixed_h20_events(
        _gate(symbols=symbols, days=2), _bars(symbols=symbols), E12Config(max_positions=2)
    )
    first = select_with_capacity(events, E12Config(max_positions=2), policy="random", seed=7)
    second = select_with_capacity(events, E12Config(max_positions=2), policy="random", seed=7)
    assert first[["date", "symbol"]].equals(second[["date", "symbol"]])


def test_membership_filter_is_exact_date_symbol() -> None:
    events = build_fixed_h20_events(_gate(days=2), _bars(), E12Config())
    membership = events.iloc[[0]][["date", "symbol"]]
    filtered = filter_by_membership(events, membership)
    assert len(filtered) == 1
    assert filtered.iloc[0]["symbol"] == membership.iloc[0]["symbol"]


def test_prod_lifecycle_hits_take_profit() -> None:
    bars = prepare_bars(_bars(symbols=("AAA",)))
    config = E12Config(tp_atr_multiple=0.1, tp_max_pct=0.07)
    result = simulate_prod_long(
        bars, signal_date=pd.Timestamp("2024-02-01"), config=config
    )
    assert result is not None
    assert result["exit_reason"] == "take_profit"


def test_prod_lifecycle_rejects_large_entry_gap() -> None:
    raw = _bars(symbols=("AAA",))
    target = raw.index[raw["date"].eq(pd.Timestamp("2024-02-02"))][0]
    raw.loc[target, ["open", "high", "low", "close", "adj_close"]] = [120, 121, 119, 120, 120]
    bars = prepare_bars(raw)
    result = simulate_prod_long(
        bars, signal_date=pd.Timestamp("2024-02-01"), config=E12Config()
    )
    assert result is not None
    assert result["exit_reason"] == "entry_gap_rejected"


def test_config_rejects_other_horizon() -> None:
    with pytest.raises(ValueError, match="H20"):
        E12Config(horizon=10)


def test_dynamic_capacity_refills_after_real_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    dates = pd.bdate_range("2024-01-02", periods=3)
    events = pd.DataFrame([
        {
            "date": date, "entry_date": date + pd.offsets.BDay(1),
            "terminal_date": date + pd.offsets.BDay(21), "symbol": f"S{index}",
            "directional_oracle_proba_extreme": 0.9, "adv20": 1_000_000,
            "net_return": 0.01, "fold": "0", "semester": "2024H1",
        }
        for index, date in enumerate(dates)
    ])

    def fake_simulate(_bars: pd.DataFrame, *, signal_date: pd.Timestamp, config: E12Config):
        entry_date = signal_date + pd.offsets.BDay(1)
        return {
            "entry_date": entry_date, "entry_price": 100.0,
            "exit_date": entry_date, "exit_price": 101.0,
            "exit_reason": "take_profit", "holding_sessions": 1,
            "gross_return": 0.01, "net_return": 0.0094,
        }

    monkeypatch.setattr(bridge, "simulate_prod_long", fake_simulate)
    selected, rejected = replay_lifecycle_with_dynamic_capacity(
        events, pd.DataFrame({"symbol": pd.Series(dtype=str)}),
        E12Config(max_positions=1), policy="oracle_score"
    )
    assert len(selected) == 3
    assert rejected.empty
