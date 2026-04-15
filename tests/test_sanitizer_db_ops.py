from datetime import date, datetime
from decimal import Decimal

import polars as pl
from sqlalchemy import Column, DateTime, Integer, MetaData, Numeric, String, Table, create_engine

from database import sanitizer_db_ops
from database.sanitizer_db_ops import get_stock_bars


class _FakeUpsertConnection:
    def __init__(self) -> None:
        self.executed = None

    def execute(self, statement):
        self.executed = statement


class _FakeInsert:
    def __init__(self) -> None:
        self.records = None
        self.inserted = {
            "open": "open_inserted",
            "high": "high_inserted",
            "low": "low_inserted",
            "close": "close_inserted",
            "volume": "volume_inserted",
            "adj_close": "adj_close_inserted",
            "vwap": "vwap_inserted",
            "daily_return": "daily_return_inserted",
            "is_filled": "is_filled_inserted",
        }

    def values(self, records):
        self.records = records
        return self

    def on_duplicate_key_update(self, **kwargs):
        return ("upsert", self.records, kwargs)


def _build_stock_bars_table(metadata: MetaData) -> Table:
    return Table(
        "stock_bars",
        metadata,
        Column("symbol", String(10), nullable=False),
        Column("timeframe", String(5), nullable=False),
        Column("timestamp", DateTime, nullable=False),
        Column("open_price", Numeric(20, 8), nullable=False),
        Column("high_price", Numeric(20, 8), nullable=False),
        Column("low_price", Numeric(20, 8), nullable=False),
        Column("close_price", Numeric(20, 8), nullable=False),
        Column("trade_count", Numeric(20, 8), nullable=True),
        Column("volume", Integer, nullable=False),
        Column("vwa_price", Numeric(20, 8), nullable=True),
    )


def test_get_stock_bars_filters_and_sorts_from_start_date() -> None:
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stock_bars = _build_stock_bars_table(metadata)
    metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            stock_bars.insert(),
            [
                {
                    "symbol": "SPY",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 4, 0, 0, 0),
                    "open_price": Decimal("103.0"),
                    "high_price": Decimal("104.0"),
                    "low_price": Decimal("102.0"),
                    "close_price": Decimal("103.5"),
                    "trade_count": Decimal("12"),
                    "volume": 1300,
                    "vwa_price": Decimal("103.25"),
                },
                {
                    "symbol": "SPY",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 2, 0, 0, 0),
                    "open_price": Decimal("100.0"),
                    "high_price": Decimal("101.0"),
                    "low_price": Decimal("99.0"),
                    "close_price": Decimal("100.5"),
                    "trade_count": Decimal("10"),
                    "volume": 1100,
                    "vwa_price": Decimal("100.25"),
                },
                {
                    "symbol": "SPY",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 3, 0, 0, 0),
                    "open_price": Decimal("101.0"),
                    "high_price": Decimal("102.0"),
                    "low_price": Decimal("100.0"),
                    "close_price": Decimal("101.5"),
                    "trade_count": None,
                    "volume": 1200,
                    "vwa_price": None,
                },
                {
                    "symbol": "SPY",
                    "timeframe": "1H",
                    "timestamp": datetime(2024, 1, 3, 10, 0, 0),
                    "open_price": Decimal("1.0"),
                    "high_price": Decimal("1.0"),
                    "low_price": Decimal("1.0"),
                    "close_price": Decimal("1.0"),
                    "trade_count": Decimal("1"),
                    "volume": 1,
                    "vwa_price": Decimal("1.0"),
                },
                {
                    "symbol": "QQQ",
                    "timeframe": "1D",
                    "timestamp": datetime(2024, 1, 3, 0, 0, 0),
                    "open_price": Decimal("1.0"),
                    "high_price": Decimal("1.0"),
                    "low_price": Decimal("1.0"),
                    "close_price": Decimal("1.0"),
                    "trade_count": Decimal("1"),
                    "volume": 1,
                    "vwa_price": Decimal("1.0"),
                },
            ],
        )

        bars = get_stock_bars(conn, stock_bars, "SPY", "1D", date(2024, 1, 3))

    assert [bar["t"] for bar in bars] == [datetime(2024, 1, 3, 0, 0, 0), datetime(2024, 1, 4, 0, 0, 0)]
    assert [bar["c"] for bar in bars] == [101.5, 103.5]
    assert bars[0]["n"] == 0
    assert bars[0]["vw"] is None
    assert all(isinstance(bar["v"], int) for bar in bars)


def test_upsert_stock_bars_daily_uses_current_timestamp_for_last_updated(monkeypatch) -> None:
    metadata = MetaData()
    stock_bars_daily = Table(
        "stock_bars_daily",
        metadata,
        Column("symbol", String(10), primary_key=True),
        Column("date", DateTime, primary_key=True),
        Column("open", Numeric(20, 8), nullable=False),
        Column("high", Numeric(20, 8), nullable=False),
        Column("low", Numeric(20, 8), nullable=False),
        Column("close", Numeric(20, 8), nullable=False),
        Column("volume", Integer, nullable=False),
        Column("adj_close", Numeric(20, 8), nullable=False),
        Column("vwap", Numeric(20, 8), nullable=True),
        Column("daily_return", Numeric(20, 8), nullable=True),
        Column("is_filled", Integer, nullable=False),
        Column("last_updated", DateTime, nullable=True),
    )
    fake_insert = _FakeInsert()
    fake_conn = _FakeUpsertConnection()
    monkeypatch.setattr(sanitizer_db_ops, "mysql_insert", lambda table: fake_insert)

    df = pl.DataFrame(
        {
            "date": [datetime(2024, 1, 2, 0, 0, 0)],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.5],
            "volume": [1000],
            "adj_close": [100.5],
            "vwap": [100.25],
            "daily_return": [0.01],
            "is_filled": [False],
        }
    )

    inserted = sanitizer_db_ops.upsert_stock_bars_daily(fake_conn, stock_bars_daily, "SPY", df)

    assert inserted == 1
    assert fake_conn.executed[0] == "upsert"
    update_dict = fake_conn.executed[2]
    assert "symbol" not in update_dict
    assert "date" not in update_dict
    assert update_dict["open"] == "open_inserted"
    assert "last_updated" in update_dict
    assert "current_timestamp" in str(update_dict["last_updated"]).lower()


