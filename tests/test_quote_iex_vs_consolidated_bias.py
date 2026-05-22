from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, text

from dataIntegrityEngine import sync_latest_quotes
from dataIntegrityEngine.sync_latest_quotes import _build_quote_bias_summary_from_rows


def _prepare_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_quote_snapshots (
                    symbol TEXT NOT NULL,
                    quote_date DATE NOT NULL,
                    bid_price REAL,
                    ask_price REAL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_bars_daily (
                    symbol TEXT NOT NULL,
                    date DATE NOT NULL,
                    close REAL
                )
                """
            )
        )
    return engine


def test_build_quote_iex_vs_consolidated_bias_summary_computes_abs_and_signed_bps(monkeypatch) -> None:
    engine = _prepare_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO stock_quote_snapshots(symbol, quote_date, bid_price, ask_price)
                VALUES
                    ('AAPL', '2026-04-29', 100.0, 101.0),
                    ('MSFT', '2026-04-29', 99.0, 100.0)
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO stock_bars_daily(symbol, date, close)
                VALUES
                    ('AAPL', '2026-04-29', 100.0),
                    ('MSFT', '2026-04-29', 100.0)
                """
            )
        )

    monkeypatch.setattr(sync_latest_quotes, "get_sqlalchemy_engine", lambda: engine)
    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda *args, **kwargs: ["AAPL", "MSFT"])

    payload = sync_latest_quotes.build_quote_iex_vs_consolidated_bias_summary(
        from_date=date(2026, 4, 29),
        to_date=date(2026, 4, 29),
        symbol_source="stock_scores",
        limit=2,
        start_symbol=None,
    )

    assert payload["quote_iex_vs_consolidated_status"] == "ok"
    assert payload["quote_iex_vs_consolidated_proxy"] == "same_session_mid_vs_stock_bars_daily_close"
    assert payload["quote_iex_vs_consolidated_observations"] == 2
    assert payload["quote_iex_vs_consolidated_bps"] == 50.0
    assert payload["quote_iex_vs_consolidated_signed_bps"] == 0.0
    assert payload["max_quote_iex_vs_consolidated_bps"] == 50.0
    assert payload["max_quote_iex_vs_consolidated_symbol"] == "MSFT"
    assert payload["quote_iex_vs_consolidated_window_mode"] == "historical"
    assert payload["quote_iex_vs_consolidated_window_start"] == "2026-04-29"
    assert payload["quote_iex_vs_consolidated_window_end"] == "2026-04-29"


