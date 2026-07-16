from datetime import date
from typing import cast
from unittest.mock import MagicMock

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from modelFactory import db_registry


def test_db_registry_importable():
    assert hasattr(db_registry, "__doc__")


def test_training_batch_registry_persists_metadata_and_only_updates_terminal_fields() -> None:
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False

    started_at = pd.Timestamp("2026-07-16T10:15:00").to_pydatetime()
    db_registry.insert_training_batch(
        mock_engine,
        batch_id="model-factory-20260716101500-abc123",
        command_line="python -m modelFactory --mode train",
        command_argv_json='["--mode", "train"]',
        metadata_json='{"feature_columns": ["daily_return"]}',
        symbol_source="tradable-universe",
        universe_date=date(2026, 7, 16),
        requested_symbol_count=2,
        training_start_date=date(2020, 1, 1),
        training_end_date=None,
        started_at=started_at,
    )
    db_registry.update_training_batch(
        mock_engine,
        "model-factory-20260716101500-abc123",
        status="completed",
        symbols_completed=2,
        symbols_skipped=0,
        symbols_failed=0,
    )

    insert_stmt, insert_params = mock_conn.execute.call_args_list[0].args
    assert "INSERT INTO model_training_batch" in str(insert_stmt)
    assert insert_params["bid"] == "model-factory-20260716101500-abc123"
    assert insert_params["command_argv_json"] == '["--mode", "train"]'

    update_stmt, update_params = mock_conn.execute.call_args_list[1].args
    assert "UPDATE model_training_batch" in str(update_stmt)
    assert update_params["symbols_completed"] == 2

    with pytest.raises(ValueError, match="immutable"):
        db_registry.update_training_batch(mock_engine, "batch", metadata_json="{}")


def test_load_training_run_filters_completed_artifacts_by_batch_id() -> None:
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.connect.return_value.__exit__.return_value = False
    mock_conn.execute.return_value.mappings.return_value.first.return_value = None

    assert db_registry.load_training_run(mock_engine, "AAPL", batch_id="campaign-expert") is None

    statement, params = mock_conn.execute.call_args.args
    assert "batch_id = :bid" in str(statement)
    assert "status = 'completed'" in str(statement)
    assert params == {"sym": "AAPL", "bid": "campaign-expert"}


def test_load_training_run_rejects_run_and_batch_selection_together() -> None:
    with pytest.raises(ValueError, match="cannot be selected together"):
        db_registry.load_training_run(MagicMock(), "AAPL", run_id="run-1", batch_id="campaign-expert")


def test_upsert_directional_oos_metrics_keeps_only_complete_empirical_sides() -> None:
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False

    db_registry.upsert_directional_oos_metrics(
        mock_engine,
        run_id="run-1",
        symbol="AAPL",
        as_of_date=date(2026, 4, 15),
        metrics_by_split={
            "test": {
                "long": {"hit_rate": 0.6, "payoff": 1.5, "tail_loss": 0.04, "trade_count": 12},
                "short": {"hit_rate": 1.0, "payoff": 0.0, "tail_loss": None, "trade_count": 5},
            },
        },
    )

    assert mock_conn.execute.call_count == 2
    _, inserted_rows = mock_conn.execute.call_args.args
    assert inserted_rows == [{
        "rid": "run-1", "sym": "AAPL", "side": "long", "split": "test",
        "asof": date(2026, 4, 15), "hit": 0.6, "payoff": 1.5,
        "tail": 0.04, "trades": 12, "policy_version": 1,
    }]


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
    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_conn.execute.return_value = mock_result

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


def test_load_score_context_delegates_to_stock_scores(monkeypatch) -> None:
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
        "load_stock_score_context",
        lambda engine, limit=None: expected,
    )

    result = db_registry.load_score_context(cast(Engine, object()), limit=5)

    assert result.equals(expected)


def test_filter_symbols_by_score_context_applies_all_supported_filters(monkeypatch) -> None:
    monkeypatch.setattr(
        db_registry,
        "load_score_context",
        lambda engine: pd.DataFrame(
            [
                {
                    "symbol": "AAPL",
                    "selector_signal_mode": "strict",
                    "selection_rank": 4,
                    "earnings_blackout": False,
                },
                {
                    "symbol": "MSFT",
                    "selector_signal_mode": "sector_neutralized",
                    "selection_rank": 11,
                    "earnings_blackout": False,
                },
                {
                    "symbol": "NVDA",
                    "selector_signal_mode": "strict",
                    "selection_rank": 2,
                    "earnings_blackout": True,
                },
            ]
        ),
    )

    filtered, summary = db_registry.filter_symbols_by_score_context(
        cast(Engine, object()),
        ["AAPL", "MSFT", "NVDA"],
        signal_modes=("strict",),
        max_selection_rank=5,
        exclude_earnings_blackout=True,
    )

    assert filtered == ["AAPL"]
    assert summary["enabled"] is True
    assert summary["applied"] is True
    assert summary["output_symbol_count"] == 1


def test_filter_symbols_by_score_context_fails_open_when_required_columns_are_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        db_registry,
        "load_score_context",
        lambda engine: pd.DataFrame([{"symbol": "AAPL"}, {"symbol": "MSFT"}]),
    )

    filtered, summary = db_registry.filter_symbols_by_score_context(
        cast(Engine, object()),
        ["AAPL", "MSFT"],
        signal_modes=("strict",),
    )

    assert filtered == ["AAPL", "MSFT"]
    assert summary["enabled"] is True
    assert summary["applied"] is False
    assert "score_context_missing_columns" in str(summary["reason"])


