from sqlalchemy import Boolean, Column, Float, MetaData, String, Table

from database import stock_scores


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


def test_list_candidate_symbols_filters_candidates_and_orders_by_score() -> None:
    metadata = MetaData()
    table = Table(
        "stock_scores",
        metadata,
        Column("symbol", String(20), primary_key=True),
        Column("is_candidate", Boolean),
        Column("total_score", Float),
    )
    fake_connection = _FakeConnection([" msft ", "AAPL"])

    symbols = stock_scores.list_candidate_symbols(
        engine=_FakeEngine(fake_connection),
        stock_scores=table,
        limit=5,
    )

    assert symbols == ["MSFT", "AAPL"]
    statement_sql = str(fake_connection.statement).lower()
    assert "is_candidate" in statement_sql
    assert "total_score" in statement_sql
    assert "limit" in statement_sql


def test_list_candidate_symbols_rejects_invalid_limit() -> None:
    try:
        stock_scores.list_candidate_symbols(limit=0, engine=object(), stock_scores=Table("stock_scores", MetaData()))
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("ValueError attendu")
