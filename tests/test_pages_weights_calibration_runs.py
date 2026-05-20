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
                "eligible_for_live": 1,
            },
            {
                "run_id": "wcr-001",
                "market_regime_mode": "all",
                "metric_name": "sharpe",
                "metric_value": 1.1111,
                "eligible_for_live": 0,
            },
        ]
    )

    metrics = weights_calibration_runs._build_overview_metrics(df)

    assert metrics["runs"] == 2
    assert metrics["latest_run_id"] == "wcr-002"
    assert metrics["latest_regime"] == "capital_preservation"
    assert metrics["latest_metric"] == "sharpe=1.2345"
    assert metrics["eligible_segments"] == 1


def test_prepare_drift_frames_sorts_and_summarizes_selected_run() -> None:
    df = pd.DataFrame(
        [
            {
                "run_id": "wcsd-001",
                "comparison_kind": "vs_reference_live_segment",
                "source_run_id": "wcr-002",
                "metric_delta": 0.10,
                "final_value_drift_pct": 0.08,
                "compared_at": "2026-05-20T10:00:00",
            },
            {
                "run_id": "wcsd-002",
                "comparison_kind": "vs_all_same_horizon_window",
                "source_run_id": "wcr-002",
                "metric_delta": -0.20,
                "final_value_drift_pct": -0.12,
                "compared_at": "2026-05-20T11:00:00",
            },
            {
                "run_id": "wcsd-003",
                "comparison_kind": "vs_reference_live_segment",
                "source_run_id": "wcr-001",
                "metric_delta": 0.05,
                "final_value_drift_pct": 0.02,
                "compared_at": "2026-05-20T09:00:00",
            },
        ]
    )

    frames = weights_calibration_runs._prepare_drift_frames(df, selected_run_id="wcr-002")

    assert list(frames["selected"]["run_id"]) == ["wcsd-002", "wcsd-001"]
    assert set(frames["summary"]["comparison_kind"]) == {
        "vs_all_same_horizon_window",
        "vs_reference_live_segment",
    }
    summary_rows = {
        row["comparison_kind"]: row for row in frames["summary"].to_dict("records")
    }
    assert summary_rows["vs_all_same_horizon_window"]["max_abs_final_value_drift_pct"] == 0.12
    assert summary_rows["vs_reference_live_segment"]["drift_rows"] == 2


def test_build_drift_metrics_exposes_abs_maxima() -> None:
    df = pd.DataFrame(
        [
            {"comparison_kind": "vs_all_same_horizon_window", "abs_metric_delta": 0.2, "abs_final_value_drift_pct": 0.12},
            {"comparison_kind": "vs_reference_live_segment", "abs_metric_delta": 0.1, "abs_final_value_drift_pct": 0.08},
        ]
    )

    metrics = weights_calibration_runs._build_drift_metrics(df)

    assert metrics["drift_rows"] == 2
    assert metrics["comparison_kinds"] == 2
    assert metrics["max_abs_metric_delta"] == 0.2
    assert metrics["max_abs_final_value_drift_pct"] == 0.12


def test_build_drift_chart_frames_returns_summary_and_detail_series() -> None:
    all_drifts = pd.DataFrame(
        [
            {
                "comparison_kind": "vs_all_same_horizon_window",
                "target_segment_key": "regime=all|horizon=5d|window=12m",
                "metric_delta": -0.2,
                "final_value_drift_pct": -0.12,
                "abs_metric_delta": 0.2,
                "abs_final_value_drift_pct": 0.12,
                "compared_at": "2026-05-20T10:00:00",
            },
            {
                "comparison_kind": "vs_reference_live_segment",
                "target_segment_key": "regime=all|horizon=5d|window=12m",
                "metric_delta": 0.1,
                "final_value_drift_pct": 0.08,
                "abs_metric_delta": 0.1,
                "abs_final_value_drift_pct": 0.08,
                "compared_at": "2026-05-20T11:00:00",
            },
        ]
    )
    selected_drifts = all_drifts.iloc[[0]].copy()

    chart_frames = weights_calibration_runs._build_drift_chart_frames(all_drifts, selected_drifts=selected_drifts)

    assert list(chart_frames["summary_chart"].columns) == ["max_abs_metric_delta", "max_abs_final_value_drift_pct"]
    assert "vs_all_same_horizon_window" in chart_frames["summary_chart"].index
    assert list(chart_frames["detail_chart"].columns) == ["metric_delta", "final_value_drift_pct"]
    assert "regime=all|horizon=5d|window=12m" in chart_frames["detail_chart"].index
    assert list(chart_frames["metric_direction_chart"].columns) == ["metric_delta"]
    assert list(chart_frames["final_value_direction_chart"].columns) == ["final_value_drift_pct"]
    assert not chart_frames["timeline_chart"].empty


