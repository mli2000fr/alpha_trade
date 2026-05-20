import pandas as pd

from ihm.pages import weights_calibration_runs


def test_pages_weights_calibration_runs_importable() -> None:
    assert hasattr(weights_calibration_runs, "__doc__")


def test_parse_json_payload_returns_dict_or_empty() -> None:
    assert weights_calibration_runs._parse_json_payload('{"score_weight": 0.4}') == {"score_weight": 0.4}
    assert weights_calibration_runs._parse_json_payload("not-json") == {}


def test_build_candidates_frame_flattens_weights_payload() -> None:
    df = weights_calibration_runs._build_candidates_frame(
        '[{"metric_value": 1.2, "weights": {"score_weight": 0.3, "prediction_weight": 0.7}}]'
    )

    assert list(df.columns) == ["metric_value", "weights", "score_weight", "prediction_weight"]
    assert df.iloc[0]["score_weight"] == 0.3
    assert df.iloc[0]["prediction_weight"] == 0.7


def test_build_overview_metrics_exposes_latest_run_context() -> None:
    df = pd.DataFrame(
        [
            {
                "run_id": "wcr-002",
                "market_regime_mode": "capital_preservation",
                "metric_name": "sharpe",
                "metric_value": 1.2345,
            },
            {
                "run_id": "wcr-001",
                "market_regime_mode": "all",
                "metric_name": "sharpe",
                "metric_value": 1.1111,
            },
        ]
    )

    metrics = weights_calibration_runs._build_overview_metrics(df)

    assert metrics["runs"] == 2
    assert metrics["latest_run_id"] == "wcr-002"
    assert metrics["latest_regime"] == "capital_preservation"
    assert metrics["latest_metric"] == "sharpe=1.2345"

