from __future__ import annotations

from datetime import date, datetime, timezone
import logging
from typing import cast

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from selector.alpha_scanner import AlphaScanner, AlphaScannerConfig


def _create_shared_sqlite_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _make_market_frame(
    symbol: str,
    sector: str,
    drift: float,
    base_price: float = 50.0,
    rows: int = 260,
    volume: float = 600_000.0,
    noise_scale: float = 0.002,
) -> tuple[pd.DataFrame, dict[str, object]]:
    dates = pd.bdate_range(end=datetime.now(timezone.utc), periods=rows)
    trend = np.linspace(0.0, drift, rows)
    noise = np.sin(np.linspace(0.0, 12.0, rows)) * noise_scale
    close = base_price * (1.0 + trend + noise)
    high = close * 1.01
    low = close * 0.99
    market = pd.DataFrame(
        {
            "symbol": symbol,
            "date": dates.tz_localize(None),
            "close": close,
            "volume": np.full(rows, volume),
            "high": high,
            "low": low,
        }
    )
    score_row = {
        "symbol": symbol,
        "liquidity_val": float(np.mean(close[-20:] * volume)),
        "relative_strength_index": max(1.0, 50.0 + drift * 100.0),
        "total_score": max(1.0, 60.0 + drift * 100.0),
        "sector": sector,
        "anomaly_count": 0,
        "missing_days_count": 0,
        "is_candidate": 0,
        "last_updated_scan": datetime.now(timezone.utc).replace(tzinfo=None),
    }
    return market, score_row


def test_compute_factors_prefers_trending_and_tighter_symbols() -> None:
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=AlphaScannerConfig(selection_size=10, max_workers=1))
    bull_frame, _ = _make_market_frame("AAA", "Technology", drift=0.45, noise_scale=0.001)
    weak_frame, _ = _make_market_frame("BBB", "Finance", drift=-0.10, noise_scale=0.05)

    factors = scanner.compute_factors(cast(pd.DataFrame, pd.concat([bull_frame, weak_frame], ignore_index=True)))
    by_symbol = factors.set_index("symbol")

    assert set(factors["symbol"]) == {"AAA", "BBB"}
    assert 0.0 <= by_symbol.loc["AAA", "trend_score"] <= 1.0
    assert 0.0 <= by_symbol.loc["AAA", "vcp_score"] <= 1.0
    assert 0.0 <= by_symbol.loc["AAA", "weekly_trend_score"] <= 1.0
    assert by_symbol.loc["AAA", "atr_pct_20"] > 0.0
    assert by_symbol.loc["AAA", "trend_score"] > by_symbol.loc["BBB", "trend_score"]
    assert by_symbol.loc["AAA", "weekly_trend_score"] >= by_symbol.loc["BBB", "weekly_trend_score"]
    assert by_symbol.loc["AAA", "latest_close"] > by_symbol.loc["BBB", "latest_close"]


def test_compute_factors_exposes_weekly_and_atr_features() -> None:
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=AlphaScannerConfig(selection_size=10, max_workers=1))
    strong_frame, _ = _make_market_frame("AAA", "Technology", drift=0.35, noise_scale=0.01)

    factors = scanner.compute_factors(strong_frame)

    row = factors.to_dict(orient="records")[0]
    assert row["atr_20"] > 0.0
    assert 0.0 < row["atr_pct_20"] < 1.0
    assert row["high_52w_proximity"] > 0.0
    assert pd.notna(row["weekly_close"])
    assert pd.notna(row["weekly_ma10"])
    assert pd.notna(row["weekly_ma30"])
    assert 0.0 <= row["weekly_trend_score"] <= 1.0


def test_merge_scores_falls_back_to_computed_scores_when_auxiliary_scores_are_missing() -> None:
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=AlphaScannerConfig(selection_size=10, max_workers=1))
    computed = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "date": pd.Timestamp("2026-01-02"),
                "latest_close": 100.0,
                "avg_dollar_volume_20d": 40_000_000.0,
                "history_days": 260,
                "ma50": 95.0,
                "ma150": 90.0,
                "ma200": 85.0,
                "high_52w": 105.0,
                "low_52w": 60.0,
                "volatility_ratio": 0.40,
                "trend_score": 0.80,
                "vcp_score": 0.60,
            }
        ]
    )

    merged = scanner.merge_scores(computed, pd.DataFrame())

    assert merged.loc[0, "raw_final_score"] == pytest.approx(0.70)
    assert merged.loc[0, "final_score"] == pytest.approx(0.70)
    assert merged.loc[0, "sector"] == "Unknown"


