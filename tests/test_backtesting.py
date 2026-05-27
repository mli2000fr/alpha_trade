"""Tests unitaires pour le module backtesting."""
from __future__ import annotations

from datetime import date
import logging
from pathlib import Path
import json
import os
from types import SimpleNamespace
from typing import cast

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def _make_single_row_walk_forward_scores_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "symbol": ["AAPL"],
            "trade_date": [pd.Timestamp("2025-01-01")],
            "final_score": [0.7],
            "final_score_sentiment": [0.9],
            "sentiment_net_agg": [1.0],
            "sector_impact_agg": [0.0],
        }
    )


def _make_swing_backtest_config():  # type: ignore[no-untyped-def]
    from backtesting.simulator import BacktestConfig
    from backtesting.trading_constraints import TradingConstraintConfig

    swing_constraints = TradingConstraintConfig(account_type="margin", pdt_rule="off", swing_only=True)
    return BacktestConfig(  # type: ignore[arg-type]
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 3),
        initial_equity=10_000,
        max_positions=1,
        trading_constraints=swing_constraints,
    )


def test_build_backtest_common_params_preserves_phase_and_baseline_metadata() -> None:
    from backtesting.cli import _impl

    class _Cfg:
        def __init__(self, *, is_default_value: bool):
            self._is_default_value = is_default_value

        def is_default(self) -> bool:
            return self._is_default_value

    args = SimpleNamespace(
        start="2025-01-01",
        end="2025-01-31",
        equity=25_000.0,
        tp=0.1,
        ts=0.05,
        max_positions=7,
        commission_bps=4.0,
        slippage_bps=6.0,
        fees=None,
        profile="strict_swing_cash",
        fidelity_baseline_id="smoke",
        fidelity_baseline_catalog="config/fidelity_baseline_catalog.json",
        sentiment_lookback=365,
        ml_mode="auto",
        sentiment_mode="rebuild-missing",
        artifacts_dir="artifacts/models",
        score_column="final_score_sentiment",
        walk_forward_artifacts_dir="artifacts/wf/run_1",
        no_save=False,
        risk_free_rate=0.02,
        slippage_model="fixed",
        slippage_base_bps=2.0,
        slippage_impact_coef=0.0,
        initial_stop_pct=0.03,
        max_entry_gap_pct=0.04,
        intrabar_priority="conservative",
        sizing_mode="equal_weight",
        sizing_min_weight_pct=0.0,
        sizing_max_weight_pct=0.2,
        regime_filter=True,
        regime_sma_window=200,
        regime_bear_threshold=-0.02,
        max_sector_exposure_pct=0.4,
        max_portfolio_dd_pct=0.15,
        dd_recovery_pct=0.95,
        target_annual_vol=0.2,
    )
    phase2_execution_result = SimpleNamespace(diagnostics={"targets": 3}, tca_summary={"fills": 2})
    params = _impl._build_backtest_common_params(
        args=args,
        fees_pct=0.001,
        effective_preset=SimpleNamespace(key="capital_0_5000"),
        preset_source="explicit_key",
        preset_fingerprint="abc123",
        engine_mode="pipeline",
        phase2_mode="risk_execution",
        phase3_mode="execution_replay",
        phase4_mode="protection_replay",
        phase5_mode="watcher_replay",
        phase7_mode="exit_lifecycle_replay",
        ml_pit_strategy="use-persisted",
        dividends_received=12.5,
        trading_constraints=SimpleNamespace(
            account_type="cash",
            pdt_rule="off",
            effective_pdt_rule="off",
            swing_only=True,
        ),
        bt_config=SimpleNamespace(execution_timing="next_session_open"),
        microstructure_cfg=_Cfg(is_default_value=False),
        risk_overlay_cfg=_Cfg(is_default_value=True),
        phase2_risk_result=SimpleNamespace(diagnostics={"signals_generated": 5}),
        phase2_execution_result=phase2_execution_result,
        phase3_execution_replay_result=SimpleNamespace(diagnostics={"scheduled_entries": 3}),
        phase4_protection_replay_result=SimpleNamespace(diagnostics={"protections_replayed": 3}),
        phase5_watcher_replay_result=SimpleNamespace(diagnostics={"transitioned_items": 2}),
        phase7_exit_lifecycle_result=SimpleNamespace(diagnostics={"exit_rows": 1}),
    )

    assert params["capital_preset_key"] == "capital_0_5000"
    assert params["fidelity_baseline_id"] == "smoke"
    assert params["ml_pit_strategy"] == "use-persisted"
    assert params["microstructure"]["is_default"] is False
    assert params["risk_overlay"]["is_default"] is True
    assert params["phase2"]["execution_tca"] == {"fills": 2}
    assert params["phase7"]["exit_lifecycle_replay"] == {"exit_rows": 1}


def test_collect_compare_to_live_trade_dates_merges_sources_without_duplicates() -> None:
    from backtesting.cli import _impl

    scores_df = pd.DataFrame({"trade_date": pd.to_datetime(["2025-01-02", "2025-01-03"])})
    research_signals_df = pd.DataFrame({"trade_date": pd.to_datetime(["2025-01-03", "2025-01-06"])})
    phase2_risk_result = SimpleNamespace(
        entries=[
            SimpleNamespace(score_snapshot_date=date(2025, 1, 2)),
            SimpleNamespace(score_snapshot_date=date(2025, 1, 7)),
        ]
    )
    phase2_execution_result = SimpleNamespace(
        targets=[
            SimpleNamespace(trade_date=date(2025, 1, 6)),
            SimpleNamespace(trade_date=date(2025, 1, 8)),
        ]
    )

    out = _impl._collect_compare_to_live_trade_dates(
        scores_df=scores_df,
        research_signals_df=research_signals_df,
        phase2_risk_result=phase2_risk_result,
        phase2_execution_result=phase2_execution_result,
    )

    assert [ts.date().isoformat() for ts in out] == [
        "2025-01-02",
        "2025-01-03",
        "2025-01-06",
        "2025-01-07",
        "2025-01-08",
    ]


