"""Tests pour ``run_summary`` ML (Phase 4.2.h)."""
from __future__ import annotations

import argparse
import json
from datetime import date

from modelFactory import cli as model_factory_cli
from modelFactory.config import (
    BaselineConfig,
    CalibrationConfig,
    ChampionSelectionConfig,
    DataConfig,
    ModelConfig,
    TargetOptimizationConfig,
    TrainingConfig,
    WalkForwardConfig,
)


def _make_opts(**overrides) -> argparse.Namespace:
    base = dict(
        walkforward=True,
        ml_mode="rebuild-all",
        training_start_date=date(2020, 1, 1),
        champion_min_runs=0,
        champion_min_days=0,
    )
    base.update(overrides)
    return argparse.Namespace(**base)


def _make_cfg() -> TrainingConfig:
    return TrainingConfig(
        data=DataConfig(training_start_date=date(2020, 1, 1)),
        model=ModelConfig(),
        calibration=CalibrationConfig(method="none"),
        walk_forward=WalkForwardConfig(),
        baseline=BaselineConfig(),
        champion_selection=ChampionSelectionConfig(),
        target_optimization=TargetOptimizationConfig(),
    )


def test_build_run_summary_contains_required_fields() -> None:
    from datetime import datetime
    started = datetime(2026, 4, 27, 10, 0, 0)
    finished = datetime(2026, 4, 27, 10, 5, 0)
    summary = model_factory_cli._build_run_summary(
        mode="train",
        run_id="model-factory-test-abc123",
        opts=_make_opts(),
        cfg=_make_cfg(),
        started_at=started,
        finished_at=finished,
        symbols_total=20,
        completed=18,
        skipped=1,
        failed=1,
        quarantined=0,
    )
    assert summary["schema_version"] == 1
    assert summary["mode"] == "train"
    assert summary["walkforward_enabled"] is True
    assert summary["ml_mode"] == "rebuild-all"
    assert summary["training_start_date"] == "2020-01-01"
    assert "feature_fingerprint" in summary
    assert summary["champion_min_runs"] == 0
    assert summary["champion_min_days"] == 0
    assert summary["symbols_total"] == 20
    assert summary["symbols_completed"] == 18
    assert summary["symbols_skipped"] == 1
    assert summary["symbols_failed"] == 1
    assert summary["symbols_quarantined"] == 0
    assert summary["duration_seconds"] == 300.0


def test_build_run_summary_reflects_quarantine_thresholds() -> None:
    from datetime import datetime
    summary = model_factory_cli._build_run_summary(
        mode="train",
        run_id="rid",
        opts=_make_opts(champion_min_runs=5, champion_min_days=14),
        cfg=_make_cfg(),
        started_at=datetime(2026, 4, 27),
        finished_at=datetime(2026, 4, 27),
        symbols_total=1,
        completed=1,
        skipped=0,
        failed=0,
        quarantined=1,
    )
    assert summary["champion_min_runs"] == 5
    assert summary["champion_min_days"] == 14
    assert summary["symbols_quarantined"] == 1


def test_run_summary_round_trips_through_json() -> None:
    from datetime import datetime
    summary = model_factory_cli._build_run_summary(
        mode="predict",
        run_id="rid-2",
        opts=_make_opts(walkforward=False, ml_mode="rebuild-missing"),
        cfg=_make_cfg(),
        started_at=datetime(2026, 4, 27),
        finished_at=datetime(2026, 4, 27),
        symbols_total=0,
        completed=0,
        skipped=0,
        failed=0,
        quarantined=0,
    )
    encoded = json.dumps(summary, sort_keys=True, default=str)
    decoded = json.loads(encoded)
    assert decoded["mode"] == "predict"
    assert decoded["walkforward_enabled"] is False
    assert decoded["ml_mode"] == "rebuild-missing"
    assert decoded["training_start_date"] == "2020-01-01"


def test_cli_parses_walkforward_default_on_and_no_walkforward() -> None:
    parser = model_factory_cli.build_arg_parser()
    opts_default = parser.parse_args(["--mode", "train"])
    assert opts_default.walkforward is True
    assert opts_default.ml_mode == "rebuild-all"
    assert opts_default.training_start_date == date(2020, 1, 1)

    opts_off = parser.parse_args(["--mode", "train", "--no-walkforward", "--ml-mode", "rebuild-missing", "--training-start-date", "2018-01-01"])
    assert opts_off.walkforward is False
    assert opts_off.ml_mode == "rebuild-missing"
    assert opts_off.training_start_date == date(2018, 1, 1)


def test_cli_parses_champion_quarantine_thresholds() -> None:
    parser = model_factory_cli.build_arg_parser()
    opts = parser.parse_args(["--mode", "train", "--champion-min-runs", "5", "--champion-min-days", "14"])
    assert opts.champion_min_runs == 5
    assert opts.champion_min_days == 14

