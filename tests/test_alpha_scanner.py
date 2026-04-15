from __future__ import annotations

from datetime import datetime, timezone

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

    factors = scanner.compute_factors(pd.concat([bull_frame, weak_frame], ignore_index=True))
    by_symbol = factors.set_index("symbol")

    assert set(factors["symbol"]) == {"AAA", "BBB"}
    assert 0.0 <= by_symbol.loc["AAA", "trend_score"] <= 1.0
    assert 0.0 <= by_symbol.loc["AAA", "vcp_score"] <= 1.0
    assert by_symbol.loc["AAA", "trend_score"] > by_symbol.loc["BBB", "trend_score"]
    assert by_symbol.loc["AAA", "latest_close"] > by_symbol.loc["BBB", "latest_close"]


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
                "anomaly_count": 2,
                "missing_days_count": 1,
            },
            {
                "symbol": "BBB",
                "history_days": 260,
                "latest_close": 50.0,
                "avg_dollar_volume_20d": 30_000_000.0,
                "liquidity_val": 25_000_000.0,
                "anomaly_count": 6,
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


def test_update_database_resets_then_marks_selected_symbols() -> None:
    engine = _create_shared_sqlite_engine()
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE stock_scores (
                    symbol TEXT PRIMARY KEY,
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
            {"symbol": "AAA", "trend_score": 0.80, "vcp_score": 0.60, "final_score": 1.10},
            {"symbol": "BBB", "trend_score": 0.55, "vcp_score": 0.40, "final_score": 0.82},
        ]
    )

    updated_count = scanner.update_database(selected, scored)

    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT symbol, trend_score, vcp_score, final_score, is_candidate FROM stock_scores ORDER BY symbol")
        ).fetchall()

    assert updated_count == 1
    assert rows == [
        ("AAA", 0.8, 0.6, 1.1, 1),
        ("BBB", 0.55, 0.4, 0.82, 0),
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
                    anomaly_count INTEGER,
                    missing_days_count INTEGER,
                    is_candidate INTEGER NOT NULL DEFAULT 0,
                    last_updated_scan DATETIME
                )
                """
            )
        )

        markets: list[pd.DataFrame] = []
        scores: list[dict[str, object]] = []
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

    scanner = AlphaScanner(
        engine=engine,
        config=AlphaScannerConfig(selection_size=4, chunk_size=3, update_batch_size=2, max_workers=1),
    )

    result = scanner.run()

    assert len(result) == 4
    assert list(result["rank"]) == [1, 2, 3, 4]
    assert list(result["final_score"]) == sorted(result["final_score"], reverse=True)

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




