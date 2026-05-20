from typing import cast
from unittest.mock import MagicMock

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from modelFactory import db_registry


def test_db_registry_importable():
    assert hasattr(db_registry, "__doc__")


def test_build_governance_rows_extracts_ranking_routes_and_metrics():
    rows = db_registry.build_governance_rows(
        run_id="run-1",
        symbol="AAPL",
        challengers={
            "lstm_attention": {
                "status": "completed",
                "selection_score": 0.61,
                "selection_eligible": True,
                "calibration_method": "platt",
                "val": {"auc": 0.62, "threshold_business_score": 0.58},
                "test": {"auc": 0.61, "threshold_business_score": 0.57},
                "walk_forward": {"mean": {"auc": 0.60, "threshold_business_score": 0.55}},
            },
            "lightgbm": {
                "status": "completed",
                "selection_score": 0.70,
                "selection_eligible": True,
                "backend_model_name": "lightgbm",
                "test": {"auc": 0.70, "threshold_business_score": 0.69},
            },
        },
        artifact_routes_models={
            "lstm_attention": {
                "inference_backend": "lstm_attention",
                "checkpoint_path": "best.ckpt",
                "scaler_path": "scaler.pkl",
                "config_path": "config.json",
            },
            "lightgbm": {
                "inference_backend": "lightgbm_tabular",
                "model_path": "lightgbm.pkl",
                "config_path": "config.json",
                "selected_decision_threshold": 0.61,
            },
        },
        selected_model="lightgbm",
        selection_mode="auto_selected_champion",
        selection_metric="selection_score",
        ranking=[
            {"rank": 1, "model_name": "lightgbm", "status": "selected_auto_champion", "selection_score": 0.70},
            {"rank": 2, "model_name": "lstm_attention", "status": "completed", "selection_score": 0.61},
        ],
    )

    assert len(rows) == 2
    by_model = {row["model_name"]: row for row in rows}
    assert by_model["lightgbm"]["rank"] == 1
    assert by_model["lightgbm"]["is_selected_model"] == 1
    assert by_model["lightgbm"]["decision_threshold"] == 0.61
    assert by_model["lightgbm"]["inference_backend"] == "lightgbm_tabular"
    assert by_model["lstm_attention"]["calibration_method"] == "platt"
    assert by_model["lstm_attention"]["wf_auc"] == 0.60


def test_replace_model_governance_propagates_db_errors():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False
    mock_conn.execute.side_effect = RuntimeError("unknown table")

    with pytest.raises(RuntimeError, match="unknown table"):
        db_registry.replace_model_governance(
            mock_engine,
            run_id="run-1",
            symbol="AAPL",
            challengers={"lstm_attention": {"status": "completed", "selection_score": 0.5}},
            artifact_routes_models={"lstm_attention": {"inference_backend": "lstm_attention"}},
            selected_model="lstm_attention",
            selection_mode="default_champion",
            selection_metric="selection_score",
            ranking=[{"rank": 1, "model_name": "lstm_attention", "status": "selected_default_champion"}],
        )


def test_insert_predictions_uses_current_schema_columns_only():
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False

    predictions = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "prediction_date": "2026-04-21",
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
    assert mock_conn.execute.call_count == 1
    stmt, params = mock_conn.execute.call_args.args
    sql_text = str(stmt)
    assert "selected_model" in sql_text
    assert "decision_threshold" in sql_text
    assert params["selected_model"] == "lightgbm"
    assert params["signal_label"] == "long"


def test_load_candidate_selector_context_delegates_to_stock_scores(monkeypatch) -> None:
    expected = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "final_score": 0.91,
                "selector_signal_mode": "strict",
                "selection_explanation": "breakout + RS",
            }
        ]
    )

    monkeypatch.setattr(
        db_registry,
        "load_candidate_stock_score_context",
        lambda engine, limit=None: expected,
    )

    result = db_registry.load_candidate_selector_context(cast(Engine, object()), limit=5)

    assert result.equals(expected)


def test_filter_symbols_by_selector_context_applies_all_supported_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        db_registry,
        "load_candidate_selector_context",
        lambda engine: pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "selector_signal_mode": "strict",
                    "candidate_rank": 4,
                    "earnings_blackout": False,
                },
                {
                    "symbol": "MSFT",
                    "selector_signal_mode": "sector_neutralized",
                    "candidate_rank": 11,
                    "earnings_blackout": False,
                },
                {
                    "symbol": "NVDA",
                    "selector_signal_mode": "strict",
                    "candidate_rank": 2,
                    "earnings_blackout": True,
                },
            ]
        ),
    )

    filtered, summary = db_registry.filter_symbols_by_selector_context(
        cast(Engine, object()),
        ["AAPL", "MSFT", "NVDA"],
        signal_modes=("strict",),
        max_candidate_rank=5,
        exclude_earnings_blackout=True,
    )

    assert filtered == ["AAPL"]
    assert summary["enabled"] is True
    assert summary["applied"] is True
    assert summary["output_symbol_count"] == 1


def test_filter_symbols_by_selector_context_fails_open_when_required_columns_are_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        db_registry,
        "load_candidate_selector_context",
        lambda engine: pd.DataFrame([{"symbol": "AAPL"}, {"symbol": "MSFT"}]),
    )

    filtered, summary = db_registry.filter_symbols_by_selector_context(
        cast(Engine, object()),
        ["AAPL", "MSFT"],
        signal_modes=("strict",),
    )

    assert filtered == ["AAPL", "MSFT"]
    assert summary["enabled"] is True
    assert summary["applied"] is False
    assert "selector_context_missing_columns" in str(summary["reason"])


