from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.metrics import (
    decile_monotonicity,
    precision_recall_at_top_pct,
    roc_auc,
)


def test_roc_auc_perfect_ranking() -> None:
    assert roc_auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])) == pytest.approx(1.0)


def test_precision_recall_at_top_pct_is_cross_sectional() -> None:
    rows = []
    for date in ("2025-01-02", "2025-01-03"):
        for index in range(20):
            rows.append(
                {
                    "date": date,
                    "score": float(index),
                    "oracle_extreme10": int(index >= 18),
                }
            )
    result = precision_recall_at_top_pct(pd.DataFrame(rows), "score", pct=0.10)
    assert result == {"precision": 1.0, "recall": 1.0, "n_dates": 2}


def test_decile_monotonicity_detects_increasing_returns() -> None:
    frame = pd.DataFrame(
        {
            "date": ["2025-01-02"] * 100,
            "score": np.arange(100, dtype=float),
            "future_return": np.arange(100, dtype=float),
        }
    )
    monotonicity, stats = decile_monotonicity(frame, "score")
    assert monotonicity == pytest.approx(1.0)
    assert len(stats) == 10


def test_diagnostics_use_lightweight_metrics_module() -> None:
    source = (
        __import__("pathlib").Path("ihm/pages/ml_diagnostics.py")
        .read_text(encoding="utf-8")
    )
    render_source = source[source.index("def _render_oracle_quality"):source.index("def _render_prediction_periods")]
    assert "from modelFactory.oracle.metrics import" in render_source
    assert "from modelFactory.oracle.train import" not in render_source
