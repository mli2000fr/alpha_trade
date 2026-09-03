from __future__ import annotations

import pandas as pd
import pytest

from backtesting.prediction_pit import (
    PredictionPitViolationError,
    assert_directional_bundle_predictions_pit,
)


def _predictions(**overrides: object) -> pd.DataFrame:
    row: dict[str, object] = {
        "symbol": "AAL",
        "trade_date": "2025-01-02",
        "direction_long_run_id": "long-run",
        "direction_short_run_id": "short-run",
        "direction_long_train_end_date": "2024-06-28",
        "direction_short_train_end_date": "2024-06-28",
    }
    row.update(overrides)
    return pd.DataFrame([row])


def test_directional_bundle_pit_accepts_two_models_available_before_trade() -> None:
    audit = assert_directional_bundle_predictions_pit(_predictions())

    assert audit.checked_rows == 1
    assert audit.invalid_rows == 0


@pytest.mark.parametrize(
    "column,value",
    [
        ("direction_long_train_end_date", "2025-01-02"),
        ("direction_short_train_end_date", "2025-06-30"),
        ("direction_long_train_end_date", None),
        ("direction_short_run_id", None),
    ],
)
def test_directional_bundle_pit_rejects_unavailable_or_unknown_branch(
    column: str,
    value: object,
) -> None:
    with pytest.raises(PredictionPitViolationError, match="Fuite temporelle ML"):
        assert_directional_bundle_predictions_pit(_predictions(**{column: value}))


def test_directional_bundle_pit_rejects_missing_lineage_columns() -> None:
    with pytest.raises(PredictionPitViolationError, match="métadonnées manquantes"):
        assert_directional_bundle_predictions_pit(
            pd.DataFrame({"symbol": ["AAL"], "trade_date": ["2025-01-02"]})
        )

