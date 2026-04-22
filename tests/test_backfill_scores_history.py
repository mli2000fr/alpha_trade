from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text

from backtesting.backfill_scores_history import BackfillScoresHistoryService


def _build_sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE stock_bars_daily (symbol TEXT, `date` DATE)"))
        conn.execute(text("CREATE TABLE stock_scores_history (snapshot_date DATE, symbol TEXT)"))
    return engine


def test_resolve_end_date_uses_previous_bar_before_first_existing_snapshot() -> None:
    engine = _build_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO stock_bars_daily(symbol, `date`) VALUES (:s, :d)"),
            [
                {"s": "AAPL", "d": date(2026, 4, 16)},
                {"s": "AAPL", "d": date(2026, 4, 17)},
            ],
        )
        conn.execute(
            text("INSERT INTO stock_scores_history(snapshot_date, symbol) VALUES (:d, :s)"),
            [{"d": date(2026, 4, 19), "s": "AAPL"}],
        )

    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)
    resolved = service.resolve_end_date(date(2025, 1, 1))
    assert resolved == date(2026, 4, 17)


def test_list_trading_dates_skips_existing_days() -> None:
    engine = _build_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO stock_bars_daily(symbol, `date`) VALUES (:s, :d)"),
            [
                {"s": "AAPL", "d": date(2026, 4, 15)},
                {"s": "AAPL", "d": date(2026, 4, 16)},
                {"s": "AAPL", "d": date(2026, 4, 17)},
            ],
        )
        conn.execute(
            text("INSERT INTO stock_scores_history(snapshot_date, symbol) VALUES (:d, :s)"),
            [{"d": date(2026, 4, 16), "s": "AAPL"}],
        )

    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)
    dates = service.list_trading_dates(date(2026, 4, 15), date(2026, 4, 17), overwrite_existing=False)
    assert dates == [date(2026, 4, 15), date(2026, 4, 17)]


def test_to_history_snapshot_normalizes_required_columns() -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)
    df = pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "sector": ["Tech"],
            "liquidity_val": [123.0],
            "relative_strength_index": [99.0],
            "historical_range_score": [88.0],
            "total_score": [77.0],
            "trend_score": [0.8],
            "vcp_score": [0.6],
            "final_score": [0.7],
            "is_candidate": [1],
            "sentiment_net_agg": [0.1],
            "sector_impact_agg": [0.0],
            "final_score_sentiment": [0.68],
            "signal_active": [True],
        }
    )

    history = service._to_history_snapshot(df, date(2026, 4, 17))
    assert history.iloc[0]["snapshot_date"] == date(2026, 4, 17)
    assert history.iloc[0]["symbol"] == "AAPL"
    assert history.iloc[0]["is_candidate"] == 1
    assert history.iloc[0]["signal_active"] == 1
    assert history.iloc[0]["anomaly_count"] == 0
    assert history.iloc[0]["missing_days_count"] == 0


def test_backfill_orchestrates_dates_and_persistence(monkeypatch) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    monkeypatch.setattr(service, "resolve_end_date", lambda start_date, explicit_end_date=None: date(2026, 4, 17))
    monkeypatch.setattr(service, "list_trading_dates", lambda start_date, end_date, overwrite_existing=False: [date(2026, 4, 15), date(2026, 4, 16)])
    monkeypatch.setattr(
        service,
        "build_snapshot_for_date",
        lambda as_of_date: pd.DataFrame({
            "snapshot_date": [as_of_date],
            "symbol": ["AAPL"],
            "sector": ["Tech"],
            "liquidity_val": [1.0],
            "relative_strength_index": [1.0],
            "historical_range_score": [1.0],
            "total_score": [1.0],
            "trend_score": [1.0],
            "vcp_score": [1.0],
            "final_score": [1.0],
            "is_candidate": [1],
            "sentiment_net_agg": [0.0],
            "sector_impact_agg": [0.0],
            "final_score_sentiment": [1.0],
            "signal_active": [1],
            "anomaly_count": [0],
            "missing_days_count": [0],
        }),
    )
    inserted_dates: list[date] = []
    monkeypatch.setattr(
        service,
        "persist_snapshot",
        lambda snapshot_df, overwrite_existing=False: inserted_dates.append(snapshot_df.iloc[0]["snapshot_date"]) or len(snapshot_df),
    )

    result = service.backfill(date(2026, 4, 15), limit_days=None)
    assert result.trading_days_processed == 2
    assert result.rows_inserted == 2
    assert inserted_dates == [date(2026, 4, 15), date(2026, 4, 16)]


def test_resolve_pit_scanner_disables_overlay_filters_when_historical_coverage_is_missing() -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    scanner, quotes_available, earnings_available = service._resolve_pit_scanner(date(2026, 4, 17))

    assert quotes_available is False
    assert earnings_available is False
    assert scanner.config.max_spread_bps is None
    assert scanner.config.earnings_blackout_days is None
    assert service.scanner_config.max_spread_bps == 25.0
    assert service.scanner_config.earnings_blackout_days == 3


