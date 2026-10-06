from __future__ import annotations

import importlib.util
from dataclasses import replace
from datetime import date
from pathlib import Path

from service.fr.universe_liquidity_6b import (
    FRLiquidityPolicy,
    build_symbol_snapshots,
)

ROOT = Path(__file__).resolve().parents[1]


def _policy(**changes) -> FRLiquidityPolicy:
    base = FRLiquidityPolicy.from_yaml(ROOT / "config" / "universe_fr_s6b.yaml")
    return replace(base, **changes)


def _row(day: date) -> dict:
    return {
        "symbol": "AIR.PA",
        "session_date": day.isoformat(),
        "mic": "XPAR",
        "research_j1_eligible": True,
    }


def _bar(day: date, close: float, volume: int) -> tuple[str, dict]:
    return day.isoformat(), {"date": day.isoformat(), "close": close, "volume": volume}


def test_fr_migration_0007_is_isolated_and_chained() -> None:
    path = ROOT / "alembic_fr" / "versions" / "0007_fr_liquidity_research.py"
    spec = importlib.util.spec_from_file_location("fr_migration_0007", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "0006_fr_universe_contract"
    sql = (
        ROOT / "database" / "sql" / "fr" / "migration_fr_0007_liquidity_research.sql"
    ).read_text(encoding="utf-8")
    assert "fr_liquidity_runs" in sql
    assert "fr_liquidity_snapshots" in sql
    assert "instrument_id BIGINT UNSIGNED NULL" in sql
    assert "alpha_trade." not in sql


def test_policy_is_pre_registered_and_research_only() -> None:
    policy = _policy()
    assert policy.availability_lag_sessions == 1
    assert policy.min_history_sessions == 252
    assert policy.liquidity_lookback_sessions == 20
    assert policy.min_liquidity_observations == 15
    assert policy.min_avg_traded_value_eur == 500_000
    assert policy.min_close_eur == 1.0
    assert not policy.tradable_enabled
    assert not policy.servable_enabled


def test_snapshots_use_only_information_available_before_decision() -> None:
    days = [date(2024, 6, 3), date(2024, 6, 4), date(2024, 6, 5), date(2024, 6, 6)]
    policy = _policy(
        min_history_sessions=2,
        liquidity_lookback_sessions=3,
        min_liquidity_observations=2,
        min_avg_traded_value_eur=1_000,
        min_close_eur=1.0,
    )
    bars = dict([
        _bar(days[0], 10.0, 100),
        _bar(days[1], 20.0, 100),
        _bar(days[2], 30.0, 100),
        _bar(days[3], 1_000_000.0, 1_000_000),
    ])
    snapshots = build_symbol_snapshots(
        symbol="AIR.PA",
        manifest_rows=[_row(day) for day in days[:3]],
        bars_by_date=bars,
        policy=policy,
        session_index={day: index for index, day in enumerate(days)},
        sessions=days,
    )
    assert [row["decision_session_date"] for row in snapshots] == [
        "2024-06-04", "2024-06-05", "2024-06-06"
    ]
    assert snapshots[0]["training_state"] == "INELIGIBLE"
    assert snapshots[0]["primary_reason"] == "INSUFFICIENT_HISTORY"
    assert snapshots[1]["training_state"] == "ELIGIBLE"
    assert snapshots[2]["avg_traded_value_eur"] == 2_000.0


def test_missing_market_sessions_reduce_liquidity_observations() -> None:
    days = [date(2024, 6, 3), date(2024, 6, 4), date(2024, 6, 5), date(2024, 6, 6)]
    policy = _policy(
        min_history_sessions=2,
        liquidity_lookback_sessions=3,
        min_liquidity_observations=3,
        min_avg_traded_value_eur=1,
    )
    bars = dict([_bar(days[0], 10.0, 100), _bar(days[2], 10.0, 100)])
    snapshots = build_symbol_snapshots(
        symbol="AIR.PA",
        manifest_rows=[_row(days[0]), _row(days[2])],
        bars_by_date=bars,
        policy=policy,
        session_index={day: index for index, day in enumerate(days)},
        sessions=days,
    )
    assert snapshots[-1]["history_state"] == "KNOWN"
    assert snapshots[-1]["liquidity_observations"] == 2
    assert snapshots[-1]["liquidity_state"] == "INSUFFICIENT"
    assert snapshots[-1]["training_state"] == "INELIGIBLE"


def test_low_price_and_low_traded_value_have_distinct_reasons() -> None:
    days = [date(2024, 6, 3), date(2024, 6, 4), date(2024, 6, 5)]
    policy = _policy(
        min_history_sessions=1,
        liquidity_lookback_sessions=1,
        min_liquidity_observations=1,
        min_avg_traded_value_eur=500_000,
        min_close_eur=1.0,
    )
    cheap = build_symbol_snapshots(
        symbol="AIR.PA",
        manifest_rows=[_row(days[0])],
        bars_by_date=dict([_bar(days[0], 0.5, 2_000_000)]),
        policy=policy,
        session_index={day: index for index, day in enumerate(days)},
        sessions=days,
    )[0]
    illiquid = build_symbol_snapshots(
        symbol="AIR.PA",
        manifest_rows=[_row(days[1])],
        bars_by_date=dict([_bar(days[1], 10.0, 10)]),
        policy=policy,
        session_index={day: index for index, day in enumerate(days)},
        sessions=days,
    )[0]
    assert cheap["primary_reason"] == "PRICE_BELOW_MINIMUM"
    assert illiquid["primary_reason"] == "AVG_TRADED_VALUE_BELOW_MINIMUM"
