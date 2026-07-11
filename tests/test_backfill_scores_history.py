from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from backtesting.backfill_scores_history import BackfillScoresHistoryService, SELECTOR_FILTER_STAT_KEYS
from screener.models import ScreenerConfig


def _build_sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE stock_bars_daily (symbol TEXT, `date` DATE, data_source TEXT DEFAULT 'eodhd_eod')"))
        conn.execute(
            text(
                "CREATE TABLE stock_scores_history (snapshot_date DATE, capital_preset_key TEXT DEFAULT 'capital_0_2000', symbol TEXT)"
            )
        )
    return engine


def test_backfill_service_defaults_to_strict_swing_cash_screener_config() -> None:
    service = BackfillScoresHistoryService(engine=_build_sqlite_engine(), screener_max_workers=1)

    assert service.screener_config == ScreenerConfig.strict_swing_cash()


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


def test_resolve_end_date_ignores_existing_snapshot_from_other_capital_preset() -> None:
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
            text(
                "INSERT INTO stock_scores_history(snapshot_date, capital_preset_key, symbol) VALUES (:d, :p, :s)"
            ),
            [{"d": date(2026, 4, 17), "p": "capital_other", "s": "AAPL"}],
        )

    service = BackfillScoresHistoryService(
        engine=engine,
        screener_max_workers=1,
        capital_preset_key="capital_current",
    )

    resolved = service.resolve_end_date(date(2026, 4, 16))

    assert resolved == date(2026, 4, 17)


