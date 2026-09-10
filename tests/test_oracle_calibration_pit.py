from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle.combine import apply_oracle_calibration


def _oracle_frame(size: int = 60) -> pd.DataFrame:
    probabilities = np.linspace(0.01, 0.99, size)
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02"] * size),
            "symbol": [f"S{i}" for i in range(size)],
            "proba_extreme": probabilities,
            "oracle_extreme10": (probabilities > 0.8).astype(int),
        }
    )


def test_isotonic_never_implicitly_fits_on_evaluated_oos_frame() -> None:
    with pytest.raises(ValueError, match="calibration_df séparé"):
        apply_oracle_calibration(_oracle_frame(), method="isotonic")


def test_isotonic_uses_explicit_separate_calibration_frame() -> None:
    evaluated = _oracle_frame(60)
    calibrated = apply_oracle_calibration(
        evaluated,
        method="isotonic",
        calibration_df=_oracle_frame(100),
    )

    assert len(calibrated) == len(evaluated)
    assert calibrated["proba_extreme"].between(0.0, 1.0).all()


def test_rank_calibration_remains_label_free() -> None:
    frame = _oracle_frame(60).drop(columns="oracle_extreme10")
    calibrated = apply_oracle_calibration(frame, method="rank")

    assert calibrated["proba_extreme"].min() > 0.0
    assert calibrated["proba_extreme"].max() == pytest.approx(1.0)
