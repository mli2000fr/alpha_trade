from sqlalchemy import Boolean, Column, MetaData, String, Table

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

