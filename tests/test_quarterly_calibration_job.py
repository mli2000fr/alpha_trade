"""S11.1 — Tests du job trimestriel de calibration des poids sentiment."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

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

