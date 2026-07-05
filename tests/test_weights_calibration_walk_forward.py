from __future__ import annotations

from datetime import date

import pandas as pd


def test_walk_forward_optimize_propagates_directional_top_n_and_net_exposure(monkeypatch, tmp_path):
	from backtesting.sentiment_calibration import SentimentWeightCalibrator
	from backtesting.weights_calibration import EmpiricalRiskCalibrator

	calibrator = EmpiricalRiskCalibrator()
	dataset = pd.DataFrame(
		{
			"snapshot_date": pd.to_datetime(
				["2025-01-10", "2025-01-10", "2025-02-10", "2025-02-10"]
			),
			"selector_signal_mode": ["long", "short", "long", "short"],
		}
	)

	train_calls: list[dict[str, object]] = []
	oos_calls: list[dict[str, object]] = []

	monkeypatch.setattr(calibrator, "load_dataset", lambda **kwargs: dataset.copy())
	monkeypatch.setattr(
		SentimentWeightCalibrator,
		"build_walk_forward_windows",
		lambda *args, **kwargs: [
			{
				"fold_index": 1,
				"train_start_date": "2025-01-01",
				"train_end_date": "2025-01-31",
				"test_start_date": "2025-02-01",
				"test_end_date": "2025-02-28",
			}
		],
	)

	def fake_walk_forward_backtest(**kwargs):
		train_calls.append(kwargs)
		return (
			type(
				"Run",
				(),
				{
					"best_weights": {
						"long_score_weight": 0.7,
						"long_prediction_weight": 0.3,
						"long_kelly_fraction_multiplier": 0.25,
						"long_min_effective_probability": 0.52,
						"long_assumed_payoff_ratio": 1.5,
						"short_score_weight": 0.6,
						"short_prediction_weight": 0.4,
						"short_kelly_fraction_multiplier": 0.25,
						"short_min_effective_probability": 0.52,
						"short_assumed_payoff_ratio": 1.5,
					},
					"sharpe_ratio": 1.23,
				},
			)(),
			pd.DataFrame(),
			pd.DataFrame(),
			pd.DataFrame(),
			{},
		)

	def fake_evaluate_kelly_in_backtest(**kwargs):
		oos_calls.append(kwargs)
		return {"sharpe": 1.0, "total_return_pct": 2.0, "max_drawdown_pct": -1.0}

	monkeypatch.setattr(calibrator, "walk_forward_backtest", fake_walk_forward_backtest)
	monkeypatch.setattr(calibrator, "evaluate_kelly_in_backtest", fake_evaluate_kelly_in_backtest)

	report = calibrator.walk_forward_optimize(
		start_date=date(2025, 1, 1),
		end_date=date(2025, 2, 28),
		output_dir=tmp_path,
		top_n=20,
		horizon_days=5,
		top_n_long=30,
		top_n_short=15,
		enforce_net_exposure=True,
		net_exposure_target=0.0,
	)

	assert report["config"]["top_n_long"] == 30
	assert report["config"]["top_n_short"] == 15
	assert report["config"]["enforce_net_exposure"] is True
	assert train_calls[0]["top_n_long"] == 30
	assert train_calls[0]["top_n_short"] == 15
	assert train_calls[0]["enforce_net_exposure"] is True
	assert train_calls[0]["net_exposure_target"] == 0.0
	assert [call["direction"] for call in oos_calls] == ["long", "short"]
	assert oos_calls[0]["top_n"] == 30
	assert oos_calls[1]["top_n"] == 15
	assert all(call["enforce_net_exposure"] is True for call in oos_calls)
	assert all(call["net_exposure_target"] == 0.0 for call in oos_calls)
