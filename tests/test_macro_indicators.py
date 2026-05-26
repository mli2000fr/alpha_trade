from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select

from database.macro_indicators import (
    get_macro_indicators_daily_table,
    persist_macro_indicator_daily,
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


