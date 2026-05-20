"""S11.1 — Tests du job trimestriel de calibration des poids sentiment."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

from scripts.run_quarterly_weights_calibration import run


@dataclass
class _StubResult:
    start_date: date
    end_date: date
    folds_evaluated: int
    scenarios_evaluated: int
    out_of_sample_rows: int
    out_of_sample_days: int
    latest_best_scenario_name: str
    final_value: float
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    artifact_dir: str | None = None


def _make_result(final_value: float) -> _StubResult:
    return _StubResult(
        start_date=date(2025, 1, 1),
        end_date=date(2026, 1, 1),
        folds_evaluated=4,
        scenarios_evaluated=12,
        out_of_sample_rows=1000,
        out_of_sample_days=63,
        latest_best_scenario_name="sent0.10_macro0.05",
        final_value=final_value,
        total_return_pct=(final_value - 100_000) / 1000,
        sharpe_ratio=1.2,
        max_drawdown_pct=-5.0,
    )


class _FakeCalibrator:
    def __init__(self, final_value: float):
        self._final_value = final_value

    def walk_forward_backtest(self, *, start_date, end_date, output_dir):
        return (
            _make_result(self._final_value),
            pd.DataFrame(),
            pd.DataFrame(),
            pd.DataFrame(),
            {"walk_forward_folds_csv": str(Path(output_dir) / "walk_forward_folds.csv")},
        )


class _FakeSegmentedCalibrator:
    def walk_forward_backtests_by_regime(self, *, start_date, end_date, output_dir):
        return {
            "all": (
                _make_result(120_000.0),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                {"dataset_csv": str(Path(output_dir) / "conviction_kelly_dataset.csv")},
            ),
            "capital_preservation": (
                _make_result(115_000.0),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                {"dataset_csv": str(Path(output_dir) / "capital_preservation" / "conviction_kelly_dataset.csv")},
            ),
        }


class _FakeMultiSegmentCalibrator:
    def __init__(self) -> None:
        self.engine = None

    def walk_forward_backtests_by_segment(
        self,
        *,
        end_date,
        output_dir,
        horizon_days_values,
        lookback_months_values,
        min_live_observations,
        min_live_snapshot_days,
        min_live_symbols,
    ):
        from backtesting.weights_calibration import EmpiricalRiskCalibrationRun

        def _result(*, run_id, segment_key, regime, horizon, lookback, final_value, eligible):
            return (
                EmpiricalRiskCalibrationRun(
                    start_date=date(2025, 4, 1),
                    end_date=end_date,
                    observations_evaluated=300,
                    scenarios_evaluated=16,
                    latest_best_scenario_name=segment_key,
                    metric_name="sharpe",
                    metric_value=1.20 if eligible else 0.80,
                    final_value=final_value,
                    total_return_pct=5.0,
                    sharpe_ratio=1.10,
                    max_drawdown_pct=-4.0,
                    calibration_run_id=run_id,
                    calibration_batch_id="batch-001",
                    segment_key=segment_key,
                    horizon_days=horizon,
                    lookback_months=lookback,
                    distinct_snapshot_days=40,
                    distinct_symbols=25,
                    eligible_for_live=eligible,
                    eligibility_reason=None if eligible else "insufficient_snapshot_days",
                    best_weights={"score_weight": 0.4, "prediction_weight": 0.6},
                    artifact_dir=str(Path(output_dir) / segment_key.replace("|", "_")),
                    market_regime_mode=regime,
                ),
                pd.DataFrame(),
                pd.DataFrame(),
                pd.DataFrame(),
                {"dataset_csv": str(Path(output_dir) / segment_key.replace("|", "_") / "dataset.csv")},
            )

        return {
            "regime=all|horizon=5d|window=12m": _result(
                run_id="wcr-all-5-12",
                segment_key="regime=all|horizon=5d|window=12m",
                regime="all",
                horizon=5,
                lookback=12,
                final_value=120_000.0,
                eligible=True,
            ),
            "regime=capital_preservation|horizon=5d|window=12m": _result(
                run_id="wcr-cap-5-12",
                segment_key="regime=capital_preservation|horizon=5d|window=12m",
                regime="capital_preservation",
                horizon=5,
                lookback=12,
                final_value=114_000.0,
                eligible=False,
            ),
        }


def test_quarterly_job_writes_calibration_json(tmp_path: Path):
    rc = run(
        end=date(2026, 4, 1),
        lookback_months=12,
        output_root=tmp_path,
        no_alert=True,
        calibrator_factory=lambda: _FakeCalibrator(120_000.0),
    )
    assert rc == 0
    out = tmp_path / "2026-04-01" / "calibration.json"
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["final_value"] == 120_000.0
    assert payload["lookback_months"] == 12


def test_quarterly_job_writes_segmented_payload_when_calibrator_supports_regimes(tmp_path: Path):
    rc = run(
        end=date(2026, 4, 1),
        lookback_months=12,
        output_root=tmp_path,
        no_alert=True,
        calibrator_factory=lambda: _FakeSegmentedCalibrator(),
    )

    assert rc == 0
    payload = json.loads((tmp_path / "2026-04-01" / "calibration.json").read_text(encoding="utf-8"))
    assert payload["final_value"] == 120_000.0
    assert payload["segments"]["all"]["final_value"] == 120_000.0
    assert payload["segments"]["capital_preservation"]["final_value"] == 115_000.0
    assert "capital_preservation" in payload["artifacts_by_regime"]


def test_quarterly_job_writes_multi_segment_governance_and_drifts_payload(tmp_path: Path):
    rc = run(
        end=date(2026, 4, 1),
        lookback_months=12,
        output_root=tmp_path,
        no_alert=True,
        calibrator_factory=lambda: _FakeMultiSegmentCalibrator(),
        segment_horizons=[5],
        segment_lookback_months=[12],
    )

    assert rc == 0
    payload = json.loads((tmp_path / "2026-04-01" / "calibration.json").read_text(encoding="utf-8"))
    assert payload["reference_segment_key"] == "regime=all|horizon=5d|window=12m"
    assert payload["governance_summary"]["eligible_segments"] == 1
    assert payload["governance_summary"]["blocked_segments"] == 1
    assert payload["segments"]["regime=capital_preservation|horizon=5d|window=12m"]["eligible_for_live"] is False
    assert payload["segment_drifts"]
    assert payload["segment_drifts"][0]["comparison_kind"] == "vs_all_same_horizon_window"


def test_quarterly_job_emits_alert_on_drift_above_threshold(tmp_path: Path):
    # 1er run : final_value = 100k$
    run(
        end=date(2026, 1, 1),
        output_root=tmp_path,
        no_alert=True,
        calibrator_factory=lambda: _FakeCalibrator(100_000.0),
    )
    # 2nd run : final_value = 110k$ → drift = +10% > 5% → alerte attendue
    captured: list[str] = []

    class _Notifier:
        def notify_warning(self, msg: str) -> None:
            captured.append(msg)

    rc = run(
        end=date(2026, 4, 1),
        threshold_drift_pct=0.05,
        output_root=tmp_path,
        calibrator_factory=lambda: _FakeCalibrator(110_000.0),
        notifier_factory=lambda: _Notifier(),
    )
    assert rc == 2
    assert captured, "alerte aurait dû être envoyée"
    assert "dérive" in captured[0]


def test_quarterly_job_no_alert_within_threshold(tmp_path: Path):
    run(
        end=date(2026, 1, 1),
        output_root=tmp_path,
        no_alert=True,
        calibrator_factory=lambda: _FakeCalibrator(100_000.0),
    )
    captured: list[str] = []

    class _Notifier:
        def notify_warning(self, msg: str) -> None:
            captured.append(msg)

    rc = run(
        end=date(2026, 4, 1),
        threshold_drift_pct=0.05,
        output_root=tmp_path,
        calibrator_factory=lambda: _FakeCalibrator(102_000.0),  # +2 %
        notifier_factory=lambda: _Notifier(),
    )
    assert rc == 0
    assert not captured


def test_quarterly_job_returns_1_on_calibrator_exception(tmp_path: Path):
    class _Boom:
        def walk_forward_backtest(self, **kw):
            raise RuntimeError("DB down")

    rc = run(
        end=date(2026, 4, 1),
        output_root=tmp_path,
        no_alert=True,
        calibrator_factory=lambda: _Boom(),
    )
    assert rc == 1
    err = tmp_path / "2026-04-01" / "calibration_error.json"
    assert err.is_file()
    payload = json.loads(err.read_text(encoding="utf-8"))
    assert payload["type"] == "RuntimeError"

