from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from database import selector_reference


def _create_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_list_active_tradable_symbols_filters_blocked_history_statuses(monkeypatch) -> None:
    engine = _create_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_metadata (
                    symbol TEXT PRIMARY KEY,
                    status TEXT,
                    tradable BOOLEAN,
                    bars_available BOOLEAN,
                    history_status TEXT,
                    asset_class TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO stock_metadata (symbol, status, tradable, bars_available, history_status, asset_class)
                VALUES
                    ('AAPL', 'active', 1, 1, 'ready', 'us_equity'),
                    ('MSFT', 'active', 1, 1, 'pending', 'us_equity'),
                    ('ERR', 'active', 1, 1, 'provider_error', 'us_equity'),
                    ('STALE', 'active', 1, 1, 'suspended_or_stale', 'us_equity'),
                    ('AMD', 'active', 1, 0, 'no_history', 'us_equity'),
                    ('QQQ', 'active', 1, 1, 'ready', 'etf')
                """
            )
        )

    monkeypatch.setattr(selector_reference, "get_sqlalchemy_engine", lambda: engine)

    assert selector_reference.list_active_tradable_symbols() == ["AAPL", "MSFT"]


def test_list_active_tradable_symbols_falls_back_when_history_status_column_is_absent(monkeypatch) -> None:
    engine = _create_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_metadata (
                    symbol TEXT PRIMARY KEY,
                    status TEXT,
                    tradable BOOLEAN,
                    bars_available BOOLEAN,
                    asset_class TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO stock_metadata (symbol, status, tradable, bars_available, asset_class)
                VALUES
                    ('AAPL', 'active', 1, 1, 'us_equity'),
                    ('MSFT', 'inactive', 1, 1, 'us_equity'),
                    ('AMD', 'active', 1, 0, 'us_equity')
                """
            )
        )

    monkeypatch.setattr(selector_reference, "get_sqlalchemy_engine", lambda: engine)

    assert selector_reference.list_active_tradable_symbols() == ["AAPL"]

