"""Sprint S1 — préflight explicite de la source OHLCV backtesting."""
from __future__ import annotations

from datetime import date
from typing import cast

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from backtesting import data_loader


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeEngine:
    def connect(self):
        return _FakeConn()


def test_preflight_required_bars_data_source_returns_warning_when_window_is_mixed(monkeypatch):
    class FakeInspector:
        def get_columns(self, table_name):
            assert table_name == "stock_bars_daily"
            return [
                {"name": "symbol"},
                {"name": "date"},
                {"name": "open"},
                {"name": "high"},
                {"name": "low"},
                {"name": "close"},
                {"name": "volume"},
                {"name": "data_source"},
            ]

    monkeypatch.setattr(data_loader, "inspect", lambda _engine: FakeInspector())
    monkeypatch.setattr(
        data_loader.pd,
        "read_sql",
        lambda query, conn, params=None: pd.DataFrame(
            {
                "source": ["eodhd_eod", "alpaca_iex"],
                "rows_n": [95, 5],
                "min_trade_date": ["2025-01-01", "2025-01-03"],
                "max_trade_date": ["2025-01-31", "2025-01-31"],
            }
        ),
    )

    payload = data_loader.preflight_required_bars_data_source(
        cast(Engine, cast(object, _FakeEngine())),
        date(2025, 1, 1),
        date(2025, 1, 31),
    )

    assert payload["required_data_source"] == "eodhd_eod"
    assert payload["required_rows"] == 95
    assert payload["rows_total"] == 100
    assert payload["status"] == "warning"
    assert payload["mixed_sources_detected"] is True
    assert payload["degraded_reasons"] == ["mixed_data_source_window"]


def test_preflight_required_bars_data_source_fails_when_eodhd_rows_are_absent(monkeypatch):
    class FakeInspector:
        def get_columns(self, table_name):
            return [
                {"name": "symbol"},
                {"name": "date"},
                {"name": "data_source"},
            ]

    monkeypatch.setattr(data_loader, "inspect", lambda _engine: FakeInspector())
    monkeypatch.setattr(
        data_loader.pd,
        "read_sql",
        lambda query, conn, params=None: pd.DataFrame(
            {
                "source": ["alpaca_iex"],
                "rows_n": [42],
                "min_trade_date": ["2025-01-01"],
                "max_trade_date": ["2025-01-31"],
            }
        ),
    )

    with pytest.raises(RuntimeError, match="eodhd_eod"):
        data_loader.preflight_required_bars_data_source(
            cast(Engine, cast(object, _FakeEngine())),
            date(2025, 1, 1),
            date(2025, 1, 31),
        )


