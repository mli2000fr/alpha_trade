"""Tests unitaires pour le module backtesting."""
from __future__ import annotations

from datetime import date
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
        pf = engine.run(close=close, high=high, low=low, signals_df=signals_df)
        final_value = pf.final_value()
        if hasattr(final_value, "iloc"):
            final_value = final_value.iloc[0]
        assert float(final_value) > 0.0


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
        assert args.sentiment_lookback == 365
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