def test_load_symbols_for_source_rejects_legacy_sources() -> None:
    with pytest.raises(ValueError, match="Source ML non admise"):
        db_registry.load_symbols_for_source(cast(Engine, object()), "stock-scores-all")


def test_load_symbols_for_source_dispatches_tradable_universe(monkeypatch) -> None:
    monkeypatch.setattr(
        db_registry,
        "load_tradable_universe_symbols",
        lambda engine, *, trade_date, capital_preset_key: ["AAPL", "MSFT"],
    )

    result = db_registry.load_symbols_for_source(
        cast(Engine, object()),
        "tradable-universe",
        trade_date=date(2025, 1, 2),
        capital_preset_key="small",
    )

    assert result == ["AAPL", "MSFT"]


def test_tradable_universe_source_requires_trade_date() -> None:
    with pytest.raises(ValueError, match="trade_date est obligatoire"):
        db_registry.load_symbols_for_source(cast(Engine, object()), "tradable-universe")


# ── Section 17 Point 5.3 : append-only idempotent predictions ───────────────

def test_insert_predictions_append_only_skips_duplicate_keys() -> None:
    """Une ré-insertion avec la même clé métier (symbol, prediction_date,
    run_id) doit être ignorée silencieusement (rowcount=0), sans erreur."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False

    # Simulation : première ligne insérée (rowcount=1), deuxième ligne
    # dupliquée (rowcount=0 car ON DUPLICATE KEY UPDATE run_id = run_id
    # est un no-op).
    mock_result_1 = MagicMock()
    mock_result_1.rowcount = 1  # nouvel insert
    mock_result_2 = MagicMock()
    mock_result_2.rowcount = 0  # clé dupliquée → ignoré
    mock_conn.execute.side_effect = [mock_result_1, mock_result_2]

    predictions = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "prediction_date": "2026-07-10",
                "predicted_proba": 0.77,
                "predicted_class": 1,
                "run_id": "run-1",
                "selected_model": "lightgbm",
                "decision_threshold": 0.61,
                "signal_label": "long",
                "calibration_method": "platt",
            },
            {
                "symbol": "AAPL",  # même clé que ci-dessus
                "prediction_date": "2026-07-10",
                "predicted_proba": 0.80,
                "predicted_class": 1,
                "run_id": "run-1",
                "selected_model": "lightgbm",
                "decision_threshold": 0.61,
                "signal_label": "long",
                "calibration_method": "platt",
            },
        ]
    )

    inserted = db_registry.insert_predictions(mock_engine, predictions)
    assert inserted == 1, (
        f"Append-only: seule la première ligne doit être insérée (1), "
        f"la seconde est un duplicata ignoré. Obtenu: {inserted}"
    )
    assert mock_conn.execute.call_count == 2


def test_insert_predictions_append_only_all_duplicates_returns_zero() -> None:
    """Si toutes les lignes sont des duplicatas, inserted=0."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False

    mock_result = MagicMock()
    mock_result.rowcount = 0  # duplicata
    mock_conn.execute.return_value = mock_result

    predictions = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "prediction_date": "2026-07-10",
                "predicted_proba": 0.77,
                "predicted_class": 1,
                "run_id": "run-1",
                "selected_model": "lightgbm",
                "decision_threshold": 0.61,
                "signal_label": "long",
                "calibration_method": "platt",
            },
        ]
    )

    inserted = db_registry.insert_predictions(mock_engine, predictions)
    assert inserted == 0, "Toutes les lignes étant des duplicatas, inserted doit être 0"


def test_insert_predictions_on_duplicate_key_is_noop() -> None:
    """Vérifie que le SQL utilise ON DUPLICATE KEY UPDATE run_id = run_id
    (no-op) et non un UPDATE réel qui écraserait les données."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__exit__.return_value = False

    mock_result = MagicMock()
    mock_result.rowcount = 1
    mock_conn.execute.return_value = mock_result

    predictions = pd.DataFrame(
        [
            {
                "symbol": "AAPL",
                "prediction_date": "2026-07-10",
                "predicted_proba": 0.77,
                "predicted_class": 1,
                "run_id": "run-1",
                "selected_model": "lightgbm",
                "decision_threshold": 0.61,
                "signal_label": "long",
                "calibration_method": "platt",
            },
        ]
    )

    db_registry.insert_predictions(mock_engine, predictions)

    stmt, _params = mock_conn.execute.call_args.args
    sql_text = str(stmt)
    # Le ON DUPLICATE KEY UPDATE doit être un no-op: run_id = run_id
    assert "ON DUPLICATE KEY UPDATE" in sql_text
    assert "run_id = run_id" in sql_text, (
        f"Attendu 'ON DUPLICATE KEY UPDATE run_id = run_id' (no-op idempotent). "
        f"SQL obtenu: {sql_text[:200]}"
    )
    # Aucune colonne métier ne doit être mise à jour
    for forbidden in [
        "predicted_proba = VALUES(predicted_proba)",
        "predicted_class = VALUES(predicted_class)",
        "selected_model = VALUES(selected_model)",
    ]:
        assert forbidden not in sql_text, (
            f"L'upsert ne doit PAS écraser {forbidden.split('=')[0].strip()}. "
            f"Persistance append-only obligatoire."
        )
