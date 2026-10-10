"""Offline regressions for the 2026-10-10 ML Predict failure."""
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

from modelFactory import cli
from modelFactory.predictor import resolve_global_rank_artifacts_dir
from modelFactory.synthetic_prediction_run import ensure_synthetic_run


class Result:
    def __init__(self, value=None, rows=()):
        self.value, self.rows = value, rows

    def scalar(self):
        return self.value

    def fetchall(self):
        return self.rows


class Engine:
    def __init__(self, market="US_EQ", rows=()):
        self.market, self.rows = market, rows
        self.calls = []

    @contextmanager
    def connect(self):
        yield self

    begin = connect

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, params if isinstance(params, list) else dict(params or {})))
        if "SELECT market_code" in sql:
            return Result(self.market)
        if "SHOW COLUMNS" in sql:
            return Result(rows=[("global_rank_20",)])
        if "SELECT symbol" in sql:
            return Result(rows=self.rows)
        return Result()


def test_synthetic_parent_has_explicit_us_scope():
    engine = Engine()
    ensure_synthetic_run(engine, batch_id="batch", run_id="run", symbol="__SYNTH__")
    insert, params = engine.calls[-1]
    assert "market_code" in insert
    assert params["market_code"] == "US_EQ"
    assert params["batch_id"] == "batch"


@pytest.mark.parametrize("market", ["CN_A", "FR_EQ", None])
def test_synthetic_parent_rejects_wrong_or_missing_parent_before_writing(market):
    engine = Engine(market)
    with pytest.raises(ValueError):
        ensure_synthetic_run(engine, batch_id="batch", run_id="run", symbol="__SYNTH__")
    assert not any("INSERT" in sql for sql, _ in engine.calls)


def test_global_synthesis_is_scoped_to_requested_session(monkeypatch):
    from modelFactory import synthesize_global_rank_predictions as module
    engine = Engine(rows=[("AAPL", "2026-10-09", .97)])
    monkeypatch.setattr(module, "get_sqlalchemy_engine", lambda: engine)
    result = module.synthesize("batch", 20, start="2026-10-09", end="2026-10-09")
    assert result["inserted"] == 1
    sql, params = next((s, p) for s, p in engine.calls if "SELECT symbol" in s)
    assert "`date` >= :start" in sql and "`date` <= :end" in sql
    assert params["start"] == params["end"] == "2026-10-09"
    assert next(p for s, p in engine.calls if "INSERT INTO alpha_trade.model_training_run" in s)["market_code"] == "US_EQ"


def test_empty_global_synthesis_creates_no_completed_run(monkeypatch):
    from modelFactory import synthesize_global_rank_predictions as module
    engine = Engine()
    monkeypatch.setattr(module, "get_sqlalchemy_engine", lambda: engine)
    assert module.synthesize("batch", 20)["status"] == "error"
    assert not any("INSERT" in s for s, _ in engine.calls)


def test_oracle_synthesis_also_has_explicit_parent_scope(monkeypatch):
    from modelFactory import synthesize_oracle_predictions as module
    engine = Engine()
    monkeypatch.setattr(module, "get_sqlalchemy_engine", lambda: engine)
    monkeypatch.setattr(module.pd, "read_sql", lambda *a, **k: pd.DataFrame([
        {"prediction_date": "2026-10-09", "symbol": "AAPL", "proba_extreme": .95}
    ]))
    assert module.synthesize("batch")["inserted"] == 1
    assert next(p for s, p in engine.calls if "INSERT INTO alpha_trade.model_training_run" in s)["market_code"] == "US_EQ"


def test_empty_oracle_synthesis_creates_no_completed_run(monkeypatch):
    from modelFactory import synthesize_oracle_predictions as module
    engine = Engine()
    monkeypatch.setattr(module, "get_sqlalchemy_engine", lambda: engine)
    monkeypatch.setattr(module.pd, "read_sql", lambda *a, **k: pd.DataFrame())
    assert module.synthesize("batch")["status"] == "error"
    assert not any("INSERT" in s for s, _ in engine.calls)


def test_artifacts_root_resolves_selected_batch_not_other_models(tmp_path):
    selected = tmp_path / "batch"
    selected.mkdir()
    (selected / "_global_ranking_features.json").write_text("{}")
    (tmp_path / "_global_ranking_features.json").write_text("{}")
    assert resolve_global_rank_artifacts_dir(tmp_path, "batch") == selected
    assert resolve_global_rank_artifacts_dir(selected, "batch") == selected


def test_missing_artifacts_point_to_expected_batch(tmp_path):
    assert resolve_global_rank_artifacts_dir(tmp_path, "batch") == tmp_path / "batch"


def test_legacy_flat_artifacts_are_supported(tmp_path):
    (tmp_path / "_global_ranking_features.json").write_text("{}")
    assert resolve_global_rank_artifacts_dir(tmp_path, "batch") == tmp_path


@pytest.mark.parametrize("historical,key", [(True, "backtest_batch_id"), (False, "live_batch_id")])
def test_cli_auto_batch_uses_live_or_historical_config(monkeypatch, historical, key):
    import builtins
    import io
    monkeypatch.setattr(builtins, "open", lambda *a, **k: io.StringIO(
        "batch_diagnostics:\n  live_batch_id: live\n  backtest_batch_id: history\n"))
    assert cli._resolve_predict_batch_id(Path("artifacts/models"), historical=historical) == (
        "live" if key == "live_batch_id" else "history")
    assert cli._resolve_predict_batch_id(Path("artifacts/models/model-factory-explicit"), historical=historical) == "model-factory-explicit"


@pytest.mark.parametrize("result", [{}, {"2026-10-09": 0}, {"2026-10-09": -1}, {"2026-10-08": 50}])
def test_live_rank_guard_rejects_empty_failed_or_stale_day(result):
    with pytest.raises(RuntimeError, match="Aucun classement"):
        cli._require_live_global_ranks(result, day="2026-10-09", batch_id="batch")


def test_live_rank_guard_accepts_current_rows():
    cli._require_live_global_ranks({"2026-10-09": 50}, day="2026-10-09", batch_id="batch")


@pytest.mark.parametrize("result", [{"status": "error"}, {"status": "completed", "inserted": 0}])
def test_live_synthesis_guard_rejects_empty(result):
    with pytest.raises(RuntimeError, match="Synthèse"):
        cli._require_live_synthesis(result, day="2026-10-09", batch_id="batch")


@pytest.mark.parametrize("historical,expected", [(False, "live"), (True, "history")])
def test_pipeline_keeps_live_and_backtest_choices_separate(historical, expected):
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    options = PipelineLaunchOptions(ml_predict_batch_id="history", ml_live_predict_batch_id="live",
        ml_predict_use_historical_range=historical, ml_training_end_date="2025-12-31")
    command = build_pipeline_command("ml_predict", options)
    assert command[command.index("--batch-id") + 1] == expected
    assert Path(command[command.index("--artifacts-dir") + 1]).name == expected


def test_pipeline_does_not_duplicate_batch_directory():
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    command = build_pipeline_command("ml_predict", PipelineLaunchOptions(
        ml_predict_batch_id="batch", ml_artifacts_dir="artifacts/models/batch"))
    assert Path(command[command.index("--artifacts-dir") + 1]) == Path("artifacts/models/batch")
