from __future__ import annotations

from datetime import date

from sqlalchemy import create_engine, select

from database.macro_indicators import (
    get_macro_indicators_daily_table,
    load_macro_indicator_daily_asof,
    load_macro_indicator_history_asof,
    persist_macro_indicator_daily,
    persist_market_macro_snapshot_daily,
)


def test_persist_macro_indicator_daily_inserts_and_updates_row() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)

        inserted = persist_macro_indicator_daily(
            trade_date=date(2025, 4, 15),
            vix=22.4,
            vix9d=14.15,
            ten_y=4.50,
            mode="normal",
            risk_multiplier=1.0,
            effective_max_positions=4,
            allow_new_entries=True,
            vix_curve_inverted=False,
            yield_10y_5d_pct=0.0123,
            sentiment_score=0.1,
            sentiment_level="normal",
            sentiment_source="ticker_daily_sentiment_features",
            engine=engine,
        )
        assert inserted == 1

        with engine.begin() as conn:
            row = conn.execute(
                select(
                    table.c.trade_date,
                    table.c.vix,
                    table.c.vix9d,
                    table.c.ten_y,
                    table.c.mode,
                    table.c.risk_multiplier,
                    table.c.effective_max_positions,
                    table.c.allow_new_entries,
                    table.c.vix_curve_inverted,
                    table.c.yield_10y_5d_pct,
                    table.c.sentiment_score,
                    table.c.sentiment_level,
                    table.c.sentiment_source,
                )
            ).one()
        assert row.trade_date == date(2025, 4, 15)
        assert row.vix == 22.4
        assert row.vix9d == 14.15
        assert row.ten_y == 4.50
        assert row.mode == "normal"
        assert row.risk_multiplier == 1.0
        assert row.effective_max_positions == 4
        assert row.allow_new_entries is True
        assert row.vix_curve_inverted is False
        assert row.yield_10y_5d_pct == 0.0123
        assert row.sentiment_score == 0.1
        assert row.sentiment_level == "normal"
        assert row.sentiment_source == "ticker_daily_sentiment_features"

        updated = persist_macro_indicator_daily(
            trade_date="2025-04-15",
            vix=23.1,
            vix9d=15.0,
            ten_y=4.65,
            mode="capital_preservation",
            risk_multiplier=0.75,
            effective_max_positions=2,
            allow_new_entries=False,
            vix_curve_inverted=True,
            yield_10y_5d_pct=0.045,
            sentiment_score=-0.2,
            sentiment_level="warning",
            sentiment_source="sector_daily_sentiment_features",
            engine=engine,
        )
        assert updated == 1

        with engine.begin() as conn:
            row = conn.execute(
                select(
                    table.c.trade_date,
                    table.c.vix,
                    table.c.vix9d,
                    table.c.ten_y,
                    table.c.mode,
                    table.c.risk_multiplier,
                    table.c.effective_max_positions,
                    table.c.allow_new_entries,
                    table.c.vix_curve_inverted,
                    table.c.yield_10y_5d_pct,
                    table.c.sentiment_score,
                    table.c.sentiment_level,
                    table.c.sentiment_source,
                )
            ).one()
        assert row.trade_date == date(2025, 4, 15)
        assert row.vix == 23.1
        assert row.vix9d == 15.0
        assert row.ten_y == 4.65
        assert row.mode == "capital_preservation"
        assert row.risk_multiplier == 0.75
        assert row.effective_max_positions == 2
        assert row.allow_new_entries is False
        assert row.vix_curve_inverted is True
        assert row.yield_10y_5d_pct == 0.045
        assert row.sentiment_score == -0.2
        assert row.sentiment_level == "warning"
        assert row.sentiment_source == "sector_daily_sentiment_features"
    finally:
        engine.dispose()


def test_persist_macro_indicator_daily_returns_zero_when_table_missing() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        persisted = persist_macro_indicator_daily(
            trade_date=date(2025, 4, 15),
            vix=22.4,
            vix9d=14.15,
            ten_y=4.50,
            engine=engine,
        )

        assert persisted == 0
    finally:
        engine.dispose()


def test_load_macro_indicator_daily_and_history_asof() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)

        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 11),
            vix=20.0,
            vix9d=19.0,
            ten_y=4.30,
            engine=engine,
        )
        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 14),
            vix=21.0,
            vix9d=20.0,
            ten_y=4.40,
            engine=engine,
        )
        persist_macro_indicator_daily(
            trade_date=date(2025, 4, 15),
            vix=22.0,
            vix9d=21.0,
            ten_y=4.50,
            engine=engine,
        )

        row = load_macro_indicator_daily_asof(trade_date=date(2025, 4, 15), engine=engine)
        strict_row = load_macro_indicator_daily_asof(
            trade_date=date(2025, 4, 15),
            engine=engine,
            strict_before=True,
        )
        history = load_macro_indicator_history_asof(
            trade_date=date(2025, 4, 15),
            column="ten_y",
            lookback_days=2,
            engine=engine,
        )
        strict_history = load_macro_indicator_history_asof(
            trade_date=date(2025, 4, 15),
            column="ten_y",
            lookback_days=2,
            engine=engine,
            strict_before=True,
        )

        assert row is not None
        assert row["trade_date"] == date(2025, 4, 15)
        assert row["vix"] == 22.0
        assert strict_row is not None
        assert strict_row["trade_date"] == date(2025, 4, 14)
        assert history == [4.40, 4.50]
        assert strict_history == [4.30, 4.40]
    finally:
        engine.dispose()


def test_persist_market_macro_snapshot_daily_maps_snapshot_payload() -> None:
    engine = create_engine("sqlite:///:memory:")
    try:
        table = get_macro_indicators_daily_table()
        table.metadata.create_all(engine)

        persisted = persist_market_macro_snapshot_daily(
            trade_date=date(2025, 4, 15),
            macro_payload={
                "mode": "capital_preservation",
                "risk_multiplier": 0.7,
                "effective_max_positions": 2,
                "allow_new_entries": True,
                "macro": {"vix": 22.4, "vix_short": 14.15, "yield_10y": 4.50, "vix_curve_inverted": True, "yield_10y_5d_pct": 0.03},
                "sentiment": {"score": -0.2, "level": "warning", "source": "ticker_daily_sentiment_features"},
            },
            engine=engine,
        )

        assert persisted == 1
        with engine.begin() as conn:
            row = conn.execute(
                select(
                    table.c.trade_date,
                    table.c.vix,
                    table.c.vix9d,
                    table.c.ten_y,
                    table.c.mode,
                    table.c.risk_multiplier,
                    table.c.effective_max_positions,
                    table.c.allow_new_entries,
                    table.c.vix_curve_inverted,
                    table.c.yield_10y_5d_pct,
                    table.c.sentiment_score,
                    table.c.sentiment_level,
                    table.c.sentiment_source,
                )
            ).one()
        assert row.trade_date == date(2025, 4, 15)
        assert row.vix == 22.4
        assert row.vix9d == 14.15
        assert row.ten_y == 4.50
        assert row.mode == "capital_preservation"
        assert row.risk_multiplier == 0.7
        assert row.effective_max_positions == 2
        assert row.allow_new_entries is True
        assert row.vix_curve_inverted is True
        assert row.yield_10y_5d_pct == 0.03
        assert row.sentiment_score == -0.2
        assert row.sentiment_level == "warning"
        assert row.sentiment_source == "ticker_daily_sentiment_features"
    finally:
        engine.dispose()


