from sqlalchemy import Column, Float, Integer, MetaData, String, Table

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

    def mappings(self):
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


def test_list_scored_symbols_orders_by_score() -> None:
    metadata = MetaData()
    table = Table(
        "stock_scores",
        metadata,
        Column("symbol", String(20), primary_key=True),
        Column("total_score", Float),
    )
    fake_connection = _FakeConnection([" msft ", "AAPL"])

    symbols = stock_scores.list_scored_symbols(
        engine=_FakeEngine(fake_connection),
        stock_scores=table,
        limit=5,
    )

    assert symbols == ["MSFT", "AAPL"]
    statement_sql = str(fake_connection.statement).lower()
    assert "is_candidate" not in statement_sql
    assert "total_score" in statement_sql
    assert "limit" in statement_sql


def test_list_scored_symbols_rejects_invalid_limit() -> None:
    try:
        stock_scores.list_scored_symbols(limit=0, engine=object(), stock_scores=Table("stock_scores", MetaData()))
    except ValueError as exc:
        assert "limit" in str(exc)
    else:
        raise AssertionError("ValueError attendu")


def test_load_score_context_exposes_available_score_columns() -> None:
    metadata = MetaData()
    table = Table(
        "stock_scores",
        metadata,
        Column("symbol", String(20), primary_key=True),
        Column("candidate_rank", Integer),
        Column("total_score", Float),
        Column("trend_score", Float),
        Column("selector_signal_mode", String(32)),
        Column("selection_explanation", String(255)),
        Column("atr_pct_20", Float),
    )
    fake_connection = _FakeConnection(
        [
            {
                "symbol": " msft ",
                "trend_score": 0.88,
                    "selection_rank": 2,
                "selector_signal_mode": "strict",
                "selection_explanation": "breakout propre",
                "atr_pct_20": 0.032,
            },
            {
                "symbol": "AAPL",
                "trend_score": 0.83,
                    "selection_rank": 1,
                "selector_signal_mode": "strict",
                "selection_explanation": "leader sectoriel",
                "atr_pct_20": 0.028,
            },
        ]
    )

    frame = stock_scores.load_score_context(
        engine=_FakeEngine(fake_connection),
        stock_scores=table,
        limit=10,
    )

    assert frame.to_dict(orient="records") == [
        {
            "symbol": "MSFT",
            "trend_score": 0.88,
            "selection_rank": 2,
            "selector_signal_mode": "strict",
            "selection_explanation": "breakout propre",
            "atr_pct_20": 0.032,
        },
        {
            "symbol": "AAPL",
            "trend_score": 0.83,
            "selection_rank": 1,
            "selector_signal_mode": "strict",
            "selection_explanation": "leader sectoriel",
            "atr_pct_20": 0.028,
        },
    ]
    statement_sql = str(fake_connection.statement).lower()
    assert "is_candidate" not in statement_sql
    assert "selection_explanation" in statement_sql
    assert "selector_signal_mode" in statement_sql

