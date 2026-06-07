from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

from modelFactory import db_registry
from modelFactory.predictor import _build_prediction_result


def test_model_predictions_sql_contains_governance_columns() -> None:
    sql_path = Path(__file__).resolve().parents[1] / "database" / "sql" / "ml" / "model_predictions.sql"
    ddl = sql_path.read_text(encoding="utf-8")

    assert "selected_model" in ddl
    assert "decision_threshold" in ddl
    assert "calibration_method" in ddl


def test_insert_predictions_rejects_missing_governance_columns() -> None:
    predictions = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "prediction_date": "2026-06-01",
                "predicted_proba": 0.71,
                "predicted_class": 1,
                "run_id": "run-1",
                "decision_threshold": 0.6,
                "signal_label": "long",
                "calibration_method": "platt",
            }
        ]
    )

    with pytest.raises(ValueError, match="missing required columns"):
        db_registry.insert_predictions(MagicMock(), predictions)


def test_insert_predictions_rejects_empty_governance_values() -> None:
    predictions = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "prediction_date": "2026-06-01",
                "predicted_proba": 0.71,
                "predicted_class": 1,
                "run_id": "run-1",
                "selected_model": "",
                "decision_threshold": 0.6,
                "signal_label": "long",
                "calibration_method": "platt",
            }
        ]
    )

    with pytest.raises(ValueError, match="selected_model"):
        db_registry.insert_predictions(MagicMock(), predictions)


def test_predictor_builds_governance_fields_for_persistence() -> None:
    result = _build_prediction_result(
        symbol="AAPL",
        prediction_date=date(2026, 6, 1),
        proba=0.71,
        pred_class=1,
        run_id="run-1",
        raw_proba=0.69,
        decision_threshold=0.6,
        signal_label="long",
        calibration_method="platt",
        selected_model="lightgbm",
    )

    assert result.iloc[0]["selected_model"] == "lightgbm"
    assert result.iloc[0]["decision_threshold"] == pytest.approx(0.6)
    assert result.iloc[0]["calibration_method"] == "platt"


def test_insert_predictions_persists_governance_values() -> None:
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False

    predictions = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "prediction_date": "2026-06-01",
                "predicted_proba": 0.77,
                "predicted_class": 1,
                "run_id": "run-1",
                "selected_model": "lightgbm",
                "decision_threshold": 0.61,
                "signal_label": "long",
                "calibration_method": "platt",
            }
        ]
    )

    inserted = db_registry.insert_predictions(mock_engine, predictions)

    assert inserted == 1
    _, params = mock_conn.execute.call_args.args
    assert params["selected_model"] == "lightgbm"
    assert params["decision_threshold"] == pytest.approx(0.61)
    assert params["calibration_method"] == "platt"

