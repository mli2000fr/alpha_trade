from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select

from database.macro_indicators import (
    get_macro_indicators_daily_table,
    load_macro_indicator_daily_asof,
    load_macro_indicator_history_asof,
    persist_macro_indicator_daily,
    persist_market_macro_snapshot_daily,
)


def test_persist_macro_indicator_daily_inserts_and_updates_row() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)

        inserted = persist_macro_indicator_daily(
            trade_date=date(2025, 4, 15),
            vix=22.4,
            vix9d=14.15,
            ten_y=4.50,
            engine=engine,
        )
        assert inserted == 1

        with engine.begin() as conn:
            row = conn.execute(
                select(table.c.trade_date, table.c.vix, table.c.vix9d, table.c.ten_y)
            ).one()
        assert row.trade_date == date(2025, 4, 15)
        assert row.vix == 22.4
        assert row.vix9d == 14.15
        assert row.ten_y == 4.50

        updated = persist_macro_indicator_daily(
            trade_date="2025-04-15",
            vix=23.1,
            vix9d=15.0,
            ten_y=4.65,
            engine=engine,
        )
        assert updated == 1

        with engine.begin() as conn:
            row = conn.execute(
                select(table.c.trade_date, table.c.vix, table.c.vix9d, table.c.ten_y)
            ).one()
        assert row.trade_date == date(2025, 4, 15)
        assert row.vix == 23.1
        assert row.vix9d == 15.0
        assert row.ten_y == 4.65
    finally:
        engine.dispose()


def test_persist_macro_indicator_daily_returns_zero_when_table_missing() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        persisted = persist_macro_indicator_daily(
            trade_date=date(2025, 4, 15),
            vix=22.4,
            vix9d=14.15,
            ten_y=4.50,
            engine=engine,
        )

        assert persisted == 0
    finally:
        engine.dispose()


def test_load_macro_indicator_daily_and_history_asof() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)

        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 11),
            vix=20.0,
            vix9d=19.0,
            ten_y=4.30,
            engine=engine,
        )
        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 14),
            vix=21.0,
            vix9d=20.0,
            ten_y=4.40,
            engine=engine,
        )
        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 15),
            vix=22.0,
            vix9d=21.0,
            ten_y=4.50,
            engine=engine,
        )

        row = load_macro_indicator_daily_asof(trade_date=date(2025, 4, 15), engine=engine)
        strict_row = load_macro_indicator_daily_asof(
            trade_date=date(2025, 4, 15),
            engine=engine,
            strict_before=True,
        )
        history = load_macro_indicator_history_asof(
            trade_date=date(2025, 4, 15),
            column="ten_y",
            lookback_days=2,
            engine=engine,
        )
        strict_history = load_macro_indicator_history_asof(
            trade_date=date(2025, 4, 15),
            column="ten_y",
            lookback_days=2,
            engine=engine,
            strict_before=True,
        )

        assert row is not None
        assert row["trade_date"] == date(2025, 4, 15)
        assert row["vix"] == 22.0
        assert strict_row is not None
        assert strict_row["trade_date"] == date(2025, 4, 14)
        assert history == [4.40, 4.50]
        assert strict_history == [4.30, 4.40]
    finally:
        engine.dispose()


def test_persist_market_macro_snapshot_daily_maps_snapshot_payload() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)

        persisted = persist_market_macro_snapshot_daily(
            trade_date=date(2025, 4, 15),
            macro_payload={"vix": 22.4, "vix_short": 14.15, "yield_10y": 4.50},
            engine=engine,
        )

        assert persisted == 1
        with engine.begin() as conn:
            row = conn.execute(
                select(table.c.trade_date, table.c.vix, table.c.vix9d, table.c.ten_y)
            ).one()
        assert row.trade_date == date(2025, 4, 15)
        assert row.vix == 22.4
        assert row.vix9d == 14.15
        assert row.ten_y == 4.50
    finally:
        engine.dispose()