def test_apply_filters_keeps_rows_without_auxiliary_scores_but_removes_bad_quality_rows() -> None:
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=AlphaScannerConfig(selection_size=10, max_workers=1))
    merged = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "history_days": 260,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 30_000_000.0,
                "liquidity_val": 25_000_000.0,
                "anomaly_count": 20,
                "missing_days_count": 1,
            },
            {
                "symbol": "BBB",
                "history_days": 260,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 30_000_000.0,
                "liquidity_val": 25_000_000.0,
                "anomaly_count": 21,
                "missing_days_count": 1,
            },
            {
                "symbol": "CCC",
                "history_days": 260,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 30_000_000.0,
                "liquidity_val": np.nan,
                "anomaly_count": np.nan,
                "missing_days_count": np.nan,
            },
        ]
    )

    filtered = scanner.apply_filters(merged)

    assert set(filtered["symbol"]) == {"AAA", "CCC"}


def test_enrich_and_filter_equities_excludes_etfs_and_backfills_sector() -> None:
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=AlphaScannerConfig(selection_size=10, max_workers=1))
    merged = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Unknown", "final_score": 0.8},
            {"symbol": "ETF1", "sector": "Unknown", "final_score": 0.9},
        ]
    )
    metadata = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "company_name": "Acme Corp",
                "asset_class": "us_equity",
                "status": "active",
                "tradable": True,
                "bars_available": True,
                "sector": "Technology",
            },
            {
                "symbol": "ETF1",
                "company_name": "Vanguard Total Bond Market ETF",
                "asset_class": "us_equity",
                "status": "active",
                "tradable": True,
                "bars_available": True,
                "sector": None,
            },
        ]
    )

    enriched = scanner._enrich_and_filter_equities(merged, metadata)

    assert list(enriched["symbol"]) == ["AAA"]
    assert enriched.loc[0, "sector"] == "Technology"


def test_enrich_and_filter_equities_logs_exclusion_breakdown(caplog) -> None:
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=AlphaScannerConfig(selection_size=10, max_workers=1))
    merged = pd.DataFrame(
        [
            {"symbol": "AAA", "sector": "Unknown", "final_score": 0.8},
            {"symbol": "ETF1", "sector": "Unknown", "final_score": 0.9},
            {"symbol": "MISS", "sector": "Unknown", "final_score": 0.7},
            {"symbol": "INAC", "sector": "Unknown", "final_score": 0.6},
        ]
    )
    metadata = pd.DataFrame(
        [
            {
                "symbol": "AAA",
                "company_name": "Acme Corp",
                "asset_class": "us_equity",
                "status": "active",
                "tradable": True,
                "bars_available": True,
                "sector": "Technology",
            },
            {
                "symbol": "ETF1",
                "company_name": "Vanguard Total Bond Market ETF",
                "asset_class": "us_equity",
                "status": "active",
                "tradable": True,
                "bars_available": True,
                "sector": None,
            },
            {
                "symbol": "INAC",
                "company_name": "Inactive Corp",
                "asset_class": "us_equity",
                "status": "inactive",
                "tradable": True,
                "bars_available": True,
                "sector": "Industrials",
            },
        ]
    )

    with caplog.at_level(logging.INFO):
        enriched = scanner._enrich_and_filter_equities(merged, metadata)

    assert list(enriched["symbol"]) == ["AAA"]
    assert "detail={'metadata_missing': 1, 'inactive': 1, 'etf_name': 1}" in caplog.text


def test_apply_sector_neutrality_caps_each_sector() -> None:
    config = AlphaScannerConfig(selection_size=50, sector_cap_ratio=0.30, max_workers=1)
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=config)
    rows: list[dict[str, object]] = []
    sectors = ["Technology", "Finance", "Healthcare", "Energy"]
    score = 1.0
    for sector in sectors:
        for index in range(20):
            rows.append(
                {
                    "symbol": f"{sector[:2]}{index:02d}",
                    "sector": sector,
                    "final_score": score,
                    "trend_score": 0.9,
                    "vcp_score": 0.8,
                    "avg_dollar_volume_20d": 40_000_000.0,
                }
            )
            score -= 0.01

    selected = scanner.apply_sector_neutrality(pd.DataFrame(rows))

    assert len(selected) == 50
    assert selected["sector"].value_counts().max() <= 15


