"""Prediction defaults must not inherit a mutable training-registry file."""

import json
from pathlib import Path

import pandas as pd
import pytest

from common.universe_files import load_universe_file_symbols
from ihm.pages import pipeline
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command


SOURCE = "universe-file:univers_filtred_tradable.txt"
OLD_SOURCE = "universe-file:oracle_balanced_400_202512.txt"


@pytest.mark.parametrize("initial", [None, "", OLD_SOURCE])
def test_new_or_old_default_session_uses_tradable(monkeypatch, initial):
    state = {} if initial is None else {"pipeline_ml_predict_symbol_source": initial}
    monkeypatch.setattr(pipeline.st, "session_state", state)
    pipeline._prime_ml_predict_symbol_source()
    assert state["pipeline_ml_predict_symbol_source"] == SOURCE
    # Once migrated, a deliberate manual choice must survive a rerender.
    state["pipeline_ml_predict_symbol_source"] = OLD_SOURCE
    pipeline._prime_ml_predict_symbol_source()
    assert state["pipeline_ml_predict_symbol_source"] == OLD_SOURCE


def test_existing_custom_choice_is_not_replaced(monkeypatch):
    state = {"pipeline_ml_predict_symbol_source": "stock-bars-daily"}
    monkeypatch.setattr(pipeline.st, "session_state", state)
    pipeline._prime_ml_predict_symbol_source()
    assert state["pipeline_ml_predict_symbol_source"] == "stock-bars-daily"


def test_selecting_batch_does_not_restore_training_source(monkeypatch):
    state = {}
    monkeypatch.setattr(pipeline.st, "session_state", state)
    monkeypatch.setattr("ihm.services.queries.safe_query", lambda *a, **kw: pd.DataFrame([
        {"batch_id": "batch-old-file", "symbol_source": OLD_SOURCE, "comment": "", "started_at": ""},
        {"batch_id": "batch-other", "symbol_source": "stock-bars-daily", "comment": "", "started_at": ""},
    ]))
    monkeypatch.setattr(pipeline.st, "selectbox", lambda *a, **kw: state[kw["key"]])
    monkeypatch.setattr(pipeline.st, "checkbox", lambda *a, **kw: kw["value"])
    monkeypatch.setattr(pipeline.st, "number_input", lambda *a, **kw: kw["value"])
    for name in ("caption", "warning", "info"):
        monkeypatch.setattr(pipeline.st, name, lambda *a, **kw: None)
    seen = []
    monkeypatch.setattr(pipeline, "_render_ml_scope_block",
                        lambda *a, **kw: seen.append(state["pipeline_ml_predict_symbol_source"]))
    options = PipelineLaunchOptions()
    for batch in ("batch-old-file", "batch-other"):
        state["pipeline_ml_predict_batch_id"] = batch
        pipeline._render_ml_predict_scope_block(options, workflow_active=False,
            active_for_step=[], db_config={}, all_runs=[])
    assert seen == [SOURCE, SOURCE]
    state["pipeline_ml_predict_symbol_source"] = "stock-bars-daily"
    state["pipeline_ml_predict_batch_id"] = "batch-old-file"
    pipeline._render_ml_predict_scope_block(options, workflow_active=False,
        active_for_step=[], db_config={}, all_runs=[])
    assert seen[-1] == "stock-bars-daily"


@pytest.mark.parametrize("options_filter", [False, True])
def test_prediction_command_default_is_explicit_tradable_file(monkeypatch, options_filter):
    from service.options_directional.config import OptionsFilterConfig
    monkeypatch.setattr("service.options_directional.config.load_options_filter_config",
                        lambda: OptionsFilterConfig(enabled=True))
    options = PipelineLaunchOptions(options_filter_enabled=options_filter,
        ml_predict_batch_id="test-batch", execution_mode="paper", account_id="default",
        risk_enable_kelly=False, trade_date="2026-10-26")
    assert options.ml_predict_symbol_source == SOURCE
    command = build_pipeline_command("ml_predict", options)
    assert command[command.index("--symbol-source") + 1] == SOURCE
    if options_filter:
        nested = json.loads(command[command.index("--command-json") + 1])
        assert nested[nested.index("--symbol-source") + 1] == SOURCE


def test_current_default_file_matches_batch_universe_file():
    """The short IHM name resolves to the same symbols as the explicit batch path."""
    assert Path("config/univers/univers_filtred_tradable.txt").is_file()
    assert set(load_universe_file_symbols(SOURCE)) == set(load_universe_file_symbols(
        "universe-file:config/univers_batch/univers_filtred_tradable.txt"))
