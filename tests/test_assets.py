from sqlalchemy import Boolean, Column, MetaData, String, TIMESTAMP, Table

from database import assets


class _FakeScalarResult:
    def __init__(self, values):
        self._values = values

    def all(self):
        return self._values


class _FakeExecuteResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return _FakeScalarResult(self._values)


class _FakeConnection:
    def __init__(self, values):
        self.values = values
        self.statement = None

    def execute(self, statement):
        self.statement = statement
        return _FakeExecuteResult(self.values)


class _FakeConnectContext:
    def __init__(self, connection):
        self._connection = connection

    def __enter__(self):
        return self._connection

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def __init__(self, connection):
        self._connection = connection

    def connect(self):
        return _FakeConnectContext(self._connection)


class _FakeInsert:
    def __init__(self):
        self.records = None
        self.inserted = type(
            "Inserted",
            (),
            {
                "id_alpaca": "id_alpaca_inserted",
                "company_name": "company_name_inserted",
                "exchange": "exchange_inserted",
                "asset_class": "asset_class_inserted",
                "status": "status_inserted",
                "tradable": "tradable_inserted",
                "bars_available": "bars_available_inserted",
                "history_status": "history_status_inserted",
            },
        )()

    def values(self, records):
        self.records = records
        return self

    def on_duplicate_key_update(self, **kwargs):
        return ("upsert", self.records, kwargs)


class _FakeSession:
    def __init__(self):
        self.statement = None
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def execute(self, statement):
        self.statement = statement

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_get_symbols_missing_sector_filters_active_tradable_and_bars_available(monkeypatch) -> None:
    metadata = MetaData()
    stock_metadata = Table(
        "stock_metadata",
        metadata,
        Column("symbol", String(100), primary_key=True),
        Column("status", String(20)),
        Column("tradable", Boolean),
        Column("bars_available", Boolean),
        Column("sector", String(50)),
    )
    fake_connection = _FakeConnection(["AAPL", "MSFT"])

    monkeypatch.setattr(assets, "get_stock_metadata_table", lambda: stock_metadata)
    monkeypatch.setattr(assets, "get_sqlalchemy_engine", lambda: _FakeEngine(fake_connection))

    symbols = assets.get_symbols_missing_sector(limit=25)

    assert symbols == ["AAPL", "MSFT"]
    statement_sql = str(fake_connection.statement).lower()
    assert "stock_metadata.status =" in statement_sql
    assert "stock_metadata.tradable is true" in statement_sql
    assert "stock_metadata.bars_available is true" in statement_sql
    assert "stock_metadata.sector is null" in statement_sql
    assert "trim(stock_metadata.sector) =" in statement_sql
    assert "limit" in statement_sql


def test_insert_assets_to_db_uses_current_timestamp_for_last_updated(monkeypatch) -> None:
    metadata = MetaData()
    stock_metadata = Table(
        "stock_metadata",
        metadata,
        Column("symbol", String(100), primary_key=True),
        Column("id_alpaca", String(88)),
        Column("company_name", String(255)),
        Column("exchange", String(20)),
        Column("asset_class", String(20)),
        Column("status", String(20)),
        Column("tradable", Boolean),
        Column("bars_available", Boolean),
        Column("history_status", String(32)),
        Column("last_updated", TIMESTAMP),
    )
    fake_session = _FakeSession()

    monkeypatch.setattr(assets, "get_stock_metadata_table", lambda: stock_metadata)
    monkeypatch.setattr(assets, "SessionLocal", lambda: fake_session)
    monkeypatch.setattr(assets, "mysql_insert", lambda table: _FakeInsert())

    inserted = assets.insert_assets_to_db(
        [
            {
                "symbol": "AAPL",
                "id": "alpaca-id",
                "name": "Apple",
                "exchange": "NASDAQ",
                "class": "us_equity",
                "status": "active",
                "tradable": True,
            }
        ]
    )

    assert inserted == 1
    assert fake_session.committed is True
    assert fake_session.closed is True
    assert fake_session.statement[0] == "upsert"
    assert fake_session.statement[1][0]["symbol"] == "AAPL"
    assert fake_session.statement[1][0]["history_status"] == assets.HISTORY_STATUS_PENDING
    assert fake_session.statement[2]["history_status"] == "history_status_inserted"
    assert "last_updated" in fake_session.statement[2]
    assert "current_timestamp" in str(fake_session.statement[2]["last_updated"]).lower()


def test_update_symbol_history_status_updates_history_status_and_bars_available(monkeypatch) -> None:
    metadata = MetaData()
    stock_metadata = Table(
        "stock_metadata",
        metadata,
        Column("symbol", String(100), primary_key=True),
        Column("bars_available", Boolean),
        Column("history_status", String(32)),
    )
    fake_session = _FakeSession()

    monkeypatch.setattr(assets, "get_stock_metadata_table", lambda: stock_metadata)
    monkeypatch.setattr(assets, "SessionLocal", lambda: fake_session)

    updated = assets.update_symbol_history_status(
        "aapl",
        assets.HISTORY_STATUS_PROVIDER_ERROR,
        bars_available=True,
    )

    assert updated == 1
    assert fake_session.committed is True
    compiled = str(fake_session.statement)
    assert "history_status" in compiled
    assert "bars_available" in compiled


