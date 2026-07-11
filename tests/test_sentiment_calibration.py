from __future__ import annotations

from datetime import date
from typing import Any, cast

import pandas as pd
import pytest

from backtesting.sentiment_calibration import (
    SentimentCalibrationScenario,
    SentimentWeightCalibrator,
)


def test_build_forward_return_frame_computes_forward_returns() -> None:
    raw = pd.DataFrame(
        {
            "snapshot_date": pd.to_datetime(["2026-01-02"] * 4),
            "symbol": ["AAPL"] * 4,
            "sector": ["Tech"] * 4,
            "final_score": [0.8] * 4,
            "sentiment_net_agg": [0.2] * 4,
            "sector_impact_agg": [0.1] * 4,
            "final_score_sentiment": [0.82] * 4,
            "selection_rank": [1] * 4,
            "short_score": [None] * 4,
            "bar_date": pd.to_datetime(["2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"]),
            "close_price": [100.0, 110.0, 120.0, 130.0],
        }
    )

    result = SentimentWeightCalibrator.build_forward_return_frame(raw, horizons=(1, 2))

    assert len(result) == 1
    assert result.iloc[0]["forward_return_1d"] == pytest.approx(0.10, rel=1e-9)
    assert result.iloc[0]["forward_return_2d"] == pytest.approx(0.20, rel=1e-9)


def test_evaluate_scenarios_prefers_sentiment_when_forward_returns_follow_signal() -> None:
    calibrator = SentimentWeightCalibrator.__new__(SentimentWeightCalibrator)
    calibrator.engine = None
    dataset = pd.DataFrame(
        {
            "snapshot_date": pd.to_datetime(["2026-01-02"] * 3 + ["2026-01-03"] * 3),
            "symbol": ["AAA", "BBB", "CCC", "AAA", "BBB", "CCC"],
            "sector": ["Tech"] * 6,
            "final_score": [0.5, 0.5, 0.5, 0.5, 0.5, 0.5],
            "sentiment_net_agg": [1.0, 0.0, -1.0, 1.0, 0.0, -1.0],
            "sector_impact_agg": [0.0] * 6,
            "final_score_sentiment": [None] * 6,
            "selection_rank": [1] * 6,
            "forward_return_5d": [0.08, 0.01, -0.04, 0.07, 0.00, -0.03],
        }
    )
    scenarios = [
        SentimentCalibrationScenario(sentiment_weight=0.0, macro_weight=0.0, quant_weight=1.0),
        SentimentCalibrationScenario(sentiment_weight=0.3, macro_weight=0.0, quant_weight=0.7),
    ]

    result_df = calibrator.evaluate_scenarios(dataset, scenarios, horizons=(5,), top_n=1)

    assert result_df.iloc[0]["scenario_name"] == "sent_0.30_macro_0.00_quant_0.70"
    assert result_df.iloc[0]["overall_score"] > result_df.iloc[1]["overall_score"]


def test_calibrate_uses_custom_dataset_and_exports(tmp_path, monkeypatch) -> None:
    calibrator = SentimentWeightCalibrator.__new__(SentimentWeightCalibrator)
    calibrator.engine = None
    dataset = pd.DataFrame(
        {
            "snapshot_date": pd.to_datetime(["2026-01-02"] * 3),
            "symbol": ["AAA", "BBB", "CCC"],
            "sector": ["Tech", "Tech", "Tech"],
            "final_score": [0.4, 0.5, 0.6],
            "sentiment_net_agg": [0.8, 0.1, -0.4],
            "sector_impact_agg": [0.2, 0.1, -0.1],
            "final_score_sentiment": [None, None, None],
            "selection_rank": [1, 2, 3],
            "forward_return_5d": [0.06, 0.01, -0.02],
        }
    )

    monkeypatch.setattr(
        calibrator,
        "load_dataset",
        lambda start_date, end_date, horizons=(5, 10, 20), selected_only=True, capital_preset_keys=None: dataset.copy(),
    )

    result, ranking_df, artifacts = calibrator.calibrate(
        start_date=date(2026, 1, 2),
        end_date=date(2026, 1, 2),
        scenarios=[SentimentCalibrationScenario(sentiment_weight=0.2, macro_weight=0.1, quant_weight=0.7)],
        horizons=(5,),
        top_n=1,
        output_dir=tmp_path,
    )

    assert result.scenarios_evaluated == 1
    assert result.best_scenario_name == "sent_0.20_macro_0.10_quant_0.70"
    assert not ranking_df.empty
    assert (tmp_path / "sentiment_weight_calibration.csv").exists()
    assert artifacts["best_json"].endswith("sentiment_weight_calibration_best.json")


def test_load_dataset_filters_stock_bars_daily_on_eodhd_source(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _FakeConn:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _FakeEngine:
        def connect(self):
            return _FakeConn()

    calibrator = SentimentWeightCalibrator.__new__(SentimentWeightCalibrator)
    calibrator.engine = _FakeEngine()

    def _fake_read_sql_query(query, conn, params=None):
        captured["sql"] = str(query)
        captured["params"] = params
        return pd.DataFrame(columns=[
            "snapshot_date", "symbol", "sector", "final_score",
            "sentiment_net_agg", "sector_impact_agg", "final_score_sentiment",
            "selection_rank", "short_score", "bar_date", "close_price",
        ])

    monkeypatch.setattr(
        "backtesting.sentiment_calibration.get_required_bars_source_filter",
        lambda engine, table_name="stock_bars_daily", table_alias=None: (
            f"AND {table_alias}.data_source = :required_data_source",
            {"required_data_source": "eodhd_eod"},
        ),
    )
    monkeypatch.setattr(pd, "read_sql_query", _fake_read_sql_query)
    monkeypatch.setattr(calibrator, "_list_symbols", lambda **kwargs: ["AAA"])

    result = calibrator.load_dataset(date(2026, 1, 1), date(2026, 1, 31))

    assert result.empty
    assert "b.data_source = :required_data_source" in captured["sql"]
    params = cast(dict[str, Any], captured["params"])
    assert params["required_data_source"] == "eodhd_eod"



