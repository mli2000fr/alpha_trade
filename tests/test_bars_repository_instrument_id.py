from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from database.repositories.bars import BarsRepository
from database.repositories.instruments import InstrumentRepository


@pytest.fixture
def engine():
    value = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with value.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE instruments (
                instrument_id INTEGER PRIMARY KEY AUTOINCREMENT,
                instrument_uid TEXT NOT NULL UNIQUE,
                market_code TEXT NOT NULL,
                exchange_mic TEXT,
                local_symbol TEXT NOT NULL,
                display_name TEXT,
                instrument_type TEXT NOT NULL,
                currency TEXT NOT NULL,
                listing_date DATE,
                delisting_date DATE,
                mapping_status TEXT NOT NULL,
                is_active BOOLEAN NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE stock_bars_daily (
                instrument_id INTEGER,
                symbol TEXT NOT NULL,
                date DATE NOT NULL,
                close REAL NOT NULL
            )
            """
        )
    yield value
    value.dispose()


def _seed(engine) -> int:
    instrument_id = InstrumentRepository(engine=engine).create_instrument(
        market_code="US_EQ",
        exchange_mic="XNAS",
        local_symbol="AAA",
        canonical_identity="test:aaa",
        currency="USD",
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO stock_bars_daily(instrument_id,symbol,date,close) "
                "VALUES (:instrument_id,'AAA','2024-01-02',10.0),"
                "(:instrument_id,'AAA','2024-01-03',11.0)"
            ),
            {"instrument_id": instrument_id},
        )
    return instrument_id


def test_symbol_bridge_and_instrument_id_return_identical_frames(engine) -> None:
    instrument_id = _seed(engine)
    repository = BarsRepository(engine=engine)
    by_symbol = repository.load_bars("AAA", start=date(2024, 1, 2))
    by_id = repository.load_bars(instrument_id=instrument_id, start=date(2024, 1, 2))
    pd.testing.assert_frame_equal(by_symbol, by_id)


def test_instrument_first_date_filter_uses_canonical_date(engine) -> None:
    instrument_id = _seed(engine)
    frame = BarsRepository(engine=engine).load_bars(
        instrument_id=instrument_id,
        start=date(2024, 1, 3),
        end=date(2024, 1, 3),
    )
    assert frame["close"].tolist() == [11.0]


def test_load_bars_requires_an_identity(engine) -> None:
    with pytest.raises(ValueError, match="symbol ou instrument_id"):
        BarsRepository(engine=engine).load_bars()
