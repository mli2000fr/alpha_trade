from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_canary import (
    _json_safe,
    daily_realized_metrics,
    load_config,
    monitor_distribution,
)


def _scores(dates: int = 50, *, shifted: bool = False) -> pd.DataFrame:
    rows = []
    base = np.linspace(0.05, 0.95, 100)
    for index, day in enumerate(pd.bdate_range("2025-01-02", periods=dates)):
        values = np.clip(base + (0.50 if shifted else 0.002 * np.sin(index)), 0, 1)
        rows.extend({"date": day, "symbol": f"S{i:03d}", "proba_extreme": value}
                    for i, value in enumerate(values))
    return pd.DataFrame(rows)


def test_load_config_requires_shadow_contract(tmp_path: Path) -> None:
    path = tmp_path / "canary.yaml"
    path.write_text("enabled: true\nbatch_id: b\n", encoding="utf-8")
    with pytest.raises(ValueError, match="symbols_file"):
        load_config(path)


def test_monitor_distribution_ok_for_baseline_like_day() -> None:
    baseline = _scores()
    current = baseline[baseline["date"].eq(baseline["date"].max())]
    report = monitor_distribution(current, baseline, model_id="batch")
    assert report["status"] == "OK"
    assert report["current"]["rows"] == 100


def test_monitor_distribution_alerts_on_large_shift() -> None:
    baseline = _scores()
    current = _scores(1, shifted=True)
    report = monitor_distribution(current, baseline, model_id="batch")
    assert report["status"] == "ALERT"
    assert report["reasons"]


def test_daily_realized_metrics_are_amplitude_based() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-02"] * 20),
        "symbol": [f"S{i}" for i in range(20)],
        "proba_extreme": np.arange(20, dtype=float),
        "future_return": np.linspace(-0.2, 0.2, 20),
        "oracle_extreme10": [1, 1] + [0] * 16 + [1, 1],
    })
    metrics = daily_realized_metrics(frame)
    assert metrics["rows"] == 20
    assert metrics["top20_amplitude_lift"] > 1.0


def test_json_safe_replaces_non_finite_values() -> None:
    assert _json_safe({"a": float("nan"), "b": np.float64(1.5)}) == {
        "a": None, "b": 1.5,
    }
