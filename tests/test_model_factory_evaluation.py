from __future__ import annotations

import numpy as np
import pandas as pd

from modelFactory.evaluation import align_sequence_rows, bucket_analysis


def test_bucket_analysis_returns_expected_bucket_count() -> None:
    result = bucket_analysis(
        np.array([0.1, 0.2, 0.7, 0.9]),
        np.array([0, 0, 1, 1]),
        np.array([-0.01, 0.0, 0.02, 0.03]),
        n_buckets=2,
    )

    assert result["n_buckets"] == 2
    assert len(result["buckets"]) == 2
    assert result["buckets"][0]["count"] == 2


def test_align_sequence_rows_drops_warmup_and_nan_targets() -> None:
    df = pd.DataFrame(
        {
            "target": [1.0, 0.0, 1.0, np.nan, 0.0],
            "future_return": [0.1, -0.1, 0.2, np.nan, -0.05],
        }
    )

    aligned = align_sequence_rows(df, seq_len=2)

    assert len(aligned) == 2
    assert aligned["target"].tolist() == [1.0, 0.0]
