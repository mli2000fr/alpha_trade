from datetime import date

import pytest
from sqlalchemy import create_engine, text

from common.tradable_universe import (
    UniverseMember,
    UniverseSnapshotNotFoundError,
    begin_universe_run,
    fail_universe_run,
    publish_universe_run,
    resolve_universe_asof,
)
from common.publish_tradable_universe import publish_full_tradable_universe
from common.capital_presets import DEFAULT_CAPITAL_PRESET_KEY
from backtesting.data_loader import (
    load_tradable_universe_asof as load_backtest_universe,
    load_tradable_universe_scope,
)
from modelFactory.db_registry import load_tradable_universe_symbols
from risk_management.db_io import RiskRepository


@pytest.fixture()
def engine():
    database = create_engine("sqlite:///:memory:")
    with database.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys = ON"))
        connection.execute(
            text(
                """
                CREATE TABLE tradable_universe_runs (
                    universe_run_id VARCHAR(64) PRIMARY KEY,
                    snapshot_date DATE NOT NULL,
                    capital_preset_key VARCHAR(64) NOT NULL,
                    config_fingerprint VARCHAR(64) NOT NULL,
                    status VARCHAR(16) NOT NULL,
                    is_canonical BOOLEAN NOT NULL DEFAULT 0,
                    rows_expected INTEGER NOT NULL,
                    rows_written INTEGER NOT NULL DEFAULT 0,
                    tradable_rows INTEGER NOT NULL DEFAULT 0,
                    data_quality_grade VARCHAR(16) NOT NULL DEFAULT 'unknown',
                    failure_reason TEXT,
                    started_at DATETIME NOT NULL,
                    finished_at DATETIME
                )
                """
            )
        )
        connection.execute(text("CREATE TABLE stock_quote_snapshots (symbol VARCHAR(32), quote_date DATE, spread_bps FLOAT)"))
        connection.execute(text("CREATE TABLE stock_earnings_calendar (symbol VARCHAR(32), earnings_date DATE)"))
        connection.execute(text("CREATE TABLE stock_metadata (symbol VARCHAR(32) PRIMARY KEY, market_cap FLOAT)"))
        connection.execute(
            text(
                """
                CREATE TABLE tradable_universe_history (
                    universe_run_id VARCHAR(64) NOT NULL,
                    symbol VARCHAR(32) NOT NULL,
                    is_tradable BOOLEAN NOT NULL,
                    tradability_reason_code VARCHAR(64) NOT NULL,
                    tradability_reasons_json TEXT,
                    history_days INTEGER,
                    bars_available BOOLEAN,
                    data_source VARCHAR(32),
                    close_price FLOAT,
                    adv_usd FLOAT,
                    spread_bps FLOAT,
                    market_cap FLOAT,
                    atr_pct_20 FLOAT,
                    earnings_blackout BOOLEAN,
                    data_quality_grade VARCHAR(16) NOT NULL DEFAULT 'unknown',
                    created_at DATETIME NOT NULL,
                    PRIMARY KEY (universe_run_id, symbol),
                    FOREIGN KEY (universe_run_id) REFERENCES tradable_universe_runs (universe_run_id)
                )
                """
            )
        )
    try:
        yield database
    finally:
        database.dispose()


def _members() -> list[UniverseMember]:
    return [
        UniverseMember("AAPL", True, "tradable", history_days=600, data_quality_grade="full"),
        UniverseMember("ILLIQ", False, "adv_below_minimum", history_days=600, data_quality_grade="full"),
    ]


def _publish(engine, run_id: str, snapshot_date: date, preset: str = "small") -> None:
    begin_universe_run(
        engine,
        universe_run_id=run_id,
        snapshot_date=snapshot_date,
        capital_preset_key=preset,
        config_fingerprint=f"config-{run_id}",
        rows_expected=2,
        data_quality_grade="full",
    )
    publish_universe_run(engine, run_id, _members())


def test_resolve_universe_asof_returns_complete_tradable_scope(engine) -> None:
    _publish(engine, "run-1", date(2025, 1, 2))

    resolution = resolve_universe_asof(engine, date(2025, 1, 3), "small")

    assert resolution.universe_run_id == "run-1"
    assert resolution.snapshot_date == date(2025, 1, 2)
    assert resolution.symbols == ["AAPL"]
    assert resolution.rows_expected == resolution.rows_written == 2


def test_resolve_can_include_rejected_symbols_with_reasons(engine) -> None:
    _publish(engine, "run-1", date(2025, 1, 2))

    resolution = resolve_universe_asof(
        engine,
        date(2025, 1, 2),
        "small",
        tradable_only=False,
    )

    assert resolution.symbols == ["AAPL", "ILLIQ"]
    rejected = resolution.frame.set_index("symbol").loc["ILLIQ"]
    assert bool(rejected["is_tradable"]) is False
    assert rejected["tradability_reason_code"] == "adv_below_minimum"


