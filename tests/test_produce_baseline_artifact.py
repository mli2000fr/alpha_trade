from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


def _load_script_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "produce_baseline_artifact.py"
    spec = importlib.util.spec_from_file_location("produce_baseline_artifact", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_load_metrics_accepts_complete_real_side_metrics(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "long": {"precision": 0.61, "total_predictions": 42},
                "short": {"precision": 0.55, "total_predictions": 21},
                "flat": {"abstention_rate": 0.30, "total_predictions": 10},
            }
        ),
        encoding="utf-8",
    )

    metrics = _load_script_module()._load_metrics(str(metrics_path))

    assert metrics["long"]["precision"] == pytest.approx(0.61)
    assert metrics["flat"]["total_predictions"] == pytest.approx(10.0)


def test_load_metrics_rejects_non_finite_value(tmp_path: Path) -> None:
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "long": {"precision": float("nan")},
                "short": {"precision": 0.55},
                "flat": {"abstention_rate": 0.30},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="métrique invalide"):
        _load_script_module()._load_metrics(str(metrics_path))