def test_resolve_pit_scanner_keeps_strict_overlay_filters_when_historical_coverage_exists() -> None:
    engine = _build_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE stock_quote_snapshots (symbol TEXT, quote_date DATE, spread_bps REAL)"))
        conn.execute(text("CREATE TABLE stock_earnings_calendar (symbol TEXT, earnings_date DATE)"))
        conn.execute(
            text("INSERT INTO stock_quote_snapshots(symbol, quote_date, spread_bps) VALUES (:s, :d, :v)"),
            [{"s": "AAPL", "d": date(2026, 4, 16), "v": 12.0}],
        )
        conn.execute(
            text("INSERT INTO stock_earnings_calendar(symbol, earnings_date) VALUES (:s, :d)"),
            [{"s": "AAPL", "d": date(2026, 4, 18)}],
        )

    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    scanner, quotes_available, earnings_available = service._resolve_pit_scanner(date(2026, 4, 17))

    assert quotes_available is True
    assert earnings_available is True
    assert scanner.config.max_spread_bps == 25.0
    assert scanner.config.earnings_blackout_days == 3


def test_resolve_pit_scanner_disables_only_missing_overlay_filter() -> None:
    engine = _build_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE stock_quote_snapshots (symbol TEXT, quote_date DATE, spread_bps REAL)"))
        conn.execute(
            text("INSERT INTO stock_quote_snapshots(symbol, quote_date, spread_bps) VALUES (:s, :d, :v)"),
            [{"s": "AAPL", "d": date(2026, 4, 16), "v": 12.0}],
        )

    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    scanner, quotes_available, earnings_available = service._resolve_pit_scanner(date(2026, 4, 17))

    assert quotes_available is True
    assert earnings_available is False
    assert scanner.config.max_spread_bps == 25.0
    assert scanner.config.earnings_blackout_days is None


def test_compute_selector_snapshot_logs_aggregated_pit_summary(monkeypatch, caplog) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    class _FakeScanner:
        def compute_factors(self, market_data: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame({"symbol": market_data["symbol"].astype(str).unique()})

        def fetch_instrument_metadata(self, symbols: list[str]) -> pd.DataFrame:
            return pd.DataFrame()

        def fetch_quote_snapshots(self, symbols: list[str], *, reference_date: date | None = None) -> pd.DataFrame:
            return pd.DataFrame()

        def fetch_next_earnings(self, symbols: list[str], *, reference_date: date | None = None) -> pd.DataFrame:
            return pd.DataFrame()

        def merge_scores(self, computed: pd.DataFrame, aux_scores: pd.DataFrame) -> pd.DataFrame:
            return computed.copy()

        def _enrich_and_filter_equities(self, merged: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame:
            return merged

        def _merge_optional_symbol_overlays(
            self,
            merged: pd.DataFrame,
            quotes_df: pd.DataFrame,
            earnings_df: pd.DataFrame,
        ) -> pd.DataFrame:
            return merged

        def _apply_filters_with_stats(self, merged: pd.DataFrame):
            filtered = merged.iloc[:1].copy()
            stats = {
                "input": 2,
                "output": 1,
                "rejected_etf": 0,
                "rejected_history": 1,
                "rejected_price": 0,
                "rejected_market_liquidity": 0,
                "rejected_volatility": 0,
                "rejected_atr": 0,
                "rejected_relative_strength": 0,
                "rejected_ma200": 0,
                "rejected_high_52w": 0,
                "rejected_weekly": 0,
                "rejected_market_cap": 0,
                "rejected_beta": 0,
                "rejected_spread": 0,
                "rejected_earnings_blackout": 0,
                "rejected_score_liquidity": 0,
                "rejected_anomalies": 0,
                "rejected_missing_days": 0,
            }
            return filtered, stats

        def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

        def rank_and_select(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

    screener_df = pd.DataFrame({"symbol": ["AAA", "BBB"]})
    monkeypatch.setattr(
        service,
        "_resolve_pit_scanner",
        lambda as_of_date: (_FakeScanner(), True, False),
    )
    monkeypatch.setattr(
        service,
        "_load_market_data",
        lambda symbols, as_of_date: pd.DataFrame({"symbol": symbols}),
    )

    with caplog.at_level(logging.INFO):
        result = service._compute_selector_snapshot(screener_df, date(2026, 4, 17))

    assert len(result) == 1
    assert "Backfill PIT summary | date=2026-04-17 quotes_available=True earnings_available=False avant_filtres=2 apres_filtres=1" in caplog.text
    assert "rejet_historique=1" in caplog.text