def test_publish_full_universe_applies_objective_context_without_mutating_source(engine) -> None:
    snapshot_date = date(2025, 1, 2)
    source_members = [
        UniverseMember("AAPL", True, "tradable", history_days=600, close_price=200.0, adv_usd=50_000_000.0, data_quality_grade="degraded"),
        UniverseMember("WIDE", True, "tradable", history_days=600, close_price=20.0, adv_usd=50_000_000.0, data_quality_grade="degraded"),
    ]
    begin_universe_run(
        engine,
        universe_run_id="source-degraded",
        snapshot_date=snapshot_date,
        capital_preset_key=DEFAULT_CAPITAL_PRESET_KEY,
        config_fingerprint="source-config",
        rows_expected=2,
        data_quality_grade="degraded",
    )
    publish_universe_run(engine, "source-degraded", source_members)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO stock_quote_snapshots VALUES (:symbol, :quote_date, :spread_bps)"),
            [
                {"symbol": "AAPL", "quote_date": snapshot_date, "spread_bps": 5.0},
                {"symbol": "WIDE", "quote_date": snapshot_date, "spread_bps": 500.0},
            ],
        )
        connection.execute(
            text("INSERT INTO stock_metadata VALUES (:symbol, :market_cap)"),
            [
                {"symbol": "AAPL", "market_cap": 3_000_000_000_000.0},
                {"symbol": "WIDE", "market_cap": 5_000_000_000.0},
            ],
        )

    full_run_id = publish_full_tradable_universe(
        engine,
        snapshot_date=snapshot_date,
        capital_preset_key=DEFAULT_CAPITAL_PRESET_KEY,
    )

    resolution = resolve_universe_asof(engine, snapshot_date, DEFAULT_CAPITAL_PRESET_KEY, tradable_only=False)
    assert resolution.universe_run_id == full_run_id
    assert resolution.data_quality_grade == "full"
    rows = resolution.frame.set_index("symbol")
    assert bool(rows.loc["AAPL", "is_tradable"]) is True
    assert rows.loc["WIDE", "tradability_reason_code"] == "spread_above_maximum"
    with engine.connect() as connection:
        source_grade = connection.execute(
            text("SELECT data_quality_grade FROM tradable_universe_runs WHERE universe_run_id = 'source-degraded'")
        ).scalar_one()
    assert source_grade == "degraded"


def test_partial_or_failed_run_is_never_served(engine) -> None:
    begin_universe_run(
        engine,
        universe_run_id="partial",
        snapshot_date=date(2025, 1, 2),
        capital_preset_key="small",
        config_fingerprint="partial-config",
        rows_expected=2,
    )
    with pytest.raises(ValueError, match="Snapshot incomplet"):
        publish_universe_run(engine, "partial", _members()[:1])
    fail_universe_run(engine, "partial", "worker_failure")

    with pytest.raises(UniverseSnapshotNotFoundError):
        resolve_universe_asof(engine, date(2025, 1, 2), "small")


def test_rerun_becomes_canonical_without_mutating_previous_run(engine) -> None:
    _publish(engine, "run-1", date(2025, 1, 2))
    _publish(engine, "run-2", date(2025, 1, 2))

    resolution = resolve_universe_asof(engine, date(2025, 1, 2), "small")
    assert resolution.universe_run_id == "run-2"

    with engine.connect() as connection:
        old_run = connection.execute(
            text("SELECT status, is_canonical, rows_written FROM tradable_universe_runs WHERE universe_run_id='run-1'")
        ).mappings().one()
        old_rows = connection.execute(
            text("SELECT COUNT(*) FROM tradable_universe_history WHERE universe_run_id='run-1'")
        ).scalar_one()
    assert old_run == {"status": "completed", "is_canonical": 0, "rows_written": 2}
    assert old_rows == 2


def test_future_snapshot_is_not_used(engine) -> None:
    _publish(engine, "future", date(2025, 1, 3))

    with pytest.raises(UniverseSnapshotNotFoundError):
        resolve_universe_asof(engine, date(2025, 1, 2), "small")


def test_presets_have_independent_scopes(engine) -> None:
    _publish(engine, "small-run", date(2025, 1, 2), preset="small")
    _publish(engine, "large-run", date(2025, 1, 2), preset="large")

    assert resolve_universe_asof(engine, date(2025, 1, 2), "small").universe_run_id == "small-run"
    assert resolve_universe_asof(engine, date(2025, 1, 2), "large").universe_run_id == "large-run"


def test_runtime_loaders_share_the_same_canonical_snapshot(engine) -> None:
    _publish(engine, "shared-run", date(2025, 1, 2), preset="small")

    risk_resolution = RiskRepository(engine).load_tradable_universe_asof(
        date(2025, 1, 2),
        "small",
    )
    backtest_resolution = load_backtest_universe(engine, date(2025, 1, 2), "small")
    model_symbols = load_tradable_universe_symbols(
        engine,
        trade_date=date(2025, 1, 2),
        capital_preset_key="small",
    )

    assert risk_resolution.universe_run_id == backtest_resolution.universe_run_id == "shared-run"
    assert risk_resolution.symbols == backtest_resolution.symbols == model_symbols == ["AAPL"]


def test_backtest_scope_resolves_each_date_asof_its_canonical_universe(engine) -> None:
    _publish(engine, "first", date(2025, 1, 2), preset="small")
    _publish(engine, "second", date(2025, 1, 3), preset="small")

    scope = load_tradable_universe_scope(
        engine,
        [date(2025, 1, 2), date(2025, 1, 3)],
        capital_preset_key="small",
    )

    assert scope["universe_run_id"].tolist() == ["first", "second"]
    assert scope["symbol"].tolist() == ["AAPL", "AAPL"]