def test_list_trading_dates_keeps_days_existing_only_for_other_capital_preset() -> None:
    engine = _build_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO stock_bars_daily(symbol, `date`) VALUES (:s, :d)"),
            [
                {"s": "AAPL", "d": date(2026, 4, 15)},
                {"s": "AAPL", "d": date(2026, 4, 16)},
            ],
        )
        conn.execute(
            text(
                "INSERT INTO stock_scores_history(snapshot_date, capital_preset_key, symbol) VALUES (:d, :p, :s)"
            ),
            [{"d": date(2026, 4, 16), "p": "capital_other", "s": "AAPL"}],
        )

    service = BackfillScoresHistoryService(
        engine=engine,
        screener_max_workers=1,
        capital_preset_key="capital_current",
    )

    dates = service.list_trading_dates(date(2026, 4, 15), date(2026, 4, 16), overwrite_existing=False)

    assert dates == [date(2026, 4, 15), date(2026, 4, 16)]


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
            "selection_rank": [1],
            "sentiment_net_agg": [0.1],
            "sector_impact_agg": [0.0],
            "final_score_sentiment": [0.68],
            "signal_active": [True],
        }
    )

    history = service._to_history_snapshot(df, date(2026, 4, 17))
    assert history.iloc[0]["snapshot_date"] == date(2026, 4, 17)
    assert history.iloc[0]["symbol"] == "AAPL"
    assert history.iloc[0]["selection_rank"] == 1
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
        lambda as_of_date, **kwargs: pd.DataFrame({
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
            "selection_rank": [1],
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


def test_backfill_persists_completed_days_before_later_interruption(monkeypatch) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    monkeypatch.setattr(service, "resolve_end_date", lambda start_date, explicit_end_date=None: date(2026, 4, 16))
    monkeypatch.setattr(
        service,
        "list_trading_dates",
        lambda start_date, end_date, overwrite_existing=False: [date(2026, 4, 15), date(2026, 4, 16)],
    )

    def _build_snapshot(as_of_date: date, **kwargs) -> pd.DataFrame:
        if as_of_date == date(2026, 4, 16):
            raise RuntimeError("stop here")
        return pd.DataFrame(
            {
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
                "selection_rank": [1],
                "sentiment_net_agg": [0.0],
                "sector_impact_agg": [0.0],
                "final_score_sentiment": [1.0],
                "signal_active": [1],
                "anomaly_count": [0],
                "missing_days_count": [0],
            }
        )

    inserted_dates: list[date] = []
    monkeypatch.setattr(service, "build_snapshot_for_date", _build_snapshot)
    monkeypatch.setattr(
        service,
        "persist_snapshot",
        lambda snapshot_df, overwrite_existing=False: inserted_dates.append(snapshot_df.iloc[0]["snapshot_date"]) or len(snapshot_df),
    )

    try:
        service.backfill(date(2026, 4, 15), limit_days=None)
    except RuntimeError as exc:
        assert str(exc) == "stop here"
    else:
        raise AssertionError("Une interruption était attendue")

    assert inserted_dates == [date(2026, 4, 15)]


def test_resolve_pit_scanner_disables_overlay_filters_when_historical_coverage_is_missing() -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    scanner, quotes_available, earnings_available = service._resolve_pit_scanner(date(2026, 4, 17))

    assert quotes_available is False
    assert earnings_available is False
    assert scanner.config.max_spread_bps is None
    assert scanner.config.earnings_blackout_days is None
    assert service.scanner_config.max_spread_bps == 40.0
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
    assert scanner.config.max_spread_bps == 40.0
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
    assert scanner.config.max_spread_bps == 40.0
    assert scanner.config.earnings_blackout_days is None


def test_resolve_pit_scanner_treats_null_or_stale_quotes_as_missing_coverage() -> None:
    engine = _build_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE stock_quote_snapshots (symbol TEXT, quote_date DATE, spread_bps REAL)"))
        conn.execute(
            text("INSERT INTO stock_quote_snapshots(symbol, quote_date, spread_bps) VALUES (:s, :d, :v)"),
            [
                {"s": "NULLSPREAD", "d": date(2026, 4, 16), "v": None},
                {"s": "STALE", "d": date(2026, 4, 1), "v": 12.0},
            ],
        )

    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    scanner, quotes_available, earnings_available = service._resolve_pit_scanner(date(2026, 4, 17))

    assert quotes_available is False
    assert earnings_available is False
    assert scanner.config.max_spread_bps is None


def test_prepare_pit_quote_snapshots_filters_stale_quotes_and_measures_coverage() -> None:
    service = BackfillScoresHistoryService(engine=_build_sqlite_engine(), screener_max_workers=1)
    quotes_df = pd.DataFrame(
        [
            {"symbol": "AAA", "quote_date": pd.Timestamp("2026-04-17"), "spread_bps": 12.0},
            {"symbol": "BBB", "quote_date": pd.Timestamp("2026-04-10"), "spread_bps": 15.0},
            {"symbol": "CCC", "quote_date": pd.Timestamp("2026-04-17"), "spread_bps": pd.NA},
        ]
    )

    usable_quotes, diagnostics = service._prepare_pit_quote_snapshots(
        ["AAA", "BBB", "CCC"],
        quotes_df,
        date(2026, 4, 17),
    )

    assert usable_quotes["symbol"].tolist() == ["AAA"]
    assert diagnostics["covered_symbols"] == 1
    assert diagnostics["stale_symbols"] == 1
    assert diagnostics["missing_spread_symbols"] == 1
    assert diagnostics["coverage_pct"] == pytest.approx(33.33)
    assert diagnostics["spread_filter_coverage_ok"] is False


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
                "rejected_market_cap_stale": 1,
                "rejected_beta": 0,
                "rejected_spread": 0,
                "rescued_spread_iex": 1,
                "rejected_earnings_blackout": 0,
                "rejected_score_liquidity": 0,
                "rejected_sanitizer": 1,
                "rejected_anomalies": 0,
                "rejected_missing_days": 0,
                "future_filter_key": 3,
            }
            return filtered, stats

        def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

        def rank_and_select(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

        def rank_and_select_short(self, df: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame()

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
    monkeypatch.setattr(service, "_build_scanner_with_overrides", lambda **kwargs: _FakeScanner())

    with caplog.at_level(logging.INFO):
        result = service._compute_selector_snapshot(screener_df, date(2026, 4, 17))

    assert len(result) == 1
    assert "Backfill PIT summary | date=2026-04-17 quotes_available=True earnings_available=False avant_filtres=2 apres_filtres=1" in caplog.text
    assert "rejet_historique=1" in caplog.text
    assert "rejet_market_cap_stale=1" in caplog.text
    assert "rescues_spread_iex=1" in caplog.text
    assert "rejet_sanitizer=1" in caplog.text


def test_compute_selector_snapshot_disables_spread_filter_when_quote_coverage_is_too_low(monkeypatch, caplog) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)

    class _FakeScanner:
        def __init__(self, max_spread_bps: float | None) -> None:
            self.config = type(service.scanner_config)(chunk_size=10, selection_size=3, max_spread_bps=max_spread_bps)

        def compute_factors(self, market_data: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame({"symbol": market_data["symbol"].astype(str).unique()})

        def fetch_instrument_metadata(self, symbols: list[str]) -> pd.DataFrame:
            return pd.DataFrame()

        def fetch_quote_snapshots(self, symbols: list[str], *, reference_date: date | None = None) -> pd.DataFrame:
            return pd.DataFrame(
                [{"symbol": symbols[0], "quote_date": pd.Timestamp(reference_date), "spread_bps": 10.0}]
            )

        def fetch_next_earnings(self, symbols: list[str], *, reference_date: date | None = None) -> pd.DataFrame:
            return pd.DataFrame()

        def merge_scores(self, computed: pd.DataFrame, aux_scores: pd.DataFrame) -> pd.DataFrame:
            return computed.copy()

        def _enrich_and_filter_equities(self, merged: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame:
            return merged

        def _merge_optional_symbol_overlays(self, merged: pd.DataFrame, quotes_df: pd.DataFrame, earnings_df: pd.DataFrame) -> pd.DataFrame:
            return merged

        def _apply_filters_with_stats(self, merged: pd.DataFrame):
            if self.config.max_spread_bps is None:
                stats = {key: 0 for key in SELECTOR_FILTER_STAT_KEYS} | {"input": len(merged), "output": len(merged)}
                return merged.copy(), stats
            stats = {key: 0 for key in SELECTOR_FILTER_STAT_KEYS} | {"input": len(merged), "output": 0, "rejected_spread": len(merged)}
            return merged.iloc[0:0].copy(), stats

        def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

        def rank_and_select(self, df: pd.DataFrame) -> pd.DataFrame:
            selected = df.head(1).copy()
            selected["selection_rank"] = 1
            return selected

        def rank_and_select_short(self, df: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame()

    strict_scanner = _FakeScanner(max_spread_bps=40.0)
    relaxed_scanner = _FakeScanner(max_spread_bps=None)
    screener_df = pd.DataFrame({"symbol": ["AAA", "BBB", "CCC"]})

    monkeypatch.setattr(service, "_resolve_pit_scanner", lambda as_of_date: (strict_scanner, True, False))
    monkeypatch.setattr(service, "_build_scanner_with_overrides", lambda **kwargs: relaxed_scanner)
    monkeypatch.setattr(
        service,
        "_load_market_data",
        lambda symbols, as_of_date: pd.DataFrame({"symbol": symbols}),
    )

    with caplog.at_level(logging.INFO):
        result = service._compute_selector_snapshot(screener_df, date(2026, 4, 17))

    assert len(result) == 3
    assert int(result["selection_rank"].notna().sum()) == 1
    assert "couverture quotes PIT insuffisante pour filtre spread" in caplog.text
    assert "spread_filter_active=False" in caplog.text


def test_get_symbol_chunks_caches_iterated_universe(monkeypatch) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)
    calls: list[int] = []

    monkeypatch.setattr(
        "backtesting.backfill_scores_history.iter_symbol_chunks",
        lambda current_engine, chunk_size: calls.append(chunk_size) or iter([["AAA", "BBB"], ["CCC"]]),
    )

    first = service._get_symbol_chunks()
    second = service._get_symbol_chunks()

    assert first == (("AAA", "BBB"), ("CCC",))
    assert second == first
    assert calls == [service.screener_config.chunk_size]


def test_compute_selector_snapshot_prefetches_metadata_and_overlays_once_per_day(monkeypatch) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=1)
    service.scanner_config = type(service.scanner_config)(chunk_size=2)

    calls = {"metadata": 0, "quotes": 0, "earnings": 0}

    class _FakeScanner:
        def compute_factors(self, market_data: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame({"symbol": market_data["symbol"].astype(str).unique()})

        def fetch_instrument_metadata(self, symbols: list[str]) -> pd.DataFrame:
            calls["metadata"] += 1
            return pd.DataFrame({"symbol": symbols, "asset_class": ["us_equity"] * len(symbols)})

        def fetch_quote_snapshots(self, symbols: list[str], *, reference_date: date | None = None) -> pd.DataFrame:
            calls["quotes"] += 1
            return pd.DataFrame({"symbol": symbols, "quote_date": [reference_date] * len(symbols), "spread_bps": [10.0] * len(symbols)})

        def fetch_next_earnings(self, symbols: list[str], *, reference_date: date | None = None) -> pd.DataFrame:
            calls["earnings"] += 1
            return pd.DataFrame({"symbol": symbols, "earnings_date": [reference_date] * len(symbols), "days_to_earnings": [10] * len(symbols), "earnings_blackout": [0] * len(symbols)})

        def merge_scores(self, computed: pd.DataFrame, aux_scores: pd.DataFrame) -> pd.DataFrame:
            return computed.merge(aux_scores, on="symbol", how="left")

        def _enrich_and_filter_equities(self, merged: pd.DataFrame, metadata_df: pd.DataFrame) -> pd.DataFrame:
            return merged.merge(metadata_df[["symbol"]], on="symbol", how="inner")

        def _merge_optional_symbol_overlays(self, merged: pd.DataFrame, quotes_df: pd.DataFrame, earnings_df: pd.DataFrame) -> pd.DataFrame:
            return merged

        def _apply_filters_with_stats(self, merged: pd.DataFrame):
            return merged.copy(), {key: 0 for key in SELECTOR_FILTER_STAT_KEYS} | {"input": len(merged), "output": len(merged)}

        def _apply_factor_neutralization(self, df: pd.DataFrame) -> pd.DataFrame:
            return df

        def rank_and_select(self, df: pd.DataFrame) -> pd.DataFrame:
            return df.head(2)

        def rank_and_select_short(self, df: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
            return pd.DataFrame()

    screener_df = pd.DataFrame(
        {
            "symbol": ["AAA", "BBB", "CCC", "DDD"],
            "liquidity_val": [1.0, 1.0, 1.0, 1.0],
            "relative_strength_index": [100.0, 100.0, 100.0, 100.0],
            "historical_range_score": [80.0, 80.0, 80.0, 80.0],
            "total_score": [1.0, 1.0, 1.0, 1.0],
        }
    )

    monkeypatch.setattr(service, "_resolve_pit_scanner", lambda as_of_date: (_FakeScanner(), True, True))
    monkeypatch.setattr(
        service,
        "_load_market_data",
        lambda symbols, as_of_date: pd.DataFrame({"symbol": symbols}),
    )

    result = service._compute_selector_snapshot(screener_df, date(2026, 4, 17))

    assert not result.empty
    assert calls == {"metadata": 1, "quotes": 1, "earnings": 1}


def test_backfill_reuses_single_screener_pool_across_trading_days(monkeypatch) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=2)
    created_executors: list[object] = []
    shutdown_calls: list[bool] = []

    class _ImmediateFuture:
        def __init__(self, value: pd.DataFrame) -> None:
            self._value = value

        def result(self) -> pd.DataFrame:
            return self._value

    class _FakeExecutor:
        def __init__(self, max_workers: int | None = None) -> None:
            self.max_workers = max_workers
            created_executors.append(self)

        def submit(self, fn, *args, **kwargs):
            return _ImmediateFuture(fn(*args, **kwargs))

        def shutdown(self, wait: bool = True) -> None:
            shutdown_calls.append(wait)

    monkeypatch.setattr(service, "resolve_end_date", lambda start_date, explicit_end_date=None: date(2026, 4, 16))
    monkeypatch.setattr(
        service,
        "list_trading_dates",
        lambda start_date, end_date, overwrite_existing=False: [date(2026, 4, 15), date(2026, 4, 16)],
    )
    monkeypatch.setattr(
        "backtesting.backfill_scores_history.ProcessPoolExecutor",
        _FakeExecutor,
    )
    monkeypatch.setattr(
        "backtesting.backfill_scores_history.wait",
        lambda pending, return_when=None: (set(pending), set()),
    )
    monkeypatch.setattr(
        "backtesting.backfill_scores_history.load_spy_return_6m",
        lambda engine, config, as_of_date=None: 0.05,
    )
    monkeypatch.setattr(
        "backtesting.backfill_scores_history.iter_symbol_chunks",
        lambda engine, chunk_size: iter([["AAA", "BBB"]]),
    )
    monkeypatch.setattr(
        "backtesting.backfill_scores_history.screener_process_chunk",
        lambda symbol_chunk, config_dict, spy_return_6m, as_of_iso: pd.DataFrame(
            {
                "symbol": [symbol_chunk[0]],
                "liquidity_val": [1.0],
                "relative_strength_index": [100.0],
                "historical_range_score": [80.0],
                "total_score": [1.0],
            }
        ),
    )
    monkeypatch.setattr(service, "_compute_selector_snapshot", lambda screener_df, as_of_date: pd.DataFrame())

    service.backfill(date(2026, 4, 15), limit_days=None)

    assert len(created_executors) == 1
    assert created_executors[0].max_workers == 2
    assert shutdown_calls == [True]


def test_backfill_closes_screener_pool_when_snapshot_build_fails(monkeypatch) -> None:
    engine = _build_sqlite_engine()
    service = BackfillScoresHistoryService(engine=engine, screener_max_workers=2)
    shutdown_calls: list[bool] = []

    class _FakeExecutor:
        def __init__(self, max_workers: int | None = None) -> None:
            self.max_workers = max_workers

        def shutdown(self, wait: bool = True) -> None:
            shutdown_calls.append(wait)

    monkeypatch.setattr(service, "resolve_end_date", lambda start_date, explicit_end_date=None: date(2026, 4, 16))
    monkeypatch.setattr(
        service,
        "list_trading_dates",
        lambda start_date, end_date, overwrite_existing=False: [date(2026, 4, 15)],
    )
    monkeypatch.setattr("backtesting.backfill_scores_history.ProcessPoolExecutor", _FakeExecutor)
    monkeypatch.setattr(service, "build_snapshot_for_date", lambda as_of_date, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")))

    try:
        service.backfill(date(2026, 4, 15), limit_days=None)
    except RuntimeError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("Une interruption était attendue")

    assert shutdown_calls == [True]