def test_build_quote_iex_vs_consolidated_bias_summary_returns_unavailable_without_matching_close(monkeypatch) -> None:
    engine = _prepare_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO stock_quote_snapshots(symbol, quote_date, bid_price, ask_price)
                VALUES ('AAPL', '2026-04-29', 100.0, 101.0)
                """
            )
        )

    monkeypatch.setattr(sync_latest_quotes, "get_sqlalchemy_engine", lambda: engine)
    monkeypatch.setattr(sync_latest_quotes, "list_symbols_for_source", lambda *args, **kwargs: ["AAPL"])

    payload = sync_latest_quotes.build_quote_iex_vs_consolidated_bias_summary(
        from_date=date(2026, 4, 29),
        to_date=date(2026, 4, 29),
        symbol_source="stock_scores",
        limit=1,
        start_symbol=None,
    )

    assert payload["quote_iex_vs_consolidated_status"] == "unavailable"
    assert payload["quote_iex_vs_consolidated_observations"] == 0
    assert payload["quote_iex_vs_consolidated_candidates"] == 1
    assert payload["quote_iex_vs_consolidated_missing_closes"] == 1


def test_build_quote_bias_summary_from_rows_computes_abs_signed_and_max_bps() -> None:
    payload = _build_quote_bias_summary_from_rows(
        [
            {"symbol": "AAPL", "quote_date": date(2026, 4, 29), "bid_price": 99.0, "ask_price": 101.0},
            {"symbol": "MSFT", "quote_date": date(2026, 4, 29), "bid_price": 101.0, "ask_price": 103.0},
            {"symbol": "NVDA", "quote_date": date(2026, 4, 29), "bid_price": 50.0, "ask_price": None},
        ],
        {
            ("AAPL", date(2026, 4, 29)): 98.0,
            ("MSFT", date(2026, 4, 29)): 101.0,
        },
    )

    assert payload["quote_iex_vs_consolidated_status"] == "ok"
    assert payload["quote_iex_vs_consolidated_observations"] == 2
    assert payload["quote_iex_vs_consolidated_candidates"] == 2
    assert payload["quote_iex_vs_consolidated_missing_closes"] == 0
    assert payload["quote_iex_vs_consolidated_bps"] == 151.55
    assert payload["quote_iex_vs_consolidated_signed_bps"] == 151.55
    assert payload["max_quote_iex_vs_consolidated_bps"] == 204.08
    assert payload["max_quote_iex_vs_consolidated_symbol"] == "AAPL"
    assert payload["max_quote_iex_vs_consolidated_date"] == "2026-04-29"


def test_build_quote_iex_vs_consolidated_bias_summary_batches_symbols_and_decorates_payload(monkeypatch) -> None:
    quote_calls: list[tuple[list[str], date, date]] = []
    close_calls: list[tuple[list[str], date, date]] = []

    monkeypatch.setattr(
        sync_latest_quotes,
        "list_symbols_for_source",
        lambda symbol_source=None, limit=None, start_symbol=None: ["AAPL", "MSFT", "NVDA"],
    )

    def _fake_load_quote_rows_for_bias(*, symbols: list[str], from_date: date, to_date: date) -> list[dict[str, object]]:
        quote_calls.append((list(symbols), from_date, to_date))
        return [
            {
                "symbol": symbol,
                "quote_date": from_date,
                "bid_price": 99.0 + index,
                "ask_price": 101.0 + index,
            }
            for index, symbol in enumerate(symbols)
        ]

    def _fake_load_consolidated_close_map(*, symbols: list[str], from_date: date, to_date: date) -> dict[tuple[str, date], float]:
        close_calls.append((list(symbols), from_date, to_date))
        return {
            (symbol, from_date): 100.0 + index
            for index, symbol in enumerate(symbols)
        }

    monkeypatch.setattr(sync_latest_quotes, "_load_quote_rows_for_bias", _fake_load_quote_rows_for_bias)
    monkeypatch.setattr(sync_latest_quotes, "_load_consolidated_close_map", _fake_load_consolidated_close_map)
    monkeypatch.setattr(sync_latest_quotes, "_iter_symbol_batches", lambda symbols, batch_size=500: [symbols[:2], symbols[2:]])

    payload = sync_latest_quotes.build_quote_iex_vs_consolidated_bias_summary(
        from_date=date(2026, 4, 29),
        to_date=date(2026, 4, 30),
        symbol_source="stock_scores_history",
        limit=3,
        start_symbol=" msft ",
    )

    assert payload["quote_iex_vs_consolidated_status"] == "ok"
    assert payload["quote_iex_vs_consolidated_symbol_scope"] == "stock-scores-history"
    assert payload["quote_iex_vs_consolidated_symbols_requested"] == 3
    assert payload["quote_iex_vs_consolidated_window_mode"] == "historical"
    assert payload["quote_iex_vs_consolidated_window_start"] == "2026-04-29"
    assert payload["quote_iex_vs_consolidated_window_end"] == "2026-04-30"
    assert quote_calls == [
        (["AAPL", "MSFT"], date(2026, 4, 29), date(2026, 4, 30)),
        (["NVDA"], date(2026, 4, 29), date(2026, 4, 30)),
    ]
    assert close_calls == quote_calls