def test_build_backtest_component_details_returns_expected_component_payloads() -> None:
    from backtesting.cli import _impl

    ohlcv_df = pd.DataFrame(
        {
            "symbol": ["AAPL", "MSFT", "AAPL"],
            "trade_date": pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-03"]),
        }
    )
    sessions = pd.DatetimeIndex(pd.to_datetime(["2025-01-02", "2025-01-03"]))
    execution_pivoted = {"close": pd.DataFrame({"AAPL": [100.0, 101.0]}, index=sessions)}

    component_details, execution_broker_like_summary = _impl._build_backtest_component_details(
        ohlcv_df=ohlcv_df,
        execution_pivoted=execution_pivoted,
        start_date=date(2025, 1, 2),
        end_date=date(2025, 1, 3),
        ohlcv_start=date(2024, 12, 15),
        signals_df=pd.DataFrame(),
        phase2_mode="off",
        phase3_mode="off",
        phase4_mode="off",
        phase5_mode="off",
        phase7_mode="off",
        phase2_risk_result=None,
        phase2_execution_result=None,
        phase3_execution_replay_result=None,
        phase4_protection_replay_result=None,
        phase5_watcher_replay_result=None,
        phase7_exit_lifecycle_result=None,
    )

    assert execution_broker_like_summary is None
    assert set(component_details.keys()) == {"bars", "risk", "execution"}
    assert component_details["bars"]["rows_loaded"] == 3
    assert component_details["bars"]["symbols_loaded"] == 2
    assert component_details["bars"]["calendar_sessions_loaded"] == 2
    assert component_details["risk"]["enabled"] is False
    assert component_details["execution"]["enabled"] is False
    assert component_details["execution"]["broker_like"] == {}


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

    def test_get_required_bars_source_filter_surfaces_inspection_cause(self, monkeypatch):
        from backtesting import data_loader

        def fake_inspect(_engine):
            raise RuntimeError("'cryptography' package is required for sha256_password auth methods")

        monkeypatch.setattr(data_loader, "inspect", fake_inspect)

        with pytest.raises(RuntimeError, match="cryptography") as exc_info:
            data_loader.get_required_bars_source_filter(cast(Engine, self._FakeEngine()), table_name="stock_bars_daily")

        assert "DB_HOST/DB_NAME" in str(exc_info.value)

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
                    {"name": "data_source"},
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

        df = data_loader.load_ohlcv(cast(Engine, self._FakeEngine()), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert "`date` AS trade_date" in captured["sql"]
        assert "COALESCE(adj_close, `close`) AS `close`" in captured["sql"]
        assert "data_source" in captured["sql"]
        assert "required_data_source" in captured["sql"]
        assert captured["params"]["required_data_source"] == "eodhd_eod"
        assert captured["parse_dates"] == ["trade_date"]

    def test_load_ohlcv_requires_data_source_column_for_eodhd_only_backtests(self, monkeypatch):
        from backtesting import data_loader

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

        monkeypatch.setattr(data_loader, "inspect", lambda _engine: FakeInspector())

        with pytest.raises(RuntimeError, match="data_source"):
            data_loader.load_ohlcv(cast(Engine, self._FakeEngine()), date(2025, 1, 1), date(2025, 1, 31))

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

        df = data_loader.load_scores(cast(Engine, self._FakeEngine()), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert "FROM stock_scores_history" in captured["sql"]
        assert "snapshot_date AS trade_date" in captured["sql"]

    def test_load_scores_filters_history_by_capital_preset_when_requested(self, monkeypatch):
        from backtesting import data_loader

        captured = {}

        class FakeInspector:
            def has_table(self, table_name):
                return table_name == "stock_scores_history"

        def fake_inspect(_engine):
            return FakeInspector()

        def fake_get_table_columns(_engine, table_name):
            if table_name == "stock_scores_history":
                return {"symbol", "snapshot_date", "final_score", "final_score_sentiment", "sector", "is_candidate", "capital_preset_key"}
            return set()

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            captured["sql"] = str(query)
            captured["params"] = params
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
        monkeypatch.setattr(data_loader, "_get_table_columns", fake_get_table_columns)
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        df = data_loader.load_scores(
            cast(Engine, self._FakeEngine()),
            date(2025, 1, 1),
            date(2025, 1, 31),
            capital_preset_key="capital_0_5000",
        )
        assert not df.empty
        assert "capital_preset_key = :capital_preset_key" in captured["sql"]
        assert captured["params"]["capital_preset_key"] == "capital_0_5000"

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

        df = data_loader.load_scores(cast(Engine, self._FakeEngine()), date(2025, 1, 1), date(2025, 1, 31))
        assert not df.empty
        assert len(calls) == 2
        assert "FROM stock_scores_history" in calls[0]
        assert "FROM stock_scores" in calls[1]

    def test_load_scores_pipeline_mode_requires_history_table(self, monkeypatch):
        from backtesting import data_loader
        from backtesting.fidelity import PitHistoryRequiredError

        class FakeInspector:
            def has_table(self, table_name):
                return False

        monkeypatch.setattr(data_loader, "inspect", lambda _engine: FakeInspector())

        with pytest.raises(PitHistoryRequiredError, match="stock_scores_history"):
            data_loader.load_scores(
                cast(Engine, self._FakeEngine()),
                date(2025, 1, 1),
                date(2025, 1, 31),
                strict_pit=True,
            )

    def test_load_scores_pipeline_mode_requires_history_rows(self, monkeypatch):
        from backtesting import data_loader
        from backtesting.fidelity import PitHistoryRequiredError

        class FakeInspector:
            def has_table(self, table_name):
                return table_name == "stock_scores_history"

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            return pd.DataFrame(columns=["symbol", "trade_date", "final_score", "final_score_sentiment", "sector", "is_candidate"])

        monkeypatch.setattr(data_loader, "inspect", lambda _engine: FakeInspector())
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        with pytest.raises(PitHistoryRequiredError, match="aucun snapshot PIT"):
            data_loader.load_scores(
                cast(Engine, self._FakeEngine()),
                date(2025, 1, 1),
                date(2025, 1, 31),
                capital_preset_key="capital_0_5000",
                strict_pit=True,
            )

    def test_load_scores_asof_latest_reuses_latest_snapshot_before_trade_date(self, monkeypatch):
        from backtesting import data_loader

        captured = {}

        class FakeInspector:
            def has_table(self, table_name):
                return table_name == "stock_scores_history"

        def fake_get_table_columns(_engine, table_name, *, required=False):
            if table_name == "stock_scores_history":
                return {
                    "symbol", "snapshot_date", "final_score", "final_score_sentiment", "sector", "is_candidate",
                    "capital_preset_key", "config_fingerprint",
                }
            if table_name == "stock_bars_daily":
                return {"trade_date", "data_source"}
            return set()

        def fake_read_sql(query, conn, params=None, parse_dates=None):
            captured["sql"] = str(query)
            captured["params"] = params
            return pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "trade_date": pd.to_datetime(["2025-01-03"]),
                    "source_snapshot_date": [date(2025, 1, 2)],
                    "capital_preset_key": ["capital_0_5000"],
                    "config_fingerprint": ["fp-001"],
                    "final_score": [0.8],
                    "final_score_sentiment": [0.82],
                    "sector": ["Tech"],
                    "is_candidate": [1],
                    "score_source": ["final_score_sentiment"],
                }
            )

        monkeypatch.setattr(data_loader, "inspect", lambda _engine: FakeInspector())
        monkeypatch.setattr(data_loader, "_get_table_columns", fake_get_table_columns)
        monkeypatch.setattr(data_loader.pd, "read_sql", fake_read_sql)

        df = data_loader.load_scores(
            cast(Engine, self._FakeEngine()),
            date(2025, 1, 1),
            date(2025, 1, 31),
            capital_preset_key="capital_0_5000",
            scores_pit_mode="asof_latest",
        )

        assert not df.empty
        assert df.iloc[0]["trade_date"] == pd.Timestamp("2025-01-03")
        assert "MAX(snapshot_date)" in captured["sql"]
        assert "FROM stock_bars_daily" in captured["sql"]
        assert "source_snapshot_date" in captured["sql"]
        assert captured["params"]["capital_preset_key"] == "capital_0_5000"

    def test_load_scores_rejects_unknown_scores_pit_mode(self):
        from backtesting import data_loader

        with pytest.raises(ValueError, match="scores_pit_mode"):
            data_loader.load_scores(
                cast(Engine, self._FakeEngine()),
                date(2025, 1, 1),
                date(2025, 1, 31),
                scores_pit_mode="unexpected",
            )

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

        df = data_loader.load_predictions(cast(Engine, self._FakeEngine()), date(2025, 1, 1), date(2025, 1, 31))
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

        df = data_loader.load_sentiment(cast(Engine, self._FakeEngine()), date(2025, 1, 1), date(2025, 1, 31))
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

        memory_engine: Engine = create_engine("sqlite:///:memory:")
        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.9],
        })
        result = prepare_scores_for_sentiment_mode(memory_engine, scores, sentiment_mode="off")
        assert result.iloc[0]["final_score_sentiment"] == 0.7

    def test_prepare_scores_sentiment_auto_fills_missing(self):
        from backtesting.resilience import prepare_scores_for_sentiment_mode

        memory_engine: Engine = create_engine("sqlite:///:memory:")
        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [None],
        })
        result = prepare_scores_for_sentiment_mode(memory_engine, scores, sentiment_mode="auto")
        assert result.iloc[0]["final_score_sentiment"] == 0.7

    def test_prepare_scores_applies_latest_walk_forward_weights_when_available(self, tmp_path):
        from backtesting.resilience import prepare_scores_for_sentiment_mode

        memory_engine: Engine = create_engine("sqlite:///:memory:")
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
        scores = _make_single_row_walk_forward_scores_df()

        result = prepare_scores_for_sentiment_mode(
            memory_engine,
            scores,
            sentiment_mode="auto",
            walk_forward_artifacts_dir=tmp_path,
        )

        # A-027 : quant_weight=0.70 est clippé à WEIGHT_MAX=0.40 → score clippé.
        assert result.iloc[0]["final_score_walk_forward"] == pytest.approx(0.53, abs=1e-6)
        assert result.iloc[0]["walk_forward_quant_weight"] == pytest.approx(0.40, abs=1e-6)
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

    def test_prepare_scores_diagnostics_expose_missing_sentiment_symbols(self):
        from backtesting.resilience import prepare_scores_for_sentiment_mode

        memory_engine: Engine = create_engine("sqlite:///:memory:")
        scores = pd.DataFrame({
            "symbol": ["AAPL", "MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
            "final_score": [0.7, 0.6],
            "final_score_sentiment": [None, 0.8],
        })

        prepared = prepare_scores_for_sentiment_mode(
            memory_engine,
            scores,
            sentiment_mode="auto",
            return_diagnostics=True,
        )

        assert prepared.diagnostics.missing_symbols_before == ("AAPL",)
        assert prepared.diagnostics.missing_symbols_after == ()

    def test_prepare_predictions_diagnostics_expose_missing_ml_symbols(self):
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

        prepared = prepare_predictions_for_ml_mode(
            None,  # type: ignore[arg-type]
            scores,
            preds,
            ml_mode="auto",
            artifacts_dir=Path("artifacts/models"),
            return_diagnostics=True,
        )

        assert prepared.diagnostics.missing_symbols_before == ("MSFT",)
        assert prepared.diagnostics.missing_symbols_after == ("MSFT",)
        assert prepared.diagnostics.missing_cause_breakdown == {"prediction_missing": 1}
        assert prepared.diagnostics.missing_causes_by_symbol == {"MSFT": ("prediction_missing",)}

    def test_prepare_predictions_rebuild_missing_classifies_artifact_missing(self, monkeypatch):
        from backtesting import resilience

        scores = pd.DataFrame({
            "symbol": ["MSFT"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
        })
        preds = pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])

        monkeypatch.setattr(resilience, "predict_batch", lambda *args, **kwargs: None)
        monkeypatch.setattr(resilience, "reset_runtime_status", lambda initial=None: None)
        monkeypatch.setattr(
            resilience,
            "snapshot_runtime_status",
            lambda: {"last_artifact_issue_reason": "config_missing"},
        )

        prepared = resilience.prepare_predictions_for_ml_mode(
            None,  # type: ignore[arg-type]
            scores,
            preds,
            ml_mode="rebuild-missing",
            artifacts_dir=Path("artifacts/models"),
            return_diagnostics=True,
        )

        assert prepared.diagnostics.missing_cause_breakdown == {"artifact_missing": 1}
        assert prepared.diagnostics.missing_causes_by_symbol == {"MSFT": ("artifact_missing",)}

    def test_prepare_predictions_rebuild_missing_classifies_artifact_invalid(self, monkeypatch):
        from backtesting import resilience

        scores = pd.DataFrame({
            "symbol": ["NVDA"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
        })
        preds = pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])

        monkeypatch.setattr(resilience, "predict_batch", lambda *args, **kwargs: None)
        monkeypatch.setattr(resilience, "reset_runtime_status", lambda initial=None: None)
        monkeypatch.setattr(
            resilience,
            "snapshot_runtime_status",
            lambda: {"last_artifact_issue_reason": "lstm_checkpoint_corrupted:lstm_attention"},
        )

        prepared = resilience.prepare_predictions_for_ml_mode(
            None,  # type: ignore[arg-type]
            scores,
            preds,
            ml_mode="rebuild-missing",
            artifacts_dir=Path("artifacts/models"),
            return_diagnostics=True,
        )

        assert prepared.diagnostics.missing_cause_breakdown == {"artifact_invalid": 1}
        assert prepared.diagnostics.missing_causes_by_symbol == {"NVDA": ("artifact_invalid",)}

    def test_prepare_predictions_ml_rebuild_missing_calls_predictor_grouped_by_trade_date(self, monkeypatch):
        from backtesting import resilience

        scores = pd.DataFrame({
            "symbol": ["AAPL", "MSFT", "NVDA", "TSLA"],
            "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-01", "2025-01-02"]),
        })
        preds = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "predicted_proba": [0.6],
            "predicted_class": [1],
        })
        calls = []

        def fake_predict_batch(symbols, artifacts_dir, engine, prediction_date=None, as_of_date=None, persist=True):
            calls.append((tuple(symbols), prediction_date, as_of_date, persist))
            return pd.DataFrame({
                "symbol": list(symbols),
                "prediction_date": [prediction_date] * len(symbols),
                "predicted_proba": [0.55] * len(symbols),
                "predicted_class": [1] * len(symbols),
                "run_id": ["run-x"] * len(symbols),
            })

        monkeypatch.setattr(resilience, "predict_batch", fake_predict_batch)
        result = resilience.prepare_predictions_for_ml_mode(
            None, scores, preds, ml_mode="rebuild-missing", artifacts_dir=Path("artifacts/models")
        )  # type: ignore[arg-type]
        assert len(result) == 4
        assert calls == [
            (("MSFT", "NVDA"), date(2025, 1, 1), date(2025, 1, 1), True),
            (("TSLA",), date(2025, 1, 2), date(2025, 1, 2), True),
        ]

    def test_prepare_scores_pipeline_rebuild_missing_does_not_write_back(self, monkeypatch):
        from backtesting import resilience

        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [None],
            "capital_preset_key": ["capital_0_5000"],
            "config_fingerprint": ["fp-123"],
        })
        persisted: list[bool] = []

        class FakeService:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def build_snapshot_for_date(self, snapshot_date):
                return pd.DataFrame({
                    "snapshot_date": [snapshot_date],
                    "symbol": ["AAPL"],
                    "final_score_sentiment": [0.91],
                })

            def persist_snapshot(self, snapshot, overwrite_existing=False):
                persisted.append(True)
                return len(snapshot)

        monkeypatch.setattr(resilience, "BackfillScoresHistoryService", FakeService)

        prepared = resilience.prepare_scores_for_sentiment_mode(
            None,  # type: ignore[arg-type]
            scores,
            sentiment_mode="rebuild-missing",
            engine_mode="pipeline",
            return_diagnostics=True,
        )

        assert prepared.frame.iloc[0]["final_score_sentiment"] == 0.91
        assert prepared.diagnostics.writeback_enabled is False
        assert prepared.diagnostics.writeback_performed is False
        assert persisted == []

    def test_prepare_predictions_pipeline_rebuild_missing_disables_persist(self, monkeypatch):
        from backtesting import resilience

        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
        })
        preds = pd.DataFrame(columns=["symbol", "trade_date", "predicted_proba", "predicted_class"])
        calls: list[tuple[tuple[str, ...], date, date, bool]] = []

        def fake_predict_batch(symbols, artifacts_dir, engine, prediction_date=None, as_of_date=None, persist=True):
            calls.append((tuple(symbols), prediction_date, as_of_date, persist))
            return pd.DataFrame({
                "symbol": list(symbols),
                "prediction_date": [prediction_date] * len(symbols),
                "predicted_proba": [0.66] * len(symbols),
                "predicted_class": [1] * len(symbols),
            })

        monkeypatch.setattr(resilience, "predict_batch", fake_predict_batch)

        prepared = resilience.prepare_predictions_for_ml_mode(
            None,  # type: ignore[arg-type]
            scores,
            preds,
            ml_mode="rebuild-missing",
            artifacts_dir=Path("artifacts/models"),
            engine_mode="pipeline",
            ml_pit_strategy="rebuild-missing",
            return_diagnostics=True,
        )

        assert len(prepared.frame) == 1
        assert prepared.diagnostics.persist_enabled is False
        assert prepared.diagnostics.persist_performed is False
        assert calls == [(("AAPL",), date(2025, 1, 1), date(2025, 1, 1), False)]

    def test_prepare_predictions_walk_forward_strategy_not_supported_yet(self):
        from backtesting import resilience
        from backtesting.fidelity import PitMlStrategyUnsupportedError

        scores = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
        })

        with pytest.raises(PitMlStrategyUnsupportedError, match="walk-forward-train-then-predict"):
            resilience.prepare_predictions_for_ml_mode(
                None,  # type: ignore[arg-type]
                scores,
                pd.DataFrame(),
                ml_mode="auto",
                artifacts_dir=Path("artifacts/models"),
                engine_mode="pipeline",
                ml_pit_strategy="walk-forward-train-then-predict",
            )