def test_apply_sector_neutrality_does_not_cap_unknown_sector() -> None:
    config = AlphaScannerConfig(selection_size=20, sector_cap_ratio=0.30, max_workers=1)
    scanner = AlphaScanner(engine=_create_shared_sqlite_engine(), config=config)
    rows: list[dict[str, object]] = []
    score = 1.0
    for index in range(18):
        rows.append(
            {
                "symbol": f"UK{index:02d}",
                "sector": "Unknown",
                "final_score": score,
                "trend_score": 0.8,
                "vcp_score": 0.7,
                "avg_dollar_volume_20d": 30_000_000.0,
            }
        )
        score -= 0.01
    for index in range(6):
        rows.append(
            {
                "symbol": f"TC{index:02d}",
                "sector": "Technology",
                "final_score": score,
                "trend_score": 0.8,
                "vcp_score": 0.7,
                "avg_dollar_volume_20d": 30_000_000.0,
            }
        )
        score -= 0.01

    selected = scanner.apply_sector_neutrality(pd.DataFrame(rows))

    assert len(selected) == 20
    assert (selected["sector"] == "Unknown").sum() > 6


def test_update_database_resets_then_marks_selected_symbols() -> None:
    engine = _create_shared_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_scores (
                    symbol TEXT PRIMARY KEY,
                    market_cap REAL,
                    beta_126 REAL,
                    spread_bps REAL,
                    earnings_date DATE,
                    days_to_earnings INTEGER,
                    earnings_blackout INTEGER DEFAULT 0,
                    is_candidate INTEGER NOT NULL DEFAULT 0,
                    last_updated_scan DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO stock_scores(symbol, is_candidate, last_updated_scan) VALUES "
                "('AAA', 0, NULL), ('BBB', 1, NULL), ('CCC', 0, NULL)"
            )
        )

    scanner = AlphaScanner(engine=engine, config=AlphaScannerConfig(selection_size=10, update_batch_size=1, max_workers=1))
    selected = pd.DataFrame({"symbol": ["AAA", "CCC"]})

    updated_count = scanner.update_database(selected)

    with engine.connect() as conn:
        rows = conn.execute(text("SELECT symbol, is_candidate FROM stock_scores ORDER BY symbol")).fetchall()

    assert updated_count == 2
    assert rows == [("AAA", 1), ("BBB", 0), ("CCC", 1)]


def test_update_database_persists_selector_scores() -> None:
    engine = _create_shared_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_scores (
                    symbol TEXT PRIMARY KEY,
                    trend_score REAL,
                    vcp_score REAL,
                    final_score REAL,
                    market_cap REAL,
                    beta_126 REAL,
                    spread_bps REAL,
                    earnings_date DATE,
                    days_to_earnings INTEGER,
                    earnings_blackout INTEGER DEFAULT 0,
                    is_candidate INTEGER NOT NULL DEFAULT 0,
                    last_updated_scan DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                "INSERT INTO stock_scores(symbol, trend_score, vcp_score, final_score, is_candidate, last_updated_scan) VALUES "
                "('AAA', NULL, NULL, NULL, 0, NULL), ('BBB', NULL, NULL, NULL, 0, NULL)"
            )
        )

    scanner = AlphaScanner(engine=engine, config=AlphaScannerConfig(selection_size=10, update_batch_size=2, max_workers=1))
    selected = pd.DataFrame({"symbol": ["AAA"]})
    scored = pd.DataFrame(
        [
            {
                "symbol": "AAA", "trend_score": 0.80, "vcp_score": 0.60, "final_score": 1.10,
                "market_cap": 5_000_000_000.0, "beta_126": 1.15, "spread_bps": 12.0,
                "earnings_date": date(2026, 4, 30), "days_to_earnings": 8, "earnings_blackout": 0,
            },
            {
                "symbol": "BBB", "trend_score": 0.55, "vcp_score": 0.40, "final_score": 0.82,
                "market_cap": 3_000_000_000.0, "beta_126": 0.95, "spread_bps": 30.0,
                "earnings_date": date(2026, 4, 24), "days_to_earnings": 2, "earnings_blackout": 1,
            },
        ]
    )

    updated_count = scanner.update_database(selected, scored)

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT symbol, trend_score, vcp_score, final_score, market_cap, beta_126, spread_bps, days_to_earnings, earnings_blackout, is_candidate "
                "FROM stock_scores ORDER BY symbol"
            )
        ).fetchall()

    assert updated_count == 1
    assert rows == [
        ("AAA", 0.8, 0.6, 1.1, 5_000_000_000.0, 1.15, 12.0, 8, 0, 1),
        ("BBB", 0.55, 0.4, 0.82, 3_000_000_000.0, 0.95, 30.0, 2, 1, 0),
    ]


