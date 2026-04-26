"""Tests unitaires pour le module backtesting."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import json
import os

import pandas as pd


# ============================================================
# test data_loader
# ============================================================

class TestDataLoader:
    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        def connect(self):
            return TestDataLoader._FakeConn()

    def test_pivot_ohlcv(self):
        from backtesting.data_loader import pivot_ohlcv

        df = pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "AAPL", "MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"]),
            "open": [100, 200, 101, 201],
            "high": [105, 205, 106, 206],
            "low": [95, 195, 96, 196],
            "close": [102, 202, 103, 203],
            "volume": [1000, 2000, 1100, 2100],
        })
        result = pivot_ohlcv(df)
        assert set(result.keys()) == {"open", "high", "low", "close", "volume"}
        assert list(result["close"].columns) == ["AAPL", "MSFT"]
        assert result["close"].shape == (2, 2)
        assert result["close"].iloc[0]["AAPL"] == 102

    def test_pivot_ohlcv_empty(self):
        from backtesting.data_loader import pivot_ohlcv

        df = pd.DataFrame(columns=["symbol", "trade_date", "open", "high", "low", "close", "volume"])
        result = pivot_ohlcv(df)
        assert result["close"].empty

    def test_load_ohlcv_supports_real_stock_bars_daily_schema(self, monkeypatch):
        from backtesting import data_loader

        captured = {}

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
                    {"name": "adj_close"},
                    {"name": "volume"},
                ]

        def fake_inspect(_engine):
            return FakeInspector()

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            captured["sql"] = str(query)
            captured["params"] = params
            captured["parse_dates"] = parse_dates
            return pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "trade_date": pd.to_datetime(["2025-01-02"]),
                    "open": [100.0],
                    "high": [101.0],
                    "low": [99.0],
                    "close": [100.5],
                    "volume": [1000],
                }
            )

        monkeypatch.setattr(data_loader, "inspect", fake_inspect)
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        df = data_loader.load_ohlcv(self._FakeEngine(), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert "`date` AS trade_date" in captured["sql"]
        assert "COALESCE(adj_close, `close`) AS `close`" in captured["sql"]
        assert captured["parse_dates"] == ["trade_date"]

    def test_load_scores_prefers_history_table(self, monkeypatch):
        from backtesting import data_loader

        captured = {}

        class FakeInspector:
            def has_table(self, table_name):
                return table_name == "stock_scores_history"

        def fake_inspect(_engine):
            return FakeInspector()

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            captured["sql"] = str(query)
            return pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "trade_date": pd.to_datetime(["2025-01-02"]),
                    "final_score": [0.8],
                    "final_score_sentiment": [0.82],
                    "sector": ["Tech"],
                    "is_candidate": [1],
                }
            )

        monkeypatch.setattr(data_loader, "inspect", fake_inspect)
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        df = data_loader.load_scores(self._FakeEngine(), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert "FROM stock_scores_history" in captured["sql"]
        assert "snapshot_date AS trade_date" in captured["sql"]

    def test_load_scores_falls_back_when_history_is_empty(self, monkeypatch):
        from backtesting import data_loader

        calls = []

        class FakeInspector:
            def has_table(self, table_name):
                return table_name == "stock_scores_history"

        def fake_inspect(_engine):
            return FakeInspector()

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            sql = str(query)
            calls.append(sql)
            if "FROM stock_scores_history" in sql:
                return pd.DataFrame(columns=["symbol", "trade_date", "final_score", "final_score_sentiment", "sector", "is_candidate"])
            return pd.DataFrame(
                {
                    "symbol": ["MSFT"],
                    "trade_date": pd.to_datetime(["2025-01-15"]),
                    "final_score": [0.7],
                    "final_score_sentiment": [0.75],
                    "sector": ["Tech"],
                    "is_candidate": [1],
                }
            )

        monkeypatch.setattr(data_loader, "inspect", fake_inspect)
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        df = data_loader.load_scores(self._FakeEngine(), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert len(calls) == 2
        assert "FROM stock_scores_history" in calls[0]
        assert "FROM stock_scores" in calls[1]

    def test_load_predictions_supports_prediction_date(self, monkeypatch):
        from backtesting import data_loader

        captured = {}

        class FakeInspector:
            def get_columns(self, table_name):
                assert table_name == "model_predictions"
                return [
                    {"name": "symbol"},
                    {"name": "prediction_date"},
                    {"name": "predicted_proba"},
                    {"name": "predicted_class"},
                ]

        def fake_inspect(_engine):
            return FakeInspector()

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            captured["sql"] = str(query)
            return pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "trade_date": pd.to_datetime(["2025-01-02"]),
                    "predicted_proba": [0.66],
                    "predicted_class": [1],
                }
            )

        monkeypatch.setattr(data_loader, "inspect", fake_inspect)
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        df = data_loader.load_predictions(self._FakeEngine(), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert "prediction_date AS trade_date" in captured["sql"]

    def test_load_sentiment_supports_1d_columns(self, monkeypatch):
        from backtesting import data_loader

        captured = {}

        class FakeInspector:
            def get_columns(self, table_name):
                assert table_name == "ticker_daily_sentiment_features"
                return [
                    {"name": "symbol"},
                    {"name": "trade_date"},
                    {"name": "sentiment_net_mean_1d"},
                    {"name": "news_count_1d"},
                ]

        def fake_inspect(_engine):
            return FakeInspector()

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            captured["sql"] = str(query)
            return pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "trade_date": pd.to_datetime(["2025-01-02"]),
                    "sentiment_net_mean": [0.12],
                    "news_count": [3],
                }
            )

        monkeypatch.setattr(data_loader, "inspect", fake_inspect)
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        df = data_loader.load_sentiment(self._FakeEngine(), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert "sentiment_net_mean_1d AS sentiment_net_mean" in captured["sql"]
        assert "news_count_1d AS news_count" in captured["sql"]


# ============================================================
# test signal_replay
# ============================================================

class TestSignalReplay:
    def _make_scores(self):
        dates = pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01"])
        return pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "NVDA"],
            "trade_date": dates,
            "final_score_sentiment": [0.9, 0.7, 0.8],
            "sector": ["Tech", "Tech", "Tech"],
        })

    def test_replay_without_predictions(self):
        from backtesting.signal_replay import replay_signals

        scores = self._make_scores()
        result = replay_signals(scores, None, max_positions=2)
        assert len(result) == 3
        assert result["selected"].sum() == 2
        # Top 2 by conviction (score_weight=0.4 only since no prediction)
        selected = result[result["selected"]]["symbol"].tolist()
        assert "AAPL" in selected  # highest score

    def test_replay_with_predictions(self):
        from backtesting.signal_replay import replay_signals

        scores = self._make_scores()
        preds = pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "NVDA"],
            "trade_date": pd.to_datetime(["2025-01-01"] * 3),
            "predicted_proba": [0.5, 0.95, 0.6],
        })
        result = replay_signals(scores, preds, max_positions=1)
        selected = result[result["selected"]]
        # MSFT has highest conviction: 0.7*0.4 + 0.95*0.6 = 0.85
        assert selected.iloc[0]["symbol"] == "MSFT"

    def test_replay_uses_final_score_fallback(self):
        from backtesting.signal_replay import replay_signals

        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.8],
            "sector": ["Tech"],
        })
        result = replay_signals(scores, None, max_positions=5)
        assert len(result) == 1
        assert result.iloc[0]["score"] == 0.8

    def test_replay_falls_back_per_row_when_final_score_sentiment_missing(self):
        from backtesting.signal_replay import replay_signals

        scores = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            "final_score_sentiment": [None, 0.9],
            "final_score": [0.7, 0.8],
            "sector": ["Tech", "Tech"],
        })
        result = replay_signals(scores, None, max_positions=2)
        assert result.loc[result["symbol"] == "AAPL", "score"].iloc[0] == 0.7
        assert result.loc[result["symbol"] == "MSFT", "score"].iloc[0] == 0.9

    def test_replay_supports_explicit_walk_forward_score_column(self):
        from backtesting.signal_replay import replay_signals

        scores = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            "final_score_walk_forward": [0.66, 0.91],
            "final_score_sentiment": [0.80, 0.20],
            "final_score": [0.70, 0.70],
            "sector": ["Tech", "Tech"],
        })

        result = replay_signals(scores, None, score_column="final_score_walk_forward", max_positions=1)

        selected = result[result["selected"]]
        assert selected.iloc[0]["symbol"] == "MSFT"
        assert selected.iloc[0]["score"] == 0.91

    def test_replay_uses_walk_forward_by_default_and_exposes_score_source(self):
        from backtesting.signal_replay import replay_signals

        scores = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            "final_score_walk_forward": [0.72, 0.88],
            "final_score_sentiment": [0.95, 0.10],
            "final_score": [0.60, 0.60],
            "sector": ["Tech", "Tech"],
        })

        result = replay_signals(scores, None, max_positions=1)

        selected = result[result["selected"]].iloc[0]
        assert selected["symbol"] == "MSFT"
        assert selected["score"] == 0.88
        assert selected["score_source"] == "final_score_walk_forward"


# ============================================================
# test resilience policies
# ============================================================

class TestResilience:
    def test_prepare_scores_sentiment_off_uses_final_score(self):
        from backtesting.resilience import prepare_scores_for_sentiment_mode

        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.9],
        })
        result = prepare_scores_for_sentiment_mode(None, scores, sentiment_mode="off")  # type: ignore[arg-type]
        assert result.iloc[0]["final_score_sentiment"] == 0.7

    def test_prepare_scores_sentiment_auto_fills_missing(self):
        from backtesting.resilience import prepare_scores_for_sentiment_mode

        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [None],
        })
        result = prepare_scores_for_sentiment_mode(None, scores, sentiment_mode="auto")  # type: ignore[arg-type]
        assert result.iloc[0]["final_score_sentiment"] == 0.7

    def test_prepare_scores_applies_latest_walk_forward_weights_when_available(self, tmp_path):
        from backtesting.resilience import prepare_scores_for_sentiment_mode

        weights_dir = tmp_path / "sentiment_walk_forward" / "run_001"
        weights_dir.mkdir(parents=True)
        (weights_dir / "latest_best_weights.json").write_text(
            json.dumps({
                "sentiment_weight": 0.2,
                "macro_weight": 0.1,
                "quant_weight": 0.7,
                "calibration_run_id": "wf-123",
                "calibration_source": "walk_forward",
            }),
            encoding="utf-8",
        )
        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.9],
            "sentiment_net_agg": [1.0],
            "sector_impact_agg": [0.0],
        })

        result = prepare_scores_for_sentiment_mode(
            None,  # type: ignore[arg-type]
            scores,
            sentiment_mode="auto",
            walk_forward_artifacts_dir=tmp_path,
        )

        assert result.iloc[0]["final_score_walk_forward"] == 0.74
        assert result.iloc[0]["score_source"] == "final_score_walk_forward"
        assert result.iloc[0]["calibration_run_id"] == "wf-123"

    def test_prepare_predictions_ml_off_returns_empty(self):
        from backtesting.resilience import prepare_predictions_for_ml_mode

        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
        })
        preds = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "predicted_proba": [0.6],
            "predicted_class": [1],
        })
        result = prepare_predictions_for_ml_mode(None, scores, preds, ml_mode="off", artifacts_dir=Path("artifacts/models"))  # type: ignore[arg-type]
        assert result.empty

    def test_prepare_predictions_ml_auto_keeps_existing(self):
        from backtesting.resilience import prepare_predictions_for_ml_mode

        scores = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
        })
        preds = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "predicted_proba": [0.6],
            "predicted_class": [1],
        })
        result = prepare_predictions_for_ml_mode(None, scores, preds, ml_mode="auto", artifacts_dir=Path("artifacts/models"))  # type: ignore[arg-type]
        assert len(result) == 1
        assert result.iloc[0]["symbol"] == "AAPL"

    def test_prepare_predictions_ml_rebuild_missing_calls_predictor(self, monkeypatch):
        from backtesting import resilience

        scores = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
        })
        preds = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "predicted_proba": [0.6],
            "predicted_class": [1],
        })
        calls = []

        def fake_predict_symbol(symbol, artifacts_dir, engine, prediction_date=None, as_of_date=None, persist=True):
            calls.append((symbol, prediction_date, as_of_date, persist))
            return pd.DataFrame({
                "symbol": [symbol],
                "prediction_date": [prediction_date],
                "predicted_proba": [0.55],
                "predicted_class": [1],
                "run_id": ["run-x"],
            })

        monkeypatch.setattr(resilience, "predict_symbol", fake_predict_symbol)
        result = resilience.prepare_predictions_for_ml_mode(
            None, scores, preds, ml_mode="rebuild-missing", artifacts_dir=Path("artifacts/models")
        )  # type: ignore[arg-type]
        assert len(result) == 2
        assert calls == [(
            "MSFT",
            date(2025, 1, 1),
            date(2025, 1, 1),
            True,
        )]


# ============================================================
# test simulator (BacktestConfig)
# ============================================================

class TestBacktestConfig:
    def test_default_config(self):
        from backtesting.simulator import BacktestConfig

        cfg = BacktestConfig(start_date=date(2020, 1, 1), end_date=date(2025, 1, 1))
        assert cfg.profit_taker_pct == 0.08
        assert cfg.trailing_stop_pct == 0.05
        assert cfg.max_positions == 20
        assert cfg.initial_equity == 100_000
        assert cfg.trading_constraints.account_type == "margin"
        assert cfg.trading_constraints.pdt_rule == "auto"
        assert cfg.trading_constraints.swing_only is False
    def test_config_from_risk_and_exec(self):
        from backtesting.simulator import BacktestConfig
        from risk_management.config import RiskConfig
        from execution_engine.config import ExecutionConfig

        rc = RiskConfig(max_positions=10)
        ec = ExecutionConfig(profit_taker_pct=0.10, trailing_stop_pct=0.04)
        cfg = BacktestConfig(
            start_date=date(2020, 1, 1), end_date=date(2025, 1, 1),
            risk_config=rc, exec_config=ec,
        )
        assert cfg.max_positions == 10
        assert cfg.profit_taker_pct == 0.10
        assert cfg.trailing_stop_pct == 0.04

    def test_backtest_engine_smoke(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0, 104.0, 103.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 103.0, 106.0, 104.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [101.0, 104.0, 108.0, 105.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 102.0, 103.0, 101.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
            }
        )

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 6),
                initial_equity=10_000,
                max_positions=1,
            )
        )
        pf = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        final_value = pf.final_value()
        if hasattr(final_value, "iloc"):
            final_value = final_value.iloc[0]
        assert float(final_value) > 0.0

    def test_backtest_engine_uses_integer_share_sizes(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0, 104.0, 103.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 103.0, 106.0, 104.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [101.0, 104.0, 108.0, 105.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 102.0, 103.0, 101.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
            }
        )

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 6),
                initial_equity=10_000,
                max_positions=1,
            )
        )
        pf = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        trades_df = pf.trades.records_readable
        assert not trades_df.empty
        assert float(trades_df["Size"].iloc[0]).is_integer()

    def test_to_scalar_supports_series_and_scalar(self):
        from backtesting.simulator import BacktestEngine, BacktestConfig

        engine = BacktestEngine(BacktestConfig(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2)))

        assert engine._to_scalar(pd.Series([123.4])) == 123.4
        assert engine._to_scalar(99.0) == 99.0

    def test_backtest_engine_raises_when_no_common_symbols(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 101.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [101.0, 102.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 100.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["MSFT"],
                "selected": [True],
            }
        )

        engine = BacktestEngine(BacktestConfig(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2)))

        try:
            engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        except ValueError as exc:
            assert "Aucun symbole en commun" in str(exc)
        else:
            raise AssertionError("Le moteur aurait dû refuser un backtest sans symbole commun.")

    def test_backtest_engine_swing_mode_blocks_same_day_exit(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine
        from backtesting.trading_constraints import TradingConstraintConfig

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
        open_ = pd.DataFrame({"AAPL": [100.0, 105.0, 120.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 118.0, 121.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [110.0, 120.0, 122.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 104.0, 119.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
            }
        )

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 2),
                initial_equity=10_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="margin", pdt_rule="off", swing_only=True),
            )
        )

        result = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        trades_df = result.closed_trades_df
        assert len(trades_df) == 1
        assert trades_df.iloc[0]["entry_date"] == pd.Timestamp("2025-01-02")
        assert trades_df.iloc[0]["entry_price"] == 105.0
        assert trades_df.iloc[0]["holding_days"] == 1
        assert bool(trades_df.iloc[0]["is_day_trade"]) is False
        assert result.diagnostics.blocked_same_day_exits == 1
        assert result.diagnostics.executed_day_trades == 0

    def test_backtest_engine_standard_mode_uses_next_open_execution(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine, BacktestResult
        from backtesting.trading_constraints import TradingConstraintConfig

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [110.0, 111.0, 112.0, 113.0, 114.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 100.0, 101.0, 102.0, 103.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": idx,
                "symbol": ["AAPL"] * len(idx),
                "selected": [True] * len(idx),
                "rank": [1.0] * len(idx),
            }
        )

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 7),
                initial_equity=2_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="margin", pdt_rule="off", swing_only=False),
            )
        )

        result = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        assert isinstance(result, BacktestResult)
        assert hasattr(result, "final_value")
        assert hasattr(result, "trades")
        assert not result.closed_trades_df.empty
        assert result.closed_trades_df.iloc[0]["signal_date"] == pd.Timestamp("2025-01-01")
        assert result.closed_trades_df.iloc[0]["entry_date"] == pd.Timestamp("2025-01-02")
        assert result.closed_trades_df.iloc[0]["entry_price"] == 101.0
        assert result.diagnostics.blocked_same_day_exits == 0

    def test_backtest_engine_pdt_mode_is_not_active_above_25k(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine, BacktestResult
        from backtesting.trading_constraints import TradingConstraintConfig

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [110.0, 111.0, 112.0, 113.0, 114.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 100.0, 101.0, 102.0, 103.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": idx,
                "symbol": ["AAPL"] * len(idx),
                "selected": [True] * len(idx),
                "rank": [1.0] * len(idx),
            }
        )

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 7),
                initial_equity=30_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="margin", pdt_rule="auto", swing_only=False),
            )
        )

        result = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        assert isinstance(result, BacktestResult)
        assert hasattr(result, "trades")
        assert hasattr(result, "final_value")
        assert result.diagnostics.blocked_pdt_day_trades == 0
        assert result.diagnostics.executed_day_trades > 0

    def test_backtest_engine_pdt_mode_blocks_fourth_day_trade_in_rolling_window(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine
        from backtesting.trading_constraints import TradingConstraintConfig

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07", "2025-01-08"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0, 103.0, 104.0, 105.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [110.0, 111.0, 112.0, 113.0, 114.0, 115.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 100.0, 101.0, 102.0, 103.0, 104.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": idx[:4],
                "symbol": ["AAPL"] * 4,
                "selected": [True] * 4,
                "rank": [1.0] * 4,
            }
        )

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 7),
                initial_equity=2_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="margin", pdt_rule="auto", swing_only=False),
            )
        )

        result = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        trades_df = result.closed_trades_df
        assert len(trades_df) == 4
        assert int(trades_df["is_day_trade"].sum()) == 3
        assert trades_df.iloc[-1]["holding_days"] == 1
        assert result.diagnostics.executed_day_trades == 3
        assert result.diagnostics.blocked_pdt_day_trades == 1

    def test_backtest_engine_cash_mode_uses_settled_cash_only(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine
        from backtesting.trading_constraints import TradingConstraintConfig

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        open_ = pd.DataFrame(
            {
                "AAPL": [100.0, 104.0, 104.0, 104.0],
                "MSFT": [100.0, 100.0, 100.0, 104.0],
            },
            index=idx,
        )
        close = pd.DataFrame(
            {
                "AAPL": [100.0, 104.0, 104.0, 104.0],
                "MSFT": [100.0, 100.0, 100.0, 104.0],
            },
            index=idx,
        )
        high = pd.DataFrame(
            {
                "AAPL": [100.0, 112.0, 104.0, 104.0],
                "MSFT": [100.0, 100.0, 100.0, 113.0],
            },
            index=idx,
        )
        low = pd.DataFrame(
            {
                "AAPL": [99.0, 103.0, 103.0, 103.0],
                "MSFT": [99.0, 99.0, 99.0, 103.0],
            },
            index=idx,
        )
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"]),
                "symbol": ["AAPL", "MSFT", "MSFT"],
                "selected": [True, True, True],
                "rank": [1.0, 1.0, 1.0],
            }
        )

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 6),
                initial_equity=10_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="cash", pdt_rule="auto", swing_only=False),
            )
        )

        result = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)
        trades_df = result.closed_trades_df
        assert len(trades_df) == 2
        assert trades_df.iloc[0]["symbol"] == "AAPL"
        assert trades_df.iloc[1]["symbol"] == "MSFT"
        assert trades_df.iloc[0]["entry_date"] == pd.Timestamp("2025-01-02")
        assert trades_df.iloc[1]["entry_date"] == pd.Timestamp("2025-01-06")

    def test_backtest_engine_standard_and_swing_share_same_entry_price(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine
        from backtesting.trading_constraints import TradingConstraintConfig

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
        open_ = pd.DataFrame({"AAPL": [100.0, 105.0, 120.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 118.0, 121.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [110.0, 120.0, 122.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 104.0, 119.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
            }
        )

        standard = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 3),
                initial_equity=10_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="margin", pdt_rule="off", swing_only=False),
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        swing = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 3),
                initial_equity=10_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="margin", pdt_rule="off", swing_only=True),
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        assert standard.closed_trades_df.iloc[0]["entry_price"] == 105.0
        assert swing.closed_trades_df.iloc[0]["entry_price"] == 105.0
        assert standard.closed_trades_df.iloc[0]["entry_date"] == pd.Timestamp("2025-01-02")
        assert swing.closed_trades_df.iloc[0]["entry_date"] == pd.Timestamp("2025-01-02")
        assert standard.closed_trades_df.iloc[0]["exit_date"] == pd.Timestamp("2025-01-02")
        assert swing.closed_trades_df.iloc[0]["exit_date"] == pd.Timestamp("2025-01-03")

    def test_backtest_engine_ignores_signal_without_next_session_open(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 101.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [101.0, 102.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 100.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-02"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
            }
        )

        result = BacktestEngine(
            BacktestConfig(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2), initial_equity=10_000, max_positions=1)
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        assert result.closed_trades_df.empty
        assert result.final_value() == 10_000

    def test_backtest_engine_conservative_trailing_stop_does_not_rachet_on_same_bar(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
        open_ = pd.DataFrame({"AAPL": [10.0, 10.0, 10.1]}, index=idx)
        close = pd.DataFrame({"AAPL": [10.0, 10.2, 9.9]}, index=idx)
        high = pd.DataFrame({"AAPL": [10.0, 10.6, 10.1]}, index=idx)
        low = pd.DataFrame({"AAPL": [10.0, 10.0, 9.4]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
            }
        )

        result = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 3),
                initial_equity=10_000,
                max_positions=1,
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        assert len(result.closed_trades_df) == 1
        trade = result.closed_trades_df.iloc[0]
        assert trade["entry_date"] == pd.Timestamp("2025-01-02")
        assert trade["exit_date"] == pd.Timestamp("2025-01-03")
        assert trade["exit_reason"] == "trailing_stop"
        assert abs(float(trade["exit_price"]) - 10.07) < 1e-9

    def test_trading_constraint_config_effective_pdt_rule_is_disabled_for_cash(self):
        from backtesting.trading_constraints import TradingConstraintConfig

        cfg = TradingConstraintConfig(account_type="cash", pdt_rule="auto", swing_only=False)

        assert cfg.effective_pdt_rule == "off"
        assert cfg.applies_pdt_limit(2_000) is False

    def test_trading_constraint_config_supports_cash_plus_swing_combination(self):
        from backtesting.trading_constraints import TradingConstraintConfig

        cfg = TradingConstraintConfig(account_type="cash", pdt_rule="auto", swing_only=True)

        assert cfg.use_settled_cash_only is True
        assert cfg.restrict_same_day_exit is True
        assert cfg.effective_pdt_rule == "off"
        assert cfg.requires_stateful_simulation(2_000) is True


# ============================================================
# test report
# ============================================================

class TestReport:
    def test_backtest_report_to_dict(self):
        from backtesting.report import BacktestReport

        r = BacktestReport(
            initial_equity=100_000, final_value=120_000,
            total_return_pct=20.0, cagr_pct=9.5,
            sharpe_ratio=1.2, sortino_ratio=1.5,
            max_drawdown_pct=12.0, total_trades=50,
            win_rate_pct=55.0, avg_trade_duration_days=7.5,
            profit_factor=1.8,
        )
        d = r.to_dict()
        assert "Capital initial" in d
        assert d["Nombre de trades"] == 50
        assert "1.200" in d["Sharpe Ratio"]

    def test_print_summary_no_error(self, capsys):
        from backtesting.report import BacktestReport

        r = BacktestReport(
            initial_equity=100_000, final_value=110_000,
            total_return_pct=10.0, cagr_pct=5.0,
            sharpe_ratio=0.8, sortino_ratio=1.0,
            max_drawdown_pct=8.0, total_trades=30,
            win_rate_pct=60.0, avg_trade_duration_days=5.0,
            profit_factor=1.5,
        )
        r.print_summary()
        out = capsys.readouterr().out
        assert "RAPPORT DE BACKTEST" in out
        assert "Sharpe Ratio" in out

    def test_generate_report_with_vectorbt_portfolio(self):
        import vectorbt as vbt
        from backtesting.report import generate_report

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        close = pd.DataFrame({"AAPL": [100.0, 103.0, 104.0, 106.0]}, index=idx)
        entries = pd.DataFrame({"AAPL": [True, False, False, False]}, index=idx)
        exits = pd.DataFrame({"AAPL": [False, False, False, True]}, index=idx)

        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            size=1.0,
            size_type="percent",
            init_cash=10_000,
            cash_sharing=True,
            group_by=True,
            freq="1D",
        )
        report = generate_report(pf, 10_000)
        assert report.final_value > 0.0
        assert isinstance(report.total_trades, int)

    def test_generate_report_ignores_open_trades_and_reports_duration_in_days(self):
        import vectorbt as vbt
        from backtesting.report import generate_report

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        close = pd.DataFrame({"AAPL": [100.0, 103.0, 104.0, 106.0]}, index=idx)
        entries = pd.DataFrame({"AAPL": [True, False, False, False]}, index=idx)
        exits = pd.DataFrame({"AAPL": [False, False, False, True]}, index=idx)

        pf_closed = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            size=1.0,
            size_type="percent",
            init_cash=10_000,
            cash_sharing=True,
            group_by=True,
            freq="1D",
        )
        report_closed = generate_report(pf_closed, 10_000)
        assert report_closed.total_trades == 1
        assert report_closed.avg_trade_duration_days == 3.0

        pf_open = vbt.Portfolio.from_signals(
            close=close.iloc[:2],
            entries=entries.iloc[:2],
            exits=pd.DataFrame({"AAPL": [False, False]}, index=idx[:2]),
            size=1.0,
            size_type="percent",
            init_cash=10_000,
            cash_sharing=True,
            group_by=True,
            freq="1D",
        )
        report_open = generate_report(pf_open, 10_000)
        assert report_open.total_trades == 0
        assert report_open.win_rate_pct == 0.0
        assert report_open.avg_trade_duration_days == 0.0

    def test_save_report_json_and_equity_curve_csv(self, tmp_path):
        import vectorbt as vbt
        from backtesting.report import generate_report, save_equity_curve_csv, save_report_json

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        close = pd.DataFrame({"AAPL": [100.0, 103.0, 104.0, 106.0]}, index=idx)
        entries = pd.DataFrame({"AAPL": [True, False, False, False]}, index=idx)
        exits = pd.DataFrame({"AAPL": [False, False, False, True]}, index=idx)

        pf = vbt.Portfolio.from_signals(
            close=close,
            entries=entries,
            exits=exits,
            size=1.0,
            size_type="percent",
            init_cash=10_000,
            cash_sharing=True,
            group_by=True,
            freq="1D",
        )
        report = generate_report(pf, 10_000)

        equity_csv_path = save_equity_curve_csv(pf, output_dir=tmp_path)
        report_json_path = save_report_json(
            report,
            output_dir=tmp_path,
            artifacts={"equity_curve_csv": str(equity_csv_path)},
            params={"start": "2025-01-01", "end": "2025-01-06"},
            diagnostics={"blocked_pdt_day_trades": 1},
        )

        assert equity_csv_path.exists()
        assert report_json_path.exists()
        equity_df = pd.read_csv(equity_csv_path)
        assert list(equity_df.columns) == ["trade_date", "portfolio_value"]
        payload = __import__("json").loads(report_json_path.read_text(encoding="utf-8"))
        assert payload["summary"]["initial_equity"] == 10000.0
        assert payload["artifacts"]["equity_curve_csv"] == str(equity_csv_path)
        assert payload["params"]["start"] == "2025-01-01"
        assert payload["diagnostics"]["blocked_pdt_day_trades"] == 1


# ============================================================
# test CLI parsing
# ============================================================

class TestCLI:
    def test_parse_run_command(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--end", "2025-12-31", "--equity", "50000"])
        assert args.command == "run"
        assert args.start == "2020-01-01"
        assert args.end == "2025-12-31"
        assert args.equity == 50000

    def test_parse_run_defaults(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01"])
        assert args.tp == 0.08
        assert args.ts == 0.05
        assert args.max_positions == 20
        assert args.fees == 0.001
        assert args.account_type == "margin"
        assert args.pdt_rule == "auto"
        assert args.swing_only is False
        assert args.sentiment_lookback == 365
        assert args.ml_mode == "auto"
        assert args.sentiment_mode == "auto"
        assert args.no_save is False

    def test_parse_custom_params(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "run", "--start", "2016-01-01", "--tp", "0.10",
            "--ts", "0.04", "--max-positions", "15", "--no-save",
        ])
        assert args.tp == 0.10
        assert args.ts == 0.04
        assert args.max_positions == 15
        assert args.no_save is True

    def test_parse_run_account_constraints(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "run", "--start", "2020-01-01",
            "--account-type", "cash",
            "--pdt-rule", "off",
            "--swing-only",
            "--ml-mode", "rebuild-missing",
            "--sentiment-mode", "off",
            "--artifacts-dir", "artifacts/models",
        ])
        assert args.account_type == "cash"
        assert args.pdt_rule == "off"
        assert args.swing_only is True
        assert args.ml_mode == "rebuild-missing"
        assert args.sentiment_mode == "off"
        assert args.artifacts_dir == "artifacts/models"


    def test_parse_run_output_dir(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "run", "--start", "2020-01-01",
            "--output-dir", "artifacts/ihm_backtesting_runs/run_123/artifacts",
        ])
        assert args.output_dir == "artifacts/ihm_backtesting_runs/run_123/artifacts"

    def test_parse_backfill_scores_history_command(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "backfill-scores-history",
            "--start", "2025-01-01",
            "--limit-days", "5",
            "--chunk-size", "250",
            "--selection-size", "50",
            "--overwrite-existing",
        ])
        assert args.command == "backfill-scores-history"
        assert args.start == "2025-01-01"
        assert args.limit_days == 5
        assert args.chunk_size == 250
        assert args.selection_size == 50
        assert args.overwrite_existing is True

    def test_parse_diagnose_screener_command(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "diagnose-screener",
            "--start", "2025-01-01",
            "--end", "2025-03-31",
            "--mode", "grid",
            "--limit-days", "15",
            "--max-scenarios", "12",
            "--output-dir", "artifacts/screener_diagnostics/run_1",
        ])
        assert args.command == "diagnose-screener"
        assert args.mode == "grid"
        assert args.limit_days == 15
        assert args.max_scenarios == 12
        assert args.output_dir == "artifacts/screener_diagnostics/run_1"

    def test_parse_recommend_screener_command(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "recommend-screener",
            "--input-dir", "artifacts/screener_diagnostics/run_1",
            "--target-horizon", "10",
            "--baseline-name", "baseline",
        ])
        assert args.command == "recommend-screener"
        assert args.input_dir == "artifacts/screener_diagnostics/run_1"
        assert args.target_horizon == 10
        assert args.baseline_name == "baseline"

    def test_parse_calibrate_sentiment_weights_command(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "calibrate-sentiment-weights",
            "--start", "2020-01-01",
            "--end", "2025-12-31",
            "--top-n", "15",
            "--horizons", "5,10",
            "--all-symbols",
            "--output-dir", "artifacts/sentiment_calibration/run_1",
        ])
        assert args.command == "calibrate-sentiment-weights"
        assert args.start == "2020-01-01"
        assert args.end == "2025-12-31"
        assert args.top_n == 15
        assert args.horizons == "5,10"
        assert args.all_symbols is True
        assert args.output_dir == "artifacts/sentiment_calibration/run_1"

    def test_parse_walk_forward_sentiment_command(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "walk-forward-sentiment",
            "--start", "2020-01-01",
            "--end", "2025-12-31",
            "--top-n", "12",
            "--horizons", "5,10",
            "--min-train-days", "126",
            "--test-days", "21",
            "--step-days", "21",
            "--max-positions", "8",
            "--equity", "75000",
            "--tp", "0.09",
            "--ts", "0.04",
            "--fees", "0.002",
            "--all-symbols",
            "--output-dir", "artifacts/sentiment_walk_forward/run_1",
        ])
        assert args.command == "walk-forward-sentiment"
        assert args.min_train_days == 126
        assert args.test_days == 21
        assert args.step_days == 21
        assert args.max_positions == 8
        assert args.equity == 75000
        assert args.tp == 0.09
        assert args.ts == 0.04
        assert args.fees == 0.002
        assert args.all_symbols is True
        assert args.output_dir == "artifacts/sentiment_walk_forward/run_1"


class TestWalkForwardUtils:
    def test_resolve_latest_walk_forward_weights_prefers_most_recent_file(self, tmp_path):
        from backtesting.walk_forward import resolve_latest_walk_forward_weights

        older = tmp_path / "run_old"
        newer = tmp_path / "run_new"
        older.mkdir()
        newer.mkdir()
        older_file = older / "latest_best_weights.json"
        newer_file = newer / "champion_weights.json"
        older_file.write_text(json.dumps({"sentiment_weight": 0.1, "macro_weight": 0.1, "quant_weight": 0.8}), encoding="utf-8")
        newer_file.write_text(json.dumps({"sentiment_weight": 0.2, "macro_weight": 0.1, "quant_weight": 0.7}), encoding="utf-8")
        os.utime(older_file, (1, 1))
        os.utime(newer_file, (2, 2))

        weights = resolve_latest_walk_forward_weights([tmp_path])

        assert weights is not None
        assert weights.sentiment_weight == 0.2
        assert weights.quant_weight == 0.7


class TestBacktestingRegistry:
    def test_start_backtesting_run_rejects_duplicate_active_kind(self, monkeypatch):
        from ihm.services import backtesting_registry
        from ihm.services.backtesting_runner import BacktestRunOptions

        monkeypatch.setattr(
            backtesting_registry,
            "list_active_backtesting_runs_by_kind",
            lambda run_kind: [{"run_id": "run-active-123", "run_kind": run_kind, "status": "running"}],
        )

        try:
            backtesting_registry.start_backtesting_run(
                "run",
                "Backtest complet",
                BacktestRunOptions(start="2025-04-21", end="2025-04-14"),
            )
        except RuntimeError as exc:
            assert "déjà en cours" in str(exc)
            assert "run-active-123" in str(exc)
        else:
            raise AssertionError("Le registre aurait dû bloquer un second run du même type.")