def test_emit_backtest_missing_coverage_logs_lists_missing_symbols(monkeypatch) -> None:
    import backtesting.cli._impl as cli_impl

    printed: list[str] = []
    monkeypatch.setattr(cli_impl, "_safe_print", lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)))

    cli_impl._emit_backtest_missing_coverage_logs(
        sentiment_mode="auto",
        sentiment_diagnostics=SimpleNamespace(
            missing_symbols_before=("AAPL", "MSFT"),
            missing_symbols_after=("MSFT",),
        ),
        ml_mode="auto",
        ml_diagnostics=SimpleNamespace(
            missing_symbols_before=("NVDA",),
            missing_symbols_after=("NVDA",),
        ),
    )

    assert any("AAPL" in message and "MSFT" in message for message in printed)
    assert any("NVDA" in message for message in printed)


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

    def test_backtest_engine_execution_replay_mode_uses_signal_share_override(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
        open_ = pd.DataFrame({"AAPL": [100.0, 105.0, 106.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 110.0, 106.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [101.0, 120.0, 107.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 104.0, 105.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
                "approved_shares": [7],
                "filled_qty": [7.0],
                "target_weight": [0.10],
            }
        )

        result = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 3),
                initial_equity=10_000,
                max_positions=1,
                execution_replay_mode="execution_replay",
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        trades_df = result.trades.records_readable
        assert not trades_df.empty
        assert float(trades_df["Size"].iloc[0]) == 7.0

    def test_backtest_engine_returns_flat_result_when_signals_are_empty(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 101.0, 102.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [101.0, 102.0, 103.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 100.0, 101.0]}, index=idx)

        engine = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 3),
                initial_equity=10_000,
                max_positions=1,
            )
        )

        result = engine.run(open=open_, close=close, high=high, low=low, signals_df=pd.DataFrame())

        assert result.final_value() == 10_000.0
        assert result.trades.count() == 0
        assert result.value().tolist() == [10_000.0, 10_000.0, 10_000.0]

    def test_backtest_engine_protection_replay_mode_uses_replayed_initial_stop(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
        open_ = pd.DataFrame({"AAPL": [100.0, 100.0, 100.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 100.0, 98.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [100.0, 104.0, 100.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [100.0, 100.0, 96.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
                "approved_shares": [5],
                "filled_qty": [5.0],
                "replay_take_profit_price": [120.0],
                "replay_initial_stop_price": [97.0],
                "replay_trailing_stop_pct": [0.20],
                "replay_trailing_activation_price": [130.0],
            }
        )

        result = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 3),
                initial_equity=10_000,
                max_positions=1,
                execution_replay_mode="execution_replay",
                protection_replay_mode="protection_replay",
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        trades_df = result.closed_trades_df
        assert len(trades_df) == 1
        assert trades_df.iloc[0]["exit_reason"] == "initial_stop"
        assert float(trades_df.iloc[0]["exit_price"]) == 97.0

    def test_backtest_engine_watcher_replay_delays_trailing_until_effective_date(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-06"])
        open_ = pd.DataFrame({"AAPL": [100.0, 100.0, 100.0, 100.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 108.0, 107.0, 106.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [100.0, 110.0, 108.0, 107.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [100.0, 97.0, 97.0, 105.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
                "approved_shares": [5],
                "filled_qty": [5.0],
                "replay_take_profit_price": [150.0],
                "replay_initial_stop_price": [90.0],
                "replay_trailing_stop_pct": [0.02],
                "replay_trailing_activation_price": [106.0],
                "watcher_transition_state": ["transitioned"],
                "watcher_trigger_date": pd.to_datetime(["2025-01-02"]),
                "watcher_transition_effective_date": pd.to_datetime(["2025-01-03"]),
            }
        )

        result = BacktestEngine(
            BacktestConfig(
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 6),
                initial_equity=10_000,
                max_positions=1,
                execution_replay_mode="execution_replay",
                protection_replay_mode="protection_replay",
                watcher_replay_mode="watcher_replay",
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        trades_df = result.closed_trades_df
        assert len(trades_df) == 1
        assert trades_df.iloc[0]["exit_date"] == pd.Timestamp("2025-01-03")
        assert trades_df.iloc[0]["exit_reason"] == "trailing_stop"
        assert result.diagnostics.watcher_replay_transitions == 1

    def test_backtest_engine_trade_audit_logs_entries_and_exits_with_signal_context(self, caplog):
        from backtesting.simulator import BacktestConfig, BacktestEngine

        idx = pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"])
        open_ = pd.DataFrame({"AAPL": [100.0, 101.0, 104.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [100.0, 103.0, 104.0]}, index=idx)
        high = pd.DataFrame({"AAPL": [100.0, 110.0, 104.0]}, index=idx)
        low = pd.DataFrame({"AAPL": [99.0, 100.0, 103.0]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
                "score": [0.81],
                "score_source": ["final_score_sentiment"],
                "predicted_proba": [0.73],
                "conviction": [0.762],
                "decision_reason": ["top conviction daily basket"],
            }
        )

        with caplog.at_level(logging.INFO):
            result = BacktestEngine(
                BacktestConfig(
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 1, 3),
                    initial_equity=10_000,
                    max_positions=1,
                )
            ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        assert not result.trade_events_df.empty
        assert result.trade_events_df["event_type"].tolist() == ["entry_opened", "exit_closed"]
        assert result.trade_events_df.iloc[0]["score"] == pytest.approx(0.81)
        assert result.trade_events_df.iloc[0]["conviction"] == pytest.approx(0.762)
        assert result.trade_events_df.iloc[0]["entry_reason"] == "top conviction daily basket"
        assert result.closed_trades_df.iloc[0]["score_source"] == "final_score_sentiment"
        assert result.closed_trades_df.iloc[0]["entry_reason"] == "top conviction daily basket"
        assert any("event_type=entry_opened" in record.message for record in caplog.records)
        assert any("event_type=exit_closed" in record.message for record in caplog.records)

    def test_to_scalar_supports_series_and_scalar(self):
        from backtesting.simulator import BacktestEngine, BacktestConfig

        engine = BacktestEngine(BacktestConfig(start_date=date(2025, 1, 1), end_date=date(2025, 1, 2)))

        assert engine._to_scalar(pd.Series([123.4])) == 123.4
        assert engine._to_scalar(99.0) == 99.0

    def test_backtest_engine_returns_flat_result_when_no_common_symbols(self):
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

        result = engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        assert result.final_value() == 100000.0
        assert result.trades.count() == 0
        assert result.closed_trades_df.empty

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
            BacktestConfig(  # type: ignore[arg-type]
                start_date=date(2025, 1, 1),
                end_date=date(2025, 1, 3),
                initial_equity=10_000,
                max_positions=1,
                trading_constraints=TradingConstraintConfig(account_type="margin", pdt_rule="off", swing_only=False),
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        swing_cfg = _make_swing_backtest_config()
        swing_engine = BacktestEngine(
            swing_cfg
        )
        swing = swing_engine.run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        assert float(standard.closed_trades_df.iloc[0]["entry_price"]) == 105.0
        assert float(swing.closed_trades_df.iloc[0]["entry_price"]) == 105.0
        assert standard.closed_trades_df.iloc[0]["entry_date"] == pd.Timestamp("2025-01-02")
        assert swing.closed_trades_df.iloc[0]["entry_date"] == pd.Timestamp("2025-01-02")
        assert standard.closed_trades_df.iloc[0]["exit_date"] == pd.Timestamp("2025-01-02")
        assert swing.closed_trades_df.iloc[0]["exit_date"] == pd.Timestamp("2025-01-03")

    def test_backtest_engine_carries_forward_last_close_for_mark_to_market_when_current_close_missing(self):
        from backtesting.simulator import BacktestConfig, BacktestEngine
        from backtesting.trading_constraints import TradingConstraintConfig

        idx = pd.to_datetime(["2024-11-26", "2024-11-27", "2024-11-28", "2024-11-29"])
        open_ = pd.DataFrame({"AAPL": [10.0, 10.0, 10.0, 10.0]}, index=idx)
        close = pd.DataFrame({"AAPL": [10.0, 10.5, None, 10.4]}, index=idx)
        high = pd.DataFrame({"AAPL": [10.0, 10.6, None, 10.5]}, index=idx)
        low = pd.DataFrame({"AAPL": [10.0, 10.0, None, 10.2]}, index=idx)
        signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2024-11-26"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
            }
        )

        result = BacktestEngine(
            BacktestConfig(
                start_date=date(2024, 11, 26),
                end_date=date(2024, 11, 29),
                initial_equity=1_000,
                max_positions=1,
                fees_pct=0.0,
                profit_taker_pct=1.0,
                trailing_stop_pct=0.99,
                trading_constraints=TradingConstraintConfig(account_type="cash", pdt_rule="off", swing_only=True),
            )
        ).run(open=open_, close=close, high=high, low=low, signals_df=signals_df)

        assert result.closed_trades_df.empty
        assert result.equity_curve.loc[pd.Timestamp("2024-11-27")] == pytest.approx(1050.0)
        assert result.equity_curve.loc[pd.Timestamp("2024-11-28")] == pytest.approx(1050.0)
        assert result.equity_curve.loc[pd.Timestamp("2024-11-29")] == pytest.approx(1040.0)

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

    def test_save_trade_audit_csv_exports_event_log(self, tmp_path: Path):
        from backtesting.report import save_trade_audit_csv

        pf = SimpleNamespace(
            trade_events_df=pd.DataFrame(
                [
                    {
                        "event_type": "entry_opened",
                        "symbol": "AAPL",
                        "score": 0.81,
                        "entry_reason": "top conviction daily basket",
                    },
                    {
                        "event_type": "exit_closed",
                        "symbol": "AAPL",
                        "exit_reason": "take_profit",
                        "pnl": 42.0,
                    },
                ]
            )
        )

        out = save_trade_audit_csv(pf, output_dir=tmp_path)

        exported = pd.read_csv(out)
        assert out.name == "trade_audit_log.csv"
        assert exported["event_type"].tolist() == ["entry_opened", "exit_closed"]
        assert exported.iloc[0]["entry_reason"] == "top conviction daily basket"

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

    def test_save_report_json_includes_fidelity_block(self, tmp_path):
        from backtesting.report import BacktestReport, save_report_json

        report = BacktestReport(
            initial_equity=10_000,
            final_value=11_000,
            total_return_pct=10.0,
            cagr_pct=5.0,
            sharpe_ratio=1.0,
            sortino_ratio=1.2,
            max_drawdown_pct=3.0,
            total_trades=4,
            win_rate_pct=50.0,
            avg_trade_duration_days=2.0,
            profit_factor=1.5,
        )

        report_json_path = save_report_json(
            report,
            output_dir=tmp_path,
            fidelity={"engine_mode": "pipeline", "strict_pit_requested": True},
        )

        payload = json.loads(report_json_path.read_text(encoding="utf-8"))
        assert payload["fidelity"]["engine_mode"] == "pipeline"
        assert payload["fidelity"]["strict_pit_requested"] is True


# ============================================================
# test CLI parsing
# ============================================================

class TestCLI:
    # Phase A/B/C (refactor) — défauts neutres à fournir aux Namespace
    # construits manuellement dans les tests CLI. Reflète strictement les
    # défauts de `backtesting.cli._build_parser()`.
    _CLI_NEUTRAL_DEFAULTS: dict[str, object] = {
        # Phase 6.1.b — costs explicites + profil.
        "commission_bps": 5.0,
        "slippage_bps": 5.0,
        "profile": "custom",
        # Phase A — reproductibilité + risk-free rate.
        "risk_free_rate": 0.0,
        "seed": None,
        # Phase B — micro-structure (tous neutres).
        "slippage_model": "fixed",
        "slippage_base_bps": 0.0,
        "slippage_impact_coef": 0.0,
        "initial_stop_pct": 0.0,
        "max_entry_gap_pct": 0.0,
        "intrabar_priority": "conservative",
        # Phase C — risk overlays (tous désactivés).
        "sizing_mode": "equal_weight",
        "sizing_min_weight_pct": 0.005,
        "sizing_max_weight_pct": 0.20,
        "regime_filter": False,
        "regime_sma_window": 200,
        "regime_bear_threshold": -0.02,
        "max_sector_exposure_pct": 0.0,
        "max_portfolio_dd_pct": 0.0,
        "dd_recovery_pct": 0.95,
        "target_annual_vol": None,
        # Phase 2 — bridges opt-in.
        "phase2_mode": "off",
        "phase3_mode": "off",
        "phase4_mode": "off",
        "phase5_mode": "off",
        "phase7_mode": "off",
    }

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
        # Phase 6.1.b — `--fees` est déprécié (None par défaut), coûts via bps.
        assert args.fees is None
        assert args.commission_bps == 5.0
        assert args.slippage_bps == 5.0
        # Phase 6.1.e — profil custom par défaut.
        assert args.profile == "custom"
        assert args.account_type == "margin"
        assert args.pdt_rule == "auto"
        assert args.macro_missing_policy is None
        assert args.fidelity_baseline_id is None
        assert args.fidelity_baseline_catalog is None

    def test_parse_run_command_accepts_macro_missing_policy_flags(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()

        args_allow = parser.parse_args([
            "run",
            "--start", "2025-01-01",
            "--allow-neutral-fallback-on-missing-macro-data",
        ])
        args_fail = parser.parse_args([
            "run",
            "--start", "2025-01-01",
            "--fail-on-missing-macro-data",
        ])

        assert args_allow.macro_missing_policy == "allow"
        assert args_fail.macro_missing_policy == "fail"

    def test_parse_run_command_accepts_fidelity_baseline_options(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "run",
            "--start", "2025-01-01",
            "--fidelity-baseline-id", "pipeline_live_like_smoke",
            "--fidelity-baseline-catalog", "config/fidelity_baseline_catalog.json",
        ])

        assert args.fidelity_baseline_id == "pipeline_live_like_smoke"
        assert args.fidelity_baseline_catalog == "config/fidelity_baseline_catalog.json"
        assert args.swing_only is False
        assert args.sentiment_lookback == 365
        assert args.ml_mode == "auto"
        assert args.sentiment_mode == "auto"
        assert args.score_column == "auto"
        assert args.walk_forward_artifacts_dir is None
        assert args.engine_mode == "research"
        assert args.scores_pit_mode == "exact"
        assert args.macro_pit_mode == "yaml_default"
        assert args.ml_pit_strategy == "auto"
        assert args.phase2_mode == "off"
        assert args.phase3_mode == "off"
        assert args.phase4_mode == "off"
        assert args.phase5_mode == "off"
        assert args.phase7_mode == "off"
        assert args.no_save is False

    def test_parse_run_engine_mode_pipeline(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--engine-mode", "pipeline"])

        assert args.command == "run"
        assert args.engine_mode == "pipeline"

    def test_parse_run_scores_pit_mode_asof_latest(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--scores-pit-mode", "asof_latest"])

        assert args.command == "run"
        assert args.scores_pit_mode == "asof_latest"

    def test_parse_run_macro_pit_mode_j_minus_1_strict(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--macro-pit-mode", "j_minus_1_strict"])

        assert args.command == "run"
        assert args.macro_pit_mode == "j_minus_1_strict"

    def test_parse_run_ml_pit_strategy(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--ml-pit-strategy", "use-persisted"])

        assert args.command == "run"
        assert args.ml_pit_strategy == "use-persisted"

    def test_parse_run_phase2_mode(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--phase2-mode", "risk_execution"])

        assert args.command == "run"
        assert args.phase2_mode == "risk_execution"

    def test_parse_run_phase3_mode(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--phase3-mode", "execution_replay"])

        assert args.command == "run"
        assert args.phase3_mode == "execution_replay"

    def test_parse_run_phase4_mode(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--phase4-mode", "protection_replay"])

        assert args.command == "run"
        assert args.phase4_mode == "protection_replay"

    def test_parse_run_phase5_mode(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--phase5-mode", "watcher_replay"])

        assert args.command == "run"
        assert args.phase5_mode == "watcher_replay"

    def test_parse_run_phase7_mode(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["run", "--start", "2020-01-01", "--phase7-mode", "exit_lifecycle_replay"])

        assert args.command == "run"
        assert args.phase7_mode == "exit_lifecycle_replay"

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

    def test_parse_run_walk_forward_options(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "run", "--start", "2020-01-01",
            "--score-column", "final_score_walk_forward",
            "--walk-forward-artifacts-dir", "artifacts/sentiment_walk_forward/run_1",
        ])
        assert args.score_column == "final_score_walk_forward"
        assert args.walk_forward_artifacts_dir == "artifacts/sentiment_walk_forward/run_1"

    def test_phase2_ohlcv_history_start_adds_warmup_for_atr_and_correlation(self):
        from backtesting.cli._impl import _resolve_phase2_ohlcv_history_start

        start = date(2020, 1, 1)

        history_start = _resolve_phase2_ohlcv_history_start(
            start,
            atr_window=20,
            correlation_lookback_days=60,
        )

        assert history_start < start
        assert (start - history_start).days == 95

    def test_run_backtest_phase2_loads_ohlcv_warmup_for_risk_but_keeps_execution_window(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, report, resilience, risk_bridge, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        requested_start = date(2020, 1, 1)
        requested_end = date(2020, 1, 2)
        trading_days = pd.to_datetime(["2019-12-30", "2019-12-31", "2020-01-01", "2020-01-02"])
        ohlcv_df = pd.DataFrame(
            {
                "symbol": ["AAPL"] * len(trading_days),
                "trade_date": trading_days,
                "open": [98.0, 99.0, 100.0, 101.0],
                "high": [99.0, 100.0, 101.0, 102.0],
                "low": [97.0, 98.0, 99.0, 100.0],
                "close": [98.5, 99.5, 100.5, 101.5],
                "volume": [1000, 1000, 1000, 1000],
            }
        )
        scores_df = pd.DataFrame(
            {
                "symbol": ["AAPL"],
                "trade_date": pd.to_datetime(["2020-01-01"]),
                "final_score": [0.7],
                "final_score_sentiment": [0.75],
                "sector": ["Tech"],
                "is_candidate": [1],
            }
        )
        phase2_signals_df = pd.DataFrame(
            {
                "trade_date": pd.to_datetime(["2020-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
            }
        )

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["engine_open_index"] = list(kwargs["open"].index)
                captured["signals_df"] = kwargs["signals_df"].copy()
                return FakePF()

        def fake_load_ohlcv(_engine, start, end):
            captured["ohlcv_start"] = start
            captured["ohlcv_end"] = end
            return ohlcv_df.copy()

        def fake_build_phase2_risk_result(**kwargs):
            captured["risk_close_index"] = list(kwargs["close_df"].index)
            return SimpleNamespace(
                entries=[{"symbol": "AAPL"}],
                signals_df=phase2_signals_df.copy(),
                diagnostics={
                    "snapshot_dates": 1,
                    "entries_total": 1,
                    "entries_accepted": 1,
                    "signals_generated": 1,
                    "bridge": "risk_management.portfolio_builder",
                },
            )

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", fake_load_ohlcv)
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(risk_bridge, "build_phase2_risk_result", fake_build_phase2_risk_result)
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", lambda *args, **kwargs: tmp_path / "report.json")
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2020-01-01",
            end="2020-01-02",
            equity=2_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=4,
            fees=0.001,
            account_type="cash",
            pdt_rule="off",
            swing_only=True,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=None,
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="pipeline",
            ml_pit_strategy="use-persisted",
            capital_preset_key="capital_0_5000",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk"},
        )

        cli._run_backtest(args)

        assert captured["ohlcv_end"] == requested_end
        assert cast(date, captured["ohlcv_start"]) < requested_start
        assert min(cast(list[pd.Timestamp], captured["risk_close_index"])) < pd.Timestamp(requested_start)
        assert pd.Timestamp("2020-01-01") not in cast(list[pd.Timestamp], captured["risk_close_index"])
        assert cast(list[pd.Timestamp], captured["engine_open_index"]) == [pd.Timestamp("2020-01-02")]
        assert cast(pd.DataFrame, captured["signals_df"]).equals(phase2_signals_df)

    def test_run_backtest_propagates_walk_forward_options(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, resilience, signal_replay, report, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        calls: dict[str, object] = {}
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                calls["signals_df"] = kwargs["signals_df"]
                return FakePF()

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })

        def fake_prepare_scores(engine, scores_df_in, *, sentiment_mode, walk_forward_artifacts_dir, **kwargs):
            calls["walk_forward_artifacts_dir"] = walk_forward_artifacts_dir
            calls["sentiment_mode"] = sentiment_mode
            return scores_df_in.copy()

        def fake_replay(scores_df_in, predictions_df, *, score_column=None, **kwargs):
            calls["score_column"] = score_column
            return pd.DataFrame({
                "trade_date": pd.to_datetime(["2025-01-01"]),
                "symbol": ["AAPL"],
                "selected": [True],
                "rank": [1.0],
            })

        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", fake_prepare_scores)
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", fake_replay)
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", lambda *args, **kwargs: tmp_path / "report.json")
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=None,
            score_column="final_score_walk_forward",
            walk_forward_artifacts_dir=str(tmp_path),
            engine_mode="research",
            **self._CLI_NEUTRAL_DEFAULTS,
        )

        cli._run_backtest(args)

        assert calls["score_column"] == "final_score_walk_forward"
        assert calls["walk_forward_artifacts_dir"] == Path(tmp_path)

    def test_run_backtest_overrides_market_regime_macro_missing_policy(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, resilience, report, simulator, risk_bridge
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection
        import common.config_loader as config_loader
        import service.market as market

        captured: dict[str, object] = {}
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "sector": ["Tech"],
            "is_candidate": [1],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                return FakePF()

        def fake_build_phase2_risk_result(**kwargs):
            mr_cfg = kwargs["market_regimes_config"]
            captured["allow_neutral_fallback_on_missing_macro_data"] = mr_cfg.allow_neutral_fallback_on_missing_macro_data
            return SimpleNamespace(
                entries=[],
                signals_df=pd.DataFrame(columns=["trade_date", "symbol", "selected", "rank"]),
                diagnostics={
                    "snapshot_dates": 1,
                    "entries_total": 0,
                    "entries_accepted": 0,
                    "signals_generated": 0,
                    "bridge": "risk_management.portfolio_builder",
                    "regime_enabled": True,
                },
            )

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(risk_bridge, "build_phase2_risk_result", fake_build_phase2_risk_result)
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", lambda *args, **kwargs: tmp_path / "report.json")
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")
        monkeypatch.setattr(config_loader, "load_config", lambda: {"market_regimes": {"enabled": True, "vix": {"enabled": True}}})
        monkeypatch.setattr(market, "build_default_macro_provider", lambda cfg: None)

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=None,
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            macro_missing_policy="fail",
            capital_preset_key="capital_50001_100000",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk"},
        )

        cli._run_backtest(args)

        assert captured["allow_neutral_fallback_on_missing_macro_data"] is False

    def test_run_backtest_phase3_requires_phase2_risk_execution(self, monkeypatch):
        import argparse
        import backtesting.cli as cli
        import backtesting.cli._impl as cli_impl

        printed: list[str] = []
        monkeypatch.setattr(cli_impl, "_safe_print", lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)))

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=None,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=None,
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "off", "phase3_mode": "execution_replay"},
        )

        with pytest.raises(SystemExit) as exc:
            cli._run_backtest(args)

        assert exc.value.code == 1
        assert any("risk_execution" in line for line in printed)

    def test_run_backtest_phase4_requires_phase3_execution_replay(self, monkeypatch):
        import argparse
        import backtesting.cli as cli
        import backtesting.cli._impl as cli_impl

        printed: list[str] = []
        monkeypatch.setattr(cli_impl, "_safe_print", lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)))

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=None,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=None,
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution", "phase3_mode": "off", "phase4_mode": "protection_replay"},
        )

        with pytest.raises(SystemExit) as exc:
            cli._run_backtest(args)

        assert exc.value.code == 1
        assert any("execution_replay" in line for line in printed)

    def test_run_backtest_phase5_requires_phase4_protection_replay(self, monkeypatch):
        import argparse
        import backtesting.cli as cli
        import backtesting.cli._impl as cli_impl

        printed: list[str] = []
        monkeypatch.setattr(cli_impl, "_safe_print", lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)))

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=None,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=None,
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution", "phase3_mode": "execution_replay", "phase4_mode": "off", "phase5_mode": "watcher_replay"},
        )

        with pytest.raises(SystemExit) as exc:
            cli._run_backtest(args)

        assert exc.value.code == 1
        assert any("protection_replay" in line for line in printed)

    def test_run_backtest_phase7_requires_phase5_watcher_replay(self, monkeypatch):
        import argparse
        import backtesting.cli as cli
        import backtesting.cli._impl as cli_impl

        printed: list[str] = []
        monkeypatch.setattr(cli_impl, "_safe_print", lambda *args, **kwargs: printed.append(" ".join(str(arg) for arg in args)))

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=None,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=None,
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution", "phase3_mode": "execution_replay", "phase4_mode": "protection_replay", "phase5_mode": "off", "phase7_mode": "exit_lifecycle_replay"},
        )

        with pytest.raises(SystemExit) as exc:
            cli._run_backtest(args)

        assert exc.value.code == 1
        assert any("watcher_replay" in line for line in printed)

    def test_run_backtest_with_real_walk_forward_artifact_writes_structured_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, report, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        output_dir = tmp_path / "out"
        weights_dir = tmp_path / "sentiment_walk_forward" / "run_001"
        weights_dir.mkdir(parents=True)
        (weights_dir / "latest_best_weights.json").write_text(
            json.dumps(
                {
                    "sentiment_weight": 0.9,
                    "macro_weight": 0.0,
                    "quant_weight": 0.1,
                    "calibration_run_id": "wf-real-001",
                    "calibration_source": "walk_forward",
                }
            ),
            encoding="utf-8",
        )

        ohlcv_df = pd.DataFrame(
            {
                "symbol": ["AAA", "BBB", "AAA", "BBB"],
                "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-02"]),
                "open": [100.0, 100.0, 101.0, 101.0],
                "high": [101.0, 101.0, 102.0, 102.0],
                "low": [99.0, 99.0, 100.0, 100.0],
                "close": [100.5, 100.5, 101.5, 101.5],
                "volume": [1000, 1000, 1100, 1100],
            }
        )
        scores_df = pd.DataFrame(
            {
                "symbol": ["AAA", "BBB"],
                "trade_date": pd.to_datetime(["2025-01-01", "2025-01-01"]),
                "final_score": [0.5, 0.5],
                "final_score_sentiment": [0.5, 0.5],
                "sentiment_net_agg": [-1.0, 1.0],
                "sector_impact_agg": [0.0, 0.0],
                "sector": ["Tech", "Tech"],
                "is_candidate": [1, 1],
            }
        )
        captured: dict[str, object] = {}

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                return FakePF()

        def fake_save_equity_curve_csv(pf, *, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "equity_curve.csv"
            path.write_text("trade_date,portfolio_value\n2025-01-02,100000\n", encoding="utf-8")
            return path

        def fake_save_trades_csv(pf, *, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "trades.csv"
            path.write_text("symbol,entry_date\nBBB,2025-01-02\n", encoding="utf-8")
            return path

        def fake_save_equity_curve(pf, *, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "equity_curve.png"
            path.write_text("png", encoding="utf-8")
            return path

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **_kwargs):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "report.json"
            payload = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": _kwargs.get("fidelity", {}),
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            captured["report_payload"] = payload
            return path

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve_csv", fake_save_equity_curve_csv)
        monkeypatch.setattr(report, "save_trades_csv", fake_save_trades_csv)
        monkeypatch.setattr(report, "save_equity_curve", fake_save_equity_curve)
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=1,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=False,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=str(tmp_path),
            engine_mode="research",
            **self._CLI_NEUTRAL_DEFAULTS,
        )

        cli._run_backtest(args)

        signals_df = cast(pd.DataFrame, captured["signals_df"])
        selected = signals_df[signals_df["selected"]].iloc[0]
        assert selected["symbol"] == "BBB"
        assert selected["score_source"] == "final_score_walk_forward"
        # A-027 : sentiment_weight=0.9 → clippé à 0.40, macro_weight=0.0 → clippé à 0.05
        # score = 0.4*normalize(1.0) + 0.05*normalize(0.0) + 0.1*0.5 = 0.40 + 0.025 + 0.05 = 0.475
        assert float(selected["score"]) == pytest.approx(0.475, abs=0.01)
        report_payload = cast(dict[str, object], captured["report_payload"])
        assert report_payload["params"]["walk_forward_artifacts_dir"] == str(tmp_path)
        assert report_payload["params"]["score_column"] == "auto"
        assert report_payload["params"]["engine_mode"] == "research"
        assert report_payload["fidelity"]["strict_pit_requested"] is False
        assert report_payload["fidelity"]["coverage"]["sentiment"]["rows_input"] == len(scores_df)
        assert report_payload["fidelity"]["provenance"]["scores"]["provenance_kind"] == "persisted_history"
        assert report_payload["fidelity"]["provenance"]["ml"]["missing_cause_breakdown"] == {"prediction_missing": 2}
        assert report_payload["fidelity"]["component_status"]["bars"]["status"] == "ok"
        assert report_payload["fidelity"]["component_status"]["walk_forward"]["status"] == "ok"
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["coverage_summary_json"].endswith("coverage_summary.json")
        assert artifacts["replay_diagnostic_summary_json"].endswith("replay_diagnostic_summary.json")
        assert artifacts["replay_diagnostic_sessions_csv"].endswith("replay_diagnostic_sessions.csv")
        assert artifacts["equity_curve_csv"].endswith("equity_curve.csv")
        assert artifacts["trades_csv"].endswith("trades.csv")
        assert artifacts["fidelity_manifest_json"].endswith("fidelity_manifest.json")
        assert (output_dir / "report.json").exists()
        assert (output_dir / "coverage_summary.json").exists()
        replay_payload = json.loads((output_dir / "replay_diagnostic_summary.json").read_text(encoding="utf-8"))
        assert replay_payload["session_count"] == 1
        assert replay_payload["sessions"][0]["selected_symbols"] == ["BBB"]
        assert replay_payload["sessions"][0]["degraded_components"] == ["ml"]
        assert replay_payload["sessions"][0]["critical_symbol"] == {
            "symbol": "BBB",
            "selected": True,
            "components": ["ml", "walk_forward"],
            "reasons": ["prediction_missing"],
            "score_source": "final_score_walk_forward",
        }
        assert replay_payload["sessions"][0]["provenance_refs"]["ml_run_ids"] == []
        assert (output_dir / "replay_diagnostic_sessions.csv").exists()

    def test_run_backtest_phase2_risk_uses_bridge_signals_and_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, report, resilience, risk_bridge, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        output_dir = tmp_path / "phase2_risk_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        phase2_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "score": [0.75],
            "score_source": ["risk_bridge"],
            "conviction_score": [0.75],
            "conviction_source": ["core.conviction:score_only"],
            "predicted_proba": [None],
            "decision_reason_code": ["ok"],
        })
        research_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "score": [0.75],
            "score_source": ["final_score_sentiment"],
            "conviction": [0.75],
            "conviction_source": ["core.conviction:score_only"],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                return FakePF()

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            captured["report_payload"] = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            return output_dir / "report.json"

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: research_signals_df.copy())

        def fake_build_phase2_risk_result(**kwargs):
            captured["risk_bridge_kwargs"] = kwargs
            return SimpleNamespace(
                entries=[
                    SimpleNamespace(
                        symbol="AAPL",
                        candidate_rank=1,
                        decision_rank=1,
                        score_used=0.75,
                        score_source="final_score_sentiment",
                        conviction_score=0.75,
                        predicted_proba=None,
                        decision="ACCEPTED",
                        decision_reason="OK",
                        decision_reason_code="ok",
                        target_weight=0.1,
                        approved_shares=10,
                        score_snapshot_date=date(2025, 1, 1),
                        prediction_asof_date=None,
                    )
                ],
                signals_df=phase2_signals_df.copy(),
                diagnostics={
                    "snapshot_dates": 1,
                    "entries_total": 1,
                    "entries_accepted": 1,
                    "signals_generated": 1,
                    "bridge": "risk_management.portfolio_builder",
                },
            )

        monkeypatch.setattr(risk_bridge, "build_phase2_risk_result", fake_build_phase2_risk_result)
        monkeypatch.setattr(
            risk_bridge,
            "save_phase2_risk_artifacts",
            lambda result, output_dir: {"phase2_risk_summary_json": str(output_dir / "phase2_risk_summary.json")},
        )
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk"},
        )

        cli._run_backtest(args)

        assert cast(pd.DataFrame, captured["signals_df"]).equals(phase2_signals_df)
        risk_kwargs = cast(dict[str, object], captured["risk_bridge_kwargs"])
        assert "risk_config" in risk_kwargs
        report_payload = cast(dict[str, object], captured["report_payload"])
        assert report_payload["params"]["phase2_mode"] == "risk"
        assert report_payload["params"]["phase2"]["enabled"] is True
        assert report_payload["params"]["phase2"]["mode"] == "risk"
        assert report_payload["params"]["phase2"]["risk_bridge"]["bridge"] == "risk_management.portfolio_builder"
        assert report_payload["params"]["phase2"]["execution_bridge"] is None
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["phase2_risk_summary_json"].endswith("phase2_risk_summary.json")
        assert artifacts["candidate_target_parity_summary_json"].endswith("candidate_target_parity_summary.json")
        assert artifacts["candidate_target_parity_sessions_csv"].endswith("candidate_target_parity_sessions.csv")

    def test_run_backtest_phase2_risk_execution_adds_execution_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, execution_bridge, report, resilience, risk_bridge, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        output_dir = tmp_path / "phase2_exec_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        phase2_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
        })
        research_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                return FakePF()

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            captured["report_payload"] = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            return output_dir / "report.json"

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: research_signals_df.copy())
        monkeypatch.setattr(
            risk_bridge,
            "build_phase2_risk_result",
            lambda **kwargs: SimpleNamespace(
                entries=["entry-a"],
                signals_df=phase2_signals_df.copy(),
                diagnostics={
                    "snapshot_dates": 1,
                    "entries_total": 1,
                    "entries_accepted": 1,
                    "signals_generated": 1,
                    "bridge": "risk_management.portfolio_builder",
                },
            ),
        )
        monkeypatch.setattr(
            risk_bridge,
            "save_phase2_risk_artifacts",
            lambda result, output_dir: {"phase2_risk_summary_json": str(output_dir / "phase2_risk_summary.json")},
        )

        def fake_simulate_phase2_execution(entries, **kwargs):
            captured["execution_entries"] = list(entries)
            captured["execution_kwargs"] = kwargs
            return SimpleNamespace(
                diagnostics={
                    "targets": 1,
                    "entry_intents": 1,
                    "child_intents": 3,
                    "fills": 1,
                    "bridge": "execution_engine.order_intents+tca",
                },
                tca_summary={"total_fills": 1, "breaches": 0},
            )

        monkeypatch.setattr(execution_bridge, "simulate_phase2_execution", fake_simulate_phase2_execution)
        monkeypatch.setattr(
            execution_bridge,
            "save_phase2_execution_artifacts",
            lambda result, output_dir: {"phase2_execution_summary_json": str(output_dir / "phase2_execution_summary.json")},
        )
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution"},
        )

        cli._run_backtest(args)

        assert cast(pd.DataFrame, captured["signals_df"]).equals(phase2_signals_df)
        assert cast(list[object], captured["execution_entries"]) == ["entry-a"]
        execution_kwargs = cast(dict[str, object], captured["execution_kwargs"])
        assert execution_kwargs["risk_run_id"] == "bt_phase2_20250101_20250102"
        report_payload = cast(dict[str, object], captured["report_payload"])
        assert report_payload["params"]["phase2_mode"] == "risk_execution"
        assert report_payload["params"]["phase2"]["execution_bridge"]["bridge"] == "execution_engine.order_intents+tca"
        assert report_payload["params"]["phase2"]["execution_tca"]["total_fills"] == 1
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["phase2_execution_summary_json"].endswith("phase2_execution_summary.json")

    def test_run_backtest_writes_compare_to_live_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, execution_bridge, report, resilience, risk_bridge, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection
        from execution_engine import db_io as execution_db_io
        from risk_management import db_io as risk_db_io

        captured: dict[str, object] = {}
        output_dir = tmp_path / "compare_live_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        research_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "score": [0.75],
            "score_source": ["final_score_sentiment"],
            "conviction": [0.75],
            "conviction_source": ["core.conviction:score_only"],
        })
        phase2_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "score": [0.75],
            "score_source": ["final_score_sentiment"],
            "conviction_score": [0.75],
            "conviction_source": ["core.conviction:score_only"],
            "predicted_proba": [None],
            "decision_reason_code": ["ok"],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                return FakePF()

        def fake_save_equity_curve_csv(pf, *, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "equity_curve.csv"
            path.write_text("trade_date,portfolio_value\n2025-01-02,100000\n", encoding="utf-8")
            return path

        def fake_save_trades_csv(pf, *, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "trades.csv"
            path.write_text("symbol,entry_date\nAAPL,2025-01-02\n", encoding="utf-8")
            return path

        def fake_save_equity_curve(pf, *, output_dir):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "equity_curve.png"
            path.write_text("png", encoding="utf-8")
            return path

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            output_dir.mkdir(parents=True, exist_ok=True)
            path = output_dir / "report.json"
            payload = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
            captured["report_payload"] = payload
            return path

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: research_signals_df.copy())
        monkeypatch.setattr(
            risk_bridge,
            "build_phase2_risk_result",
            lambda **kwargs: SimpleNamespace(
                entries=[
                    SimpleNamespace(
                        symbol="AAPL",
                        candidate_rank=1,
                        decision_rank=1,
                        score_used=0.75,
                        score_source="final_score_sentiment",
                        conviction_score=0.75,
                        predicted_proba=None,
                        decision="ACCEPTED",
                        decision_reason="OK",
                        decision_reason_code="ok",
                        target_weight=0.1,
                        approved_shares=10,
                        score_snapshot_date=date(2025, 1, 1),
                        prediction_asof_date=None,
                    )
                ],
                signals_df=phase2_signals_df.copy(),
                diagnostics={
                    "snapshot_dates": 1,
                    "entries_total": 1,
                    "entries_accepted": 1,
                    "signals_generated": 1,
                    "bridge": "risk_management.portfolio_builder",
                },
            ),
        )
        monkeypatch.setattr(
            risk_bridge,
            "save_phase2_risk_artifacts",
            lambda result, output_dir: {"phase2_risk_summary_json": str(output_dir / "phase2_risk_summary.json")},
        )
        monkeypatch.setattr(
            execution_bridge,
            "simulate_phase2_execution",
            lambda entries, **kwargs: SimpleNamespace(
                targets=[
                    SimpleNamespace(
                        symbol="AAPL",
                        target_shares=10,
                        target_weight=0.1,
                        conviction_score=0.75,
                        trade_date=date(2025, 1, 1),
                        risk_run_id="bt-phase2-live",
                    )
                ],
                diagnostics={
                    "risk_run_id": "bt-phase2-live",
                    "exec_run_id": "bt-exec-live",
                    "targets": 1,
                    "entry_intents": 1,
                    "child_intents": 3,
                    "fills": 1,
                    "bridge": "execution_engine.order_intents+tca",
                },
                tca_summary={"total_fills": 1, "breaches": 0},
            ),
        )
        monkeypatch.setattr(
            execution_bridge,
            "save_phase2_execution_artifacts",
            lambda result, output_dir: {"phase2_execution_summary_json": str(output_dir / "phase2_execution_summary.json")},
        )
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve_csv", fake_save_equity_curve_csv)
        monkeypatch.setattr(report, "save_trades_csv", fake_save_trades_csv)
        monkeypatch.setattr(report, "save_equity_curve", fake_save_equity_curve)
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        captured_portfolio_target_calls: list[dict[str, object]] = []
        monkeypatch.setattr(
            risk_db_io.RiskRepository,
            "load_risk_decisions_for_date",
            lambda self, trade_date, account_id=None: pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "decision": ["BUY"],
                    "approved_shares": [10],
                    "target_weight": [0.1],
                    "conviction_score": [0.75],
                    "run_id": ["live-risk-1"],
                }
            ),
        )
        monkeypatch.setattr(
            risk_db_io.RiskRepository,
            "load_risk_decisions_for_run_id",
            lambda self, run_id, account_id=None: pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "decision": ["BUY"],
                    "approved_shares": [10],
                    "target_weight": [0.1],
                    "conviction_score": [0.75],
                    "run_id": [run_id],
                }
            ),
        )
        monkeypatch.setattr(
            execution_db_io.ExecutionRepository,
            "load_portfolio_targets",
            lambda self, risk_run_id=None, trade_date=None, account_id=None: captured_portfolio_target_calls.append(
                {
                    "risk_run_id": risk_run_id,
                    "trade_date": trade_date,
                    "account_id": account_id,
                }
            )
            or [
                SimpleNamespace(
                    symbol="AAPL",
                    target_shares=10,
                    target_weight=0.1,
                    conviction_score=0.75,
                    risk_run_id="live-risk-1",
                )
            ],
        )
        monkeypatch.setattr(
            execution_db_io.ExecutionRepository,
            "load_execution_run_context_for_risk_run_id",
            lambda self, risk_run_id, account_id=None, trade_date=None: {
                "exec_run_id": "live-exec-1",
                "risk_run_id": risk_run_id,
                "trade_date": trade_date,
                "account_id": account_id or "default",
            },
        )
        monkeypatch.setattr(
            execution_db_io.ExecutionRepository,
            "load_execution_targets_snapshot",
            lambda self, exec_run_id: [
                SimpleNamespace(
                    symbol="AAPL",
                    target_shares=8,
                    target_weight=0.08,
                    conviction_score=0.75,
                    risk_run_id="live-exec-1",
                )
            ],
        )
        monkeypatch.setattr(
            execution_db_io.ExecutionRepository,
            "load_execution_fills_for_run",
            lambda self, exec_run_id, account_id=None: pd.DataFrame(
                {
                    "symbol": ["AAPL"],
                    "side": ["buy"],
                    "filled_qty": [10.0],
                    "avg_fill_price": [100.0],
                    "intent_role": ["entry"],
                    "fill_timestamp": pd.to_datetime(["2025-01-01 14:30:00"]),
                    "run_id": [exec_run_id],
                }
            ),
        )
        monkeypatch.setattr(
            execution_db_io.ExecutionRepository,
            "load_execution_position_lots_for_open_run",
            lambda self, open_exec_run_id, account_id=None: pd.DataFrame(),
        )

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=False,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution"},
        )

        cli._run_backtest(args)

        report_payload = cast(dict[str, object], captured["report_payload"])
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["compare_to_live_summary_json"].endswith("compare_to_live_summary.json")
        assert artifacts["compare_to_live_sessions_csv"].endswith("compare_to_live_sessions.csv")
        assert artifacts["compare_to_live_summary_md"].endswith("compare_to_live_summary.md")
        compare_payload = json.loads((output_dir / "compare_to_live_summary.json").read_text(encoding="utf-8"))
        assert compare_payload["session_count"] == 1
        assert compare_payload["live_session_count"] == 1
        assert compare_payload["sessions"][0]["candidate_compare"]["status"] == "aligned"
        assert compare_payload["sessions"][0]["risk_compare"]["status"] == "aligned"
        assert compare_payload["sessions"][0]["portfolio_compare"]["status"] == "aligned"
        assert compare_payload["sessions"][0]["execution_compare"]["divergence_kind_counts"] == {"qty_mismatch": 1}
        assert compare_payload["sessions"][0]["matching_context"]["risk_decisions_basis"] == "risk_run_id"
        assert compare_payload["sessions"][0]["matching_context"]["portfolio_targets_basis"] == "risk_run_id"
        assert captured_portfolio_target_calls == [
            {
                "risk_run_id": "live-risk-1",
                "trade_date": date(2025, 1, 1),
                "account_id": "default",
            }
        ]
        assert (output_dir / "compare_to_live_sessions.csv").exists()
        assert (output_dir / "compare_to_live_summary.md").exists()

    def test_run_backtest_phase3_execution_replay_uses_replay_signals_and_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, execution_replay, report, resilience, risk_bridge, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        output_dir = tmp_path / "phase3_exec_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        phase3_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "approved_shares": [12],
            "filled_qty": [12.0],
            "fill_price": [101.0],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                captured["bt_config"] = self.cfg
                return FakePF()

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            captured["report_payload"] = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            return output_dir / "report.json"

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: pytest.fail("replay_signals ne doit pas être utilisé en phase3_mode=execution_replay"))
        monkeypatch.setattr(
            risk_bridge,
            "build_phase2_risk_result",
            lambda **kwargs: SimpleNamespace(
                entries=["entry-a"],
                signals_df=pd.DataFrame({"symbol": ["AAPL"]}),
                diagnostics={
                    "snapshot_dates": 1,
                    "entries_total": 1,
                    "entries_accepted": 1,
                    "signals_generated": 1,
                    "bridge": "risk_management.portfolio_builder",
                },
            ),
        )
        monkeypatch.setattr(
            risk_bridge,
            "save_phase2_risk_artifacts",
            lambda result, output_dir: {"phase2_risk_summary_json": str(output_dir / "phase2_risk_summary.json")},
        )
        monkeypatch.setattr(
            execution_replay,
            "simulate_phase3_execution_replay",
            lambda entries, **kwargs: SimpleNamespace(
                execution_result=SimpleNamespace(
                    diagnostics={
                        "targets": 1,
                        "entry_intents": 1,
                        "child_intents": 3,
                        "fills": 1,
                        "bridge": "execution_engine.order_intents+tca",
                    },
                    tca_summary={"total_filled": 1, "slippage_alerts": 0},
                ),
                signals_df=phase3_signals_df.copy(),
                diagnostics={
                    "scheduled_entries": 1,
                    "signals_generated": 1,
                    "skipped_no_next_session": 0,
                    "bridge": "execution_engine.order_intents+tca+execution_replay",
                },
            ),
        )
        monkeypatch.setattr(
            execution_replay,
            "save_phase3_execution_replay_artifacts",
            lambda result, output_dir: {"phase3_execution_replay_summary_json": str(output_dir / "phase3_execution_replay_summary.json")},
        )
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution", "phase3_mode": "execution_replay"},
        )

        cli._run_backtest(args)

        assert cast(pd.DataFrame, captured["signals_df"]).equals(phase3_signals_df)
        bt_config = captured["bt_config"]
        assert bt_config.execution_replay_mode == "execution_replay"
        report_payload = cast(dict[str, object], captured["report_payload"])
        assert report_payload["params"]["phase3_mode"] == "execution_replay"
        assert report_payload["params"]["phase3"]["enabled"] is True
        assert report_payload["params"]["phase3"]["execution_replay"]["bridge"] == "execution_engine.order_intents+tca+execution_replay"
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["phase3_execution_replay_summary_json"].endswith("phase3_execution_replay_summary.json")

    def test_run_backtest_phase4_protection_replay_uses_enriched_signals_and_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, execution_lifecycle_replay, execution_replay, report, resilience, risk_bridge, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        output_dir = tmp_path / "phase4_exec_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        phase4_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "approved_shares": [12],
            "filled_qty": [12.0],
            "replay_take_profit_price": [109.0],
            "replay_initial_stop_price": [97.0],
            "replay_trailing_stop_pct": [0.05],
            "replay_trailing_activation_price": [106.0],
            "protection_replay_mode": ["protection_replay"],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                captured["bt_config"] = self.cfg
                return FakePF()

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            captured["report_payload"] = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            return output_dir / "report.json"

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: pytest.fail("replay_signals ne doit pas être utilisé en phase4_mode=protection_replay"))
        monkeypatch.setattr(
            risk_bridge,
            "build_phase2_risk_result",
            lambda **kwargs: SimpleNamespace(
                entries=["entry-a"],
                signals_df=pd.DataFrame({"symbol": ["AAPL"]}),
                diagnostics={
                    "snapshot_dates": 1,
                    "entries_total": 1,
                    "entries_accepted": 1,
                    "signals_generated": 1,
                    "bridge": "risk_management.portfolio_builder",
                },
            ),
        )
        monkeypatch.setattr(risk_bridge, "save_phase2_risk_artifacts", lambda result, output_dir: {"phase2_risk_summary_json": str(output_dir / "phase2_risk_summary.json")})
        monkeypatch.setattr(
            execution_replay,
            "simulate_phase3_execution_replay",
            lambda entries, **kwargs: SimpleNamespace(
                execution_result=SimpleNamespace(
                    diagnostics={"targets": 1, "entry_intents": 1, "child_intents": 3, "fills": 1, "bridge": "execution_engine.order_intents+tca"},
                    tca_summary={"total_filled": 1, "slippage_alerts": 0},
                ),
                signals_df=pd.DataFrame({"symbol": ["AAPL"]}),
                diagnostics={"scheduled_entries": 1, "signals_generated": 1, "bridge": "execution_engine.order_intents+tca+execution_replay"},
            ),
        )
        monkeypatch.setattr(execution_replay, "save_phase3_execution_replay_artifacts", lambda result, output_dir: {"phase3_execution_replay_summary_json": str(output_dir / "phase3_execution_replay_summary.json")})
        monkeypatch.setattr(
            execution_lifecycle_replay,
            "build_phase4_protection_replay",
            lambda result, **kwargs: SimpleNamespace(
                signals_df=phase4_signals_df.copy(),
                diagnostics={"protections_replayed": 1, "trailing_stop_protections": 1, "initial_stop_protections": 1, "bridge": "execution_engine.child_intents+protection_replay"},
            ),
        )
        monkeypatch.setattr(execution_lifecycle_replay, "save_phase4_protection_replay_artifacts", lambda result, output_dir: {"phase4_protection_replay_summary_json": str(output_dir / "phase4_protection_replay_summary.json")})
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution", "phase3_mode": "execution_replay", "phase4_mode": "protection_replay"},
        )

        cli._run_backtest(args)

        assert cast(pd.DataFrame, captured["signals_df"]).equals(phase4_signals_df)
        bt_config = captured["bt_config"]
        assert bt_config.protection_replay_mode == "protection_replay"
        report_payload = cast(dict[str, object], captured["report_payload"])
        assert report_payload["params"]["phase4_mode"] == "protection_replay"
        assert report_payload["params"]["phase4"]["enabled"] is True
        assert report_payload["params"]["phase4"]["protection_replay"]["bridge"] == "execution_engine.child_intents+protection_replay"
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["phase4_protection_replay_summary_json"].endswith("phase4_protection_replay_summary.json")

    def test_run_backtest_phase5_watcher_replay_uses_lifecycle_signals_and_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, execution_lifecycle_replay, execution_replay, protection_watcher_replay, report, resilience, risk_bridge, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        output_dir = tmp_path / "phase5_exec_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        phase5_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "approved_shares": [12],
            "filled_qty": [12.0],
            "replay_take_profit_price": [109.0],
            "replay_initial_stop_price": [97.0],
            "replay_trailing_stop_pct": [0.05],
            "replay_trailing_activation_price": [106.0],
            "watcher_transition_state": ["transitioned"],
            "watcher_trigger_date": pd.to_datetime(["2025-01-02"]),
            "watcher_transition_effective_date": pd.to_datetime(["2025-01-03"]),
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                captured["bt_config"] = self.cfg
                return FakePF()

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            captured["report_payload"] = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            return output_dir / "report.json"

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: pytest.fail("replay_signals ne doit pas être utilisé en phase5_mode=watcher_replay"))
        monkeypatch.setattr(risk_bridge, "build_phase2_risk_result", lambda **kwargs: SimpleNamespace(entries=["entry-a"], signals_df=pd.DataFrame({"symbol": ["AAPL"]}), diagnostics={"snapshot_dates": 1, "entries_total": 1, "entries_accepted": 1, "signals_generated": 1, "bridge": "risk_management.portfolio_builder"}))
        monkeypatch.setattr(risk_bridge, "save_phase2_risk_artifacts", lambda result, output_dir: {"phase2_risk_summary_json": str(output_dir / "phase2_risk_summary.json")})
        monkeypatch.setattr(execution_replay, "simulate_phase3_execution_replay", lambda entries, **kwargs: SimpleNamespace(execution_result=SimpleNamespace(diagnostics={"targets": 1, "entry_intents": 1, "child_intents": 3, "fills": 1, "bridge": "execution_engine.order_intents+tca"}, tca_summary={"total_filled": 1}), signals_df=pd.DataFrame({"symbol": ["AAPL"]}), diagnostics={"scheduled_entries": 1, "signals_generated": 1, "bridge": "execution_engine.order_intents+tca+execution_replay"}))
        monkeypatch.setattr(execution_replay, "save_phase3_execution_replay_artifacts", lambda result, output_dir: {"phase3_execution_replay_summary_json": str(output_dir / "phase3_execution_replay_summary.json")})
        monkeypatch.setattr(execution_lifecycle_replay, "build_phase4_protection_replay", lambda result, **kwargs: SimpleNamespace(signals_df=pd.DataFrame({"symbol": ["AAPL"]}), diagnostics={"protections_replayed": 1, "bridge": "execution_engine.child_intents+protection_replay"}))
        monkeypatch.setattr(execution_lifecycle_replay, "save_phase4_protection_replay_artifacts", lambda result, output_dir: {"phase4_protection_replay_summary_json": str(output_dir / "phase4_protection_replay_summary.json")})
        monkeypatch.setattr(protection_watcher_replay, "build_phase5_watcher_replay", lambda result, **kwargs: SimpleNamespace(signals_df=phase5_signals_df.copy(), diagnostics={"transitioned_items": 1, "pending_items": 0, "failed_items": 0, "bridge": "execution_engine.protection_watcher+watcher_replay"}))
        monkeypatch.setattr(protection_watcher_replay, "save_phase5_watcher_replay_artifacts", lambda result, output_dir: {"phase5_watcher_replay_summary_json": str(output_dir / "phase5_watcher_replay_summary.json")})
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution", "phase3_mode": "execution_replay", "phase4_mode": "protection_replay", "phase5_mode": "watcher_replay"},
        )

        cli._run_backtest(args)

        assert cast(pd.DataFrame, captured["signals_df"]).equals(phase5_signals_df)
        bt_config = captured["bt_config"]
        assert bt_config.watcher_replay_mode == "watcher_replay"
        report_payload = cast(dict[str, object], captured["report_payload"])
        assert report_payload["params"]["phase5_mode"] == "watcher_replay"
        assert report_payload["params"]["phase5"]["enabled"] is True
        assert report_payload["params"]["phase5"]["watcher_replay"]["bridge"] == "execution_engine.protection_watcher+watcher_replay"
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["phase5_watcher_replay_summary_json"].endswith("phase5_watcher_replay_summary.json")

    def test_run_backtest_phase7_exit_lifecycle_replay_uses_terminal_exit_signals_and_artifacts(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, execution_lifecycle_replay, execution_replay, exit_lifecycle_replay, protection_watcher_replay, report, resilience, risk_bridge, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        output_dir = tmp_path / "phase7_exec_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        phase7_signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "execution_date": pd.to_datetime(["2025-01-02"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "approved_shares": [12],
            "filled_qty": [12.0],
            "replay_exit_date": pd.to_datetime(["2025-01-03"]),
            "replay_exit_price": [100.7],
            "replay_exit_reason": ["trailing_stop"],
            "replay_exit_intent_role": ["trailing_stop"],
            "replay_oco_sibling_canceled": [True],
            "exit_lifecycle_replay_mode": ["exit_lifecycle_replay"],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                captured["bt_config"] = self.cfg
                return FakePF()

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            captured["report_payload"] = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            return output_dir / "report.json"

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: pytest.fail("replay_signals ne doit pas être utilisé en phase7_mode=exit_lifecycle_replay"))
        monkeypatch.setattr(risk_bridge, "build_phase2_risk_result", lambda **kwargs: SimpleNamespace(entries=["entry-a"], signals_df=pd.DataFrame({"symbol": ["AAPL"]}), diagnostics={"snapshot_dates": 1, "entries_total": 1, "entries_accepted": 1, "signals_generated": 1, "bridge": "risk_management.portfolio_builder"}))
        monkeypatch.setattr(risk_bridge, "save_phase2_risk_artifacts", lambda result, output_dir: {"phase2_risk_summary_json": str(output_dir / "phase2_risk_summary.json")})
        monkeypatch.setattr(execution_replay, "simulate_phase3_execution_replay", lambda entries, **kwargs: SimpleNamespace(execution_result=SimpleNamespace(diagnostics={"targets": 1, "entry_intents": 1, "child_intents": 3, "fills": 1, "bridge": "execution_engine.order_intents+tca"}, tca_summary={"total_filled": 1}), signals_df=pd.DataFrame({"symbol": ["AAPL"]}), diagnostics={"scheduled_entries": 1, "signals_generated": 1, "bridge": "execution_engine.order_intents+tca+execution_replay"}))
        monkeypatch.setattr(execution_replay, "save_phase3_execution_replay_artifacts", lambda result, output_dir: {"phase3_execution_replay_summary_json": str(output_dir / "phase3_execution_replay_summary.json")})
        monkeypatch.setattr(execution_lifecycle_replay, "build_phase4_protection_replay", lambda result, **kwargs: SimpleNamespace(signals_df=pd.DataFrame({"symbol": ["AAPL"]}), diagnostics={"protections_replayed": 1, "bridge": "execution_engine.child_intents+protection_replay"}))
        monkeypatch.setattr(execution_lifecycle_replay, "save_phase4_protection_replay_artifacts", lambda result, output_dir: {"phase4_protection_replay_summary_json": str(output_dir / "phase4_protection_replay_summary.json")})
        monkeypatch.setattr(protection_watcher_replay, "build_phase5_watcher_replay", lambda result, **kwargs: SimpleNamespace(signals_df=pd.DataFrame({"symbol": ["AAPL"]}), diagnostics={"transitioned_items": 1, "pending_items": 0, "failed_items": 0, "bridge": "execution_engine.protection_watcher+watcher_replay"}))
        monkeypatch.setattr(protection_watcher_replay, "save_phase5_watcher_replay_artifacts", lambda result, output_dir: {"phase5_watcher_replay_summary_json": str(output_dir / "phase5_watcher_replay_summary.json")})
        monkeypatch.setattr(exit_lifecycle_replay, "build_phase7_exit_lifecycle_replay", lambda result, **kwargs: SimpleNamespace(signals_df=phase7_signals_df.copy(), diagnostics={"exit_rows": 1, "events_generated": 2, "filled_take_profit": 0, "filled_initial_stop": 0, "filled_trailing_stop": 1, "oco_cancels": 1, "bridge": "execution_engine.oco_manager+exit_lifecycle_replay"}))
        monkeypatch.setattr(exit_lifecycle_replay, "save_phase7_exit_lifecycle_replay_artifacts", lambda result, output_dir: {"phase7_exit_lifecycle_replay_summary_json": str(output_dir / "phase7_exit_lifecycle_replay_summary.json")})
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            **{**self._CLI_NEUTRAL_DEFAULTS, "phase2_mode": "risk_execution", "phase3_mode": "execution_replay", "phase4_mode": "protection_replay", "phase5_mode": "watcher_replay", "phase7_mode": "exit_lifecycle_replay"},
        )

        cli._run_backtest(args)

        assert cast(pd.DataFrame, captured["signals_df"]).equals(phase7_signals_df)
        bt_config = captured["bt_config"]
        assert bt_config.exit_lifecycle_replay_mode == "exit_lifecycle_replay"
        report_payload = cast(dict[str, object], captured["report_payload"])
        assert report_payload["params"]["phase7_mode"] == "exit_lifecycle_replay"
        assert report_payload["params"]["phase7"]["enabled"] is True
        assert report_payload["params"]["phase7"]["mode"] == "exit_lifecycle_replay"
        assert report_payload["params"]["phase7"]["exit_lifecycle_replay"]["bridge"] == "execution_engine.oco_manager+exit_lifecycle_replay"
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["phase7_exit_lifecycle_replay_summary_json"].endswith("phase7_exit_lifecycle_replay_summary.json")

    def test_run_backtest_saves_fidelity_baseline_artifacts_when_requested(self, monkeypatch, tmp_path):
        import argparse
        import backtesting.cli as cli
        from backtesting import data_loader, fidelity, report, resilience, signal_replay, simulator
        from backtesting.fidelity import ScoreLoadDiagnostics, ScoreLoadResult
        from database import connection

        captured: dict[str, object] = {}
        output_dir = tmp_path / "baseline_out"
        idx = pd.to_datetime(["2025-01-01", "2025-01-02"])
        ohlcv_df = pd.DataFrame({
            "symbol": ["AAPL", "AAPL"],
            "trade_date": idx,
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.5, 101.5],
            "volume": [1000, 1100],
        })
        scores_df = pd.DataFrame({
            "symbol": ["AAPL"],
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "final_score": [0.7],
            "final_score_sentiment": [0.75],
            "sector": ["Tech"],
            "is_candidate": [1],
        })
        signals_df = pd.DataFrame({
            "trade_date": pd.to_datetime(["2025-01-01"]),
            "symbol": ["AAPL"],
            "selected": [True],
            "rank": [1.0],
            "score_source": ["final_score_sentiment"],
        })

        class FakePF:
            pass

        class FakeReport:
            def print_summary(self) -> None:
                return None

        class FakeBacktestEngine:
            def __init__(self, cfg):
                self.cfg = cfg

            def run(self, **kwargs):
                captured["signals_df"] = kwargs["signals_df"].copy()
                return FakePF()

        def fake_save_report_json(report_obj, *, output_dir, artifacts, params, diagnostics, **kwargs):
            captured["report_payload"] = {
                "artifacts": artifacts,
                "params": params,
                "diagnostics": diagnostics,
                "fidelity": kwargs.get("fidelity", {}),
            }
            return output_dir / "report.json"

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
        monkeypatch.setattr(data_loader, "load_ohlcv", lambda engine, start, end: ohlcv_df.copy())
        monkeypatch.setattr(data_loader, "load_scores", lambda engine, start, end, capital_preset_key=None, **kwargs: ScoreLoadResult(
            frame=scores_df.copy(),
            diagnostics=ScoreLoadDiagnostics(
                source_table="stock_scores_history",
                strict_pit_requested=bool(kwargs.get("strict_pit", False)),
                history_table_exists=True,
                history_rows_found=len(scores_df),
                capital_preset_key=capital_preset_key,
            ),
        ))
        monkeypatch.setattr(data_loader, "load_predictions", lambda engine, start, end: pd.DataFrame())
        monkeypatch.setattr(data_loader, "pivot_ohlcv", lambda df: {
            "open": df.pivot_table(index="trade_date", columns="symbol", values="open"),
            "close": df.pivot_table(index="trade_date", columns="symbol", values="close"),
            "high": df.pivot_table(index="trade_date", columns="symbol", values="high"),
            "low": df.pivot_table(index="trade_date", columns="symbol", values="low"),
        })
        monkeypatch.setattr(resilience, "prepare_scores_for_sentiment_mode", lambda *args, **kwargs: scores_df.copy())
        monkeypatch.setattr(resilience, "prepare_predictions_for_ml_mode", lambda *args, **kwargs: pd.DataFrame())
        monkeypatch.setattr(signal_replay, "replay_signals", lambda *args, **kwargs: signals_df.copy())
        monkeypatch.setattr(simulator, "BacktestEngine", FakeBacktestEngine)
        monkeypatch.setattr(report, "extract_diagnostics", lambda pf: {"selected_count": 1})
        monkeypatch.setattr(report, "generate_report", lambda pf, equity, **kwargs: FakeReport())
        monkeypatch.setattr(report, "save_equity_curve", lambda *args, **kwargs: tmp_path / "eq.png")
        monkeypatch.setattr(report, "save_equity_curve_csv", lambda *args, **kwargs: tmp_path / "eq.csv")
        monkeypatch.setattr(report, "save_report_json", fake_save_report_json)
        monkeypatch.setattr(report, "save_trades_csv", lambda *args, **kwargs: tmp_path / "trades.csv")
        monkeypatch.setattr(fidelity, "build_fidelity_baseline_snapshot", lambda **kwargs: {
            "snapshot_version": 1,
            "baseline_id": kwargs.get("baseline_id"),
            "requested_window": {"start_date": "2025-01-01", "end_date": "2025-01-02"},
            "phase_modes": {"phase7_mode": "off"},
            "metrics": {"compare_live_fidelity_score": 0.0},
        })
        monkeypatch.setattr(fidelity, "save_fidelity_baseline_snapshot", lambda snapshot, output_dir: output_dir / "fidelity_baseline_snapshot.json")
        monkeypatch.setattr(fidelity, "build_fidelity_baseline_comparison", lambda snapshot, *, catalog_path, baseline_id=None: {
            "comparison_version": 1,
            "status": "aligned",
            "baseline_id": baseline_id,
            "checked_count": 2,
            "failed_count": 0,
            "checks": [],
        })
        monkeypatch.setattr(fidelity, "save_fidelity_baseline_comparison", lambda comparison, output_dir: {
            "fidelity_baseline_comparison_json": output_dir / "fidelity_baseline_comparison.json",
            "fidelity_baseline_comparison_checks_csv": output_dir / "fidelity_baseline_comparison_checks.csv",
        })

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-01-02",
            equity=100_000.0,
            tp=0.08,
            ts=0.05,
            max_positions=5,
            fees=0.001,
            account_type="margin",
            pdt_rule="auto",
            swing_only=False,
            sentiment_lookback=365,
            no_save=True,
            ml_mode="auto",
            sentiment_mode="auto",
            artifacts_dir="artifacts/models",
            output_dir=str(output_dir),
            score_column="auto",
            walk_forward_artifacts_dir=None,
            engine_mode="research",
            fidelity_baseline_id="pipeline_live_like_smoke",
            fidelity_baseline_catalog="config/fidelity_baseline_catalog.json",
            **self._CLI_NEUTRAL_DEFAULTS,
        )

        cli._run_backtest(args)

        report_payload = cast(dict[str, object], captured["report_payload"])
        artifacts = cast(dict[str, str], report_payload["artifacts"])
        assert artifacts["fidelity_baseline_snapshot_json"].endswith("fidelity_baseline_snapshot.json")
        assert artifacts["fidelity_baseline_comparison_json"].endswith("fidelity_baseline_comparison.json")
        assert artifacts["fidelity_baseline_comparison_checks_csv"].endswith("fidelity_baseline_comparison_checks.csv")
        assert report_payload["params"]["fidelity_baseline_id"] == "pipeline_live_like_smoke"
        assert report_payload["params"]["fidelity_baseline_catalog"] == "config/fidelity_baseline_catalog.json"

    def test_parse_backfill_scores_history_command(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "backfill-scores-history",
            "--start", "2025-01-01",
            "--capital", "2000",
            "--capital-preset-key", "capital_0_5000",
            "--limit-days", "5",
            "--chunk-size", "250",
            "--selection-size", "50",
            "--overwrite-existing",
        ])
        assert args.command == "backfill-scores-history"
        assert args.start == "2025-01-01"
        assert args.capital == 2000
        assert args.capital_preset_key == "capital_0_5000"
        assert args.limit_days == 5
        assert args.chunk_size == 250
        assert args.selection_size == 50
        assert args.overwrite_existing is True

    def test_parse_backfill_scores_history_command_uses_optimized_defaults(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "backfill-scores-history",
            "--start", "2025-01-01",
        ])

        assert args.command == "backfill-scores-history"
        assert args.chunk_size == 1000
        assert args.screener_workers == 4

    def test_run_backfill_scores_history_prefers_explicit_selection_size_without_duplicate_kwarg(self, monkeypatch):
        import argparse
        import backtesting.cli._impl as cli
        from screener.models import ScreenerConfig

        captured: dict[str, object] = {}

        class FakeBackfillService:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def backfill(self, *, start_date, end_date, overwrite_existing, limit_days):
                captured["backfill_call"] = {
                    "start_date": start_date,
                    "end_date": end_date,
                    "overwrite_existing": overwrite_existing,
                    "limit_days": limit_days,
                }
                return SimpleNamespace(
                    start_date=start_date,
                    end_date=end_date,
                    trading_days_processed=1,
                    trading_days_requested=1,
                    trading_days_skipped_existing=0,
                    rows_inserted=50,
                )

        class FakeAlphaScannerConfig:
            @classmethod
            def strict_swing_cash(cls, **kwargs):
                captured["scanner_kwargs"] = dict(kwargs)
                return {"scanner_kwargs": dict(kwargs)}

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(cli, "resolve_effective_capital_preset", lambda **kwargs: (SimpleNamespace(key="capital_50001_100000"), "explicit_key"))
        monkeypatch.setattr(cli, "resolve_capital_preset_for_equity", lambda equity: SimpleNamespace(key="capital_25001_50000"))
        monkeypatch.setattr(cli, "build_screener_config_kwargs_from_preset", lambda preset: {"liquidity_threshold_usd": 1_000_000.0})
        monkeypatch.setattr(
            cli,
            "build_selector_config_kwargs_from_preset",
            lambda preset: {"selection_size": 25, "sector_cap_ratio": 0.28, "min_close": 10.0},
        )
        monkeypatch.setattr(cli, "capital_preset_fingerprint", lambda preset: "fp-test")

        from backtesting import backfill_scores_history
        from selector import alpha_scanner

        monkeypatch.setattr(backfill_scores_history, "BackfillScoresHistoryService", FakeBackfillService)
        monkeypatch.setattr(alpha_scanner, "AlphaScannerConfig", FakeAlphaScannerConfig)
        monkeypatch.setattr(cli.sys, "argv", ["python", "backfill-scores-history", "--selection-size", "50"])

        args = argparse.Namespace(
            start="2025-01-01",
            end="2026-03-31",
            capital=50_001.0,
            capital_preset_key="capital_50001_100000",
            overwrite_existing=False,
            limit_days=None,
            chunk_size=500,
            selection_size=50,
            screener_workers=None,
        )

        cli._run_backfill_scores_history(args)

        screener_config = cast(ScreenerConfig, captured["screener_config"])
        assert screener_config.min_close_price == 10.0
        assert screener_config.liquidity_threshold_usd == 1_000_000.0
        assert screener_config.chunk_size == 500

        scanner_kwargs = cast(dict[str, object], captured["scanner_kwargs"])
        assert scanner_kwargs["selection_size"] == 50
        assert scanner_kwargs["chunk_size"] == 500
        assert scanner_kwargs["sector_cap_ratio"] == 0.28
        assert set(scanner_kwargs.keys()) == {"chunk_size", "selection_size", "sector_cap_ratio", "min_close"}

    def test_parse_run_command_accepts_capital_preset_key(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "run",
            "--start", "2025-01-01",
            "--capital-preset-key", "capital_0_5000",
        ])

        assert args.command == "run"
        assert args.capital_preset_key == "capital_0_5000"

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

    def test_parse_diagnose_screener_command_uses_strict_liquidity_defaults(self):
        from backtesting.cli import _build_parser

        parser = _build_parser()
        args = parser.parse_args([
            "diagnose-screener",
            "--start", "2025-01-01",
        ])

        assert args.liquidity_threshold_values == "20000000,30000000,40000000"

    def test_run_screener_diagnostics_uses_strict_swing_cash_baseline(self, monkeypatch):
        import argparse
        import backtesting.cli._impl as cli
        import backtesting.screener_diagnostics as diagnostics
        from screener.models import ScreenerConfig

        captured: dict[str, object] = {}

        class FakeDiagnosticsService:
            def __init__(self, **kwargs):
                captured.update(kwargs)

            def analyze_period(self, *, start_date, end_date, scenarios, limit_days):
                return SimpleNamespace(
                    summary_metrics=pd.DataFrame([{"scenario_name": "baseline", "overall_score": 1.0}]),
                    daily_metrics=pd.DataFrame([{"scenario_name": "baseline"}]),
                    summary_metrics_by_regime=pd.DataFrame([{"scenario_name": "baseline", "market_regime": "bull"}]),
                    baseline_name="baseline",
                    trading_dates=[date(2025, 1, 2)],
                )

        monkeypatch.setattr(cli, "_safe_print", lambda *args, **kwargs: None)
        monkeypatch.setattr(diagnostics, "ScreenerDiagnosticsService", FakeDiagnosticsService)
        monkeypatch.setattr(diagnostics, "build_screener_grid_scenarios", lambda *args, **kwargs: [{"name": "baseline"}])
        monkeypatch.setattr(diagnostics, "build_screener_oat_scenarios", lambda *args, **kwargs: [{"name": "baseline"}])
        monkeypatch.setattr(
            diagnostics,
            "recommend_screener_scenarios",
            lambda *args, **kwargs: (pd.DataFrame([{"scenario_name": "baseline", "overall_score": 1.0}]), {"status": "skip"}),
        )
        monkeypatch.setattr(
            diagnostics,
            "recommend_screener_scenarios_by_regime",
            lambda *args, **kwargs: (
                pd.DataFrame([{"scenario_name": "baseline", "market_regime": "bull"}]),
                {"status": "skip"},
                pd.DataFrame([{"scenario_name": "baseline", "cross_regime_overall_score": 1.0}]),
                {"status": "skip"},
            ),
        )
        monkeypatch.setattr(
            diagnostics,
            "recommend_screener_scenarios_by_objective",
            lambda *args, **kwargs: (pd.DataFrame([{"scenario_name": "baseline", "objective": "robust"}]), {"status": "skip", "objectives": {}}),
        )
        monkeypatch.setattr(
            diagnostics,
            "export_screener_diagnostics",
            lambda *args, **kwargs: {
                "summary_metrics": "summary_metrics.csv",
                "daily_metrics": "daily_metrics.csv",
                "scenarios": "scenarios.csv",
                "metadata": "metadata.json",
            },
        )
        monkeypatch.setattr(
            diagnostics,
            "export_screener_recommendations",
            lambda *args, **kwargs: {
                "scenario_recommendations": "scenario_recommendations.csv",
                "recommendation_summary": "recommendation_summary.json",
            },
        )
        monkeypatch.setattr(
            diagnostics,
            "export_screener_regime_recommendations",
            lambda *args, **kwargs: {
                "scenario_recommendations_by_regime": "scenario_recommendations_by_regime.csv",
                "cross_regime_recommendations": "cross_regime_recommendations.csv",
                "cross_regime_recommendation_summary": "cross_regime_recommendation_summary.json",
            },
        )
        monkeypatch.setattr(
            diagnostics,
            "export_screener_objective_recommendations",
            lambda *args, **kwargs: {
                "scenario_recommendations_by_objective": "scenario_recommendations_by_objective.csv",
                "recommendation_summary_by_objective": "recommendation_summary_by_objective.json",
            },
        )
        monkeypatch.setattr(diagnostics, "validate_recommendations_holdout", lambda *args, **kwargs: ({}, pd.DataFrame()))
        monkeypatch.setattr(diagnostics, "export_holdout_validation", lambda *args, **kwargs: {})

        args = argparse.Namespace(
            start="2025-01-01",
            end="2025-03-31",
            rs_values="100,102,105",
            range_lookback_values="252,504,756",
            historical_range_score_values="65,70,75",
            liquidity_threshold_values="20000000,30000000,40000000",
            mode="oat",
            limit_days=None,
            chunk_size=500,
            selection_size=100,
            max_positions=20,
            screener_workers=None,
            max_scenarios=64,
            output_dir="artifacts/screener_diagnostics",
            holdout_train_end=None,
            holdout_min_regime_days=20,
            holdout_top_k=3,
        )

        cli._run_screener_diagnostics(args)

        base_screener_config = cast(ScreenerConfig, captured["base_screener_config"])
        assert base_screener_config.min_close_price == 10.0
        assert base_screener_config.liquidity_threshold_usd == 30_000_000.0
        assert base_screener_config.chunk_size == 500

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
        older_file.write_text(json.dumps({"sentiment_weight": 0.10, "macro_weight": 0.10, "quant_weight": 0.35}), encoding="utf-8")
        newer_file.write_text(json.dumps({"sentiment_weight": 0.20, "macro_weight": 0.10, "quant_weight": 0.35}), encoding="utf-8")
        os.utime(older_file, (1, 1))
        os.utime(newer_file, (2, 2))

        weights = resolve_latest_walk_forward_weights([tmp_path])

        assert weights is not None
        assert weights.sentiment_weight == 0.2
        assert weights.quant_weight == pytest.approx(0.35)


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
                BacktestRunOptions(start="2024-01-01", end="2025-04-14"),
            )
        except RuntimeError as exc:
            assert "déjà en cours" in str(exc)
            assert "run-active-123" in str(exc)
        else:
            raise AssertionError("Le registre aurait dû bloquer un second run du même type.")