def test_run_end_to_end_returns_ranked_top_selection_and_updates_database() -> None:
    engine = _create_shared_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_bars_daily (
                    symbol TEXT NOT NULL,
                    date DATETIME NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    PRIMARY KEY(symbol, date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_scores (
                    symbol TEXT PRIMARY KEY,
                    liquidity_val REAL,
                    relative_strength_index REAL,
                    total_score REAL,
                    trend_score REAL,
                    vcp_score REAL,
                    final_score REAL,
                    sector TEXT,
                    market_cap REAL,
                    beta_126 REAL,
                    spread_bps REAL,
                    earnings_date DATE,
                    days_to_earnings INTEGER,
                    earnings_blackout INTEGER DEFAULT 0,
                    anomaly_count INTEGER,
                    missing_days_count INTEGER,
                    is_candidate INTEGER NOT NULL DEFAULT 0,
                    last_updated_scan DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_metadata (
                    symbol TEXT PRIMARY KEY,
                    company_name TEXT,
                    asset_class TEXT,
                    status TEXT,
                    tradable BOOLEAN,
                    bars_available BOOLEAN,
                    sector TEXT,
                    market_cap REAL
                )
                """
            )
        )

        markets: list[pd.DataFrame] = []
        scores: list[dict[str, object]] = []
        metadata_rows: list[dict[str, object]] = []
        definitions = [
            ("AAA", "Technology", 0.50),
            ("AAB", "Technology", 0.40),
            ("BBB", "Finance", 0.35),
            ("BBC", "Finance", 0.25),
            ("CCC", "Healthcare", 0.32),
            ("CCD", "Healthcare", 0.22),
            ("DDD", "Energy", 0.30),
            ("DDE", "Energy", 0.18),
        ]
        for symbol, sector, drift in definitions:
            market_frame, score_row = _make_market_frame(symbol, sector, drift=drift, rows=260)
            markets.append(market_frame)
            scores.append(score_row)
            metadata_rows.append(
                {
                    "symbol": symbol,
                    "company_name": f"{symbol} Common Stock",
                    "asset_class": "us_equity",
                    "status": "active",
                    "tradable": True,
                    "bars_available": True,
                    "sector": sector,
                    "market_cap": 5_000_000_000.0,
                }
            )

        etf_market, etf_score = _make_market_frame("ETF1", "Unknown", drift=0.60, rows=260)
        markets.append(etf_market)
        scores.append(etf_score)
        metadata_rows.append(
            {
                "symbol": "ETF1",
                "company_name": "Vanguard Total Bond Market ETF",
                "asset_class": "us_equity",
                "status": "active",
                "tradable": True,
                "bars_available": True,
                "sector": None,
                "market_cap": None,
            }
        )

        scores.append(
            {
                "symbol": "ZZZ",
                "liquidity_val": 99_000_000.0,
                "relative_strength_index": 99.0,
                "total_score": 99.0,
                "trend_score": 0.9,
                "vcp_score": 0.9,
                "final_score": 1.4,
                "sector": "Legacy",
                "anomaly_count": 0,
                "missing_days_count": 0,
                "is_candidate": 1,
                "last_updated_scan": datetime.now(timezone.utc).replace(tzinfo=None),
            }
        )

        market_df = pd.concat(markets, ignore_index=True)
        market_df.to_sql("stock_bars_daily", conn, if_exists="append", index=False)
        pd.DataFrame(scores).to_sql("stock_scores", conn, if_exists="append", index=False)
        pd.DataFrame(metadata_rows).to_sql("stock_metadata", conn, if_exists="append", index=False)

    scanner = AlphaScanner(
        engine=engine,
        config=AlphaScannerConfig(selection_size=4, chunk_size=3, update_batch_size=2, max_workers=1),
    )

    result = scanner.run()

    assert len(result) == 4
    assert list(result["rank"]) == [1, 2, 3, 4]
    assert list(result["final_score"]) == sorted(result["final_score"], reverse=True)
    assert "ETF1" not in set(result["symbol"])

    with engine.connect() as conn:
        candidate_rows = conn.execute(
            text("SELECT symbol FROM stock_scores WHERE is_candidate = 1 ORDER BY symbol")
        ).fetchall()
        persisted_rows = conn.execute(
            text(
                "SELECT symbol, trend_score, vcp_score, final_score "
                "FROM stock_scores WHERE symbol IN ('AAA', 'AAB') ORDER BY symbol"
            )
        ).fetchall()
        legacy_row = conn.execute(
            text(
                "SELECT symbol, trend_score, vcp_score, final_score, is_candidate "
                "FROM stock_scores WHERE symbol = 'ZZZ'"
            )
        ).fetchone()

    assert len(candidate_rows) == 4
    assert {row[0] for row in candidate_rows} == set(result["symbol"])
    assert all(row[1] is not None and row[2] is not None and row[3] is not None for row in persisted_rows)
    assert legacy_row == ("ZZZ", None, None, None, 0)


def test_run_supports_strict_swing_preset_filters() -> None:
    engine = _create_shared_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_bars_daily (
                    symbol TEXT NOT NULL,
                    date DATETIME NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    PRIMARY KEY(symbol, date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_scores (
                    symbol TEXT PRIMARY KEY,
                    liquidity_val REAL,
                    relative_strength_index REAL,
                    total_score REAL,
                    trend_score REAL,
                    vcp_score REAL,
                    final_score REAL,
                    sector TEXT,
                    market_cap REAL,
                    beta_126 REAL,
                    spread_bps REAL,
                    earnings_date DATE,
                    days_to_earnings INTEGER,
                    earnings_blackout INTEGER DEFAULT 0,
                    anomaly_count INTEGER,
                    missing_days_count INTEGER,
                    is_candidate INTEGER NOT NULL DEFAULT 0,
                    last_updated_scan DATETIME
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_metadata (
                    symbol TEXT PRIMARY KEY,
                    company_name TEXT,
                    asset_class TEXT,
                    status TEXT,
                    tradable BOOLEAN,
                    bars_available BOOLEAN,
                    sector TEXT,
                    market_cap REAL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_quote_snapshots (
                    symbol TEXT NOT NULL,
                    quote_date DATE NOT NULL,
                    spread_bps REAL,
                    PRIMARY KEY(symbol, quote_date)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE stock_earnings_calendar (
                    symbol TEXT NOT NULL,
                    earnings_date DATE NOT NULL,
                    PRIMARY KEY(symbol, earnings_date)
                )
                """
            )
        )

        markets: list[pd.DataFrame] = []
        scores: list[dict[str, object]] = []
        metadata_rows: list[dict[str, object]] = []
        definitions = [
            ("AAA", "Technology", 0.45, 800_000.0),
            ("BBB", "Finance", 0.30, 800_000.0),
        ]
        for symbol, sector, drift, volume in definitions:
            market_frame, score_row = _make_market_frame(symbol, sector, drift=drift, rows=260, volume=volume, noise_scale=0.02)
            markets.append(market_frame)
            score_row["relative_strength_index"] = 110.0 if symbol == "AAA" else 92.0
            score_row["total_score"] = 95.0 if symbol == "AAA" else 88.0
            scores.append(score_row)
            metadata_rows.append(
                {
                    "symbol": symbol,
                    "company_name": f"{symbol} Common Stock",
                    "asset_class": "us_equity",
                    "status": "active",
                    "tradable": True,
                    "bars_available": True,
                    "sector": sector,
                    "market_cap": 5_000_000_000.0,
                }
            )

        spy_market, _ = _make_market_frame("SPY", "Benchmark", drift=0.20, rows=260, volume=2_000_000.0, noise_scale=0.01)
        markets.append(spy_market)

        pd.concat(markets, ignore_index=True).to_sql("stock_bars_daily", conn, if_exists="append", index=False)
        pd.DataFrame(scores).to_sql("stock_scores", conn, if_exists="append", index=False)
        pd.DataFrame(metadata_rows).to_sql("stock_metadata", conn, if_exists="append", index=False)
        pd.DataFrame(
            [
                {"symbol": "AAA", "quote_date": date(2026, 4, 22), "spread_bps": 12.0},
                {"symbol": "BBB", "quote_date": date(2026, 4, 22), "spread_bps": 40.0},
            ]
        ).to_sql("stock_quote_snapshots", conn, if_exists="append", index=False)
        pd.DataFrame(
            [
                {"symbol": "AAA", "earnings_date": date(2026, 5, 5)},
                {"symbol": "BBB", "earnings_date": date(2026, 4, 23)},
            ]
        ).to_sql("stock_earnings_calendar", conn, if_exists="append", index=False)

    scanner = AlphaScanner(
        engine=engine,
        config=AlphaScannerConfig.strict_swing_cash(selection_size=5, chunk_size=2, max_workers=1, min_beta_126=None),
    )

    result = scanner.run()

    assert list(result["symbol"]) == ["AAA"]




