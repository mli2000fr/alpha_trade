"""Offline regressions: weekend and midnight must not split Oracle/GPT dates."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import sys
from types import SimpleNamespace

import pytest

from common import us_signal_date as session
from service.llm_directional.runner import validate_analysis_window


SATURDAY = datetime(2026, 10, 10, 10, tzinfo=timezone.utc)


@pytest.fixture
def saturday(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return SATURDAY.astimezone(tz) if tz else SATURDAY.replace(tzinfo=None)
    monkeypatch.setattr(session, "datetime", Clock)


@pytest.mark.parametrize("requested,now,expected", [
    ("2026-10-10", SATURDAY, "2026-10-09"),
    ("2026-10-11", datetime(2026,10,11,18,tzinfo=timezone.utc), "2026-10-09"),
    (None, SATURDAY, "2026-10-09"),
    ("2026-10-09", SATURDAY, "2026-10-09"),
    ("2026-10-12", datetime(2026,10,12,6,tzinfo=timezone.utc), "2026-10-09"),
    ("2026-10-09", datetime(2026,10,9,22,tzinfo=timezone.utc), "2026-10-09"),
    ("2026-10-10", datetime(2026,10,9,22,30,tzinfo=timezone.utc), "2026-10-09"),
    ("2026-10-12", datetime(2026,10,11,22,30,tzinfo=timezone.utc), "2026-10-09"),
    ("2026-10-13", datetime(2026,10,12,22,30,tzinfo=timezone.utc), "2026-10-12"),
    ("2026-10-10", datetime(2026,10,12,22,tzinfo=timezone.utc), "2026-10-09"),
    ("2026-11-26", datetime(2026,11,26,22,tzinfo=timezone.utc), "2026-11-25"),
    ("2026-11-27", datetime(2026,11,27,19,tzinfo=timezone.utc), "2026-11-27"),
    ("2026-11-30", datetime(2026,11,30,7,tzinfo=timezone.utc), "2026-11-27"),
    ("2026-11-28", datetime(2026,11,27,23,30,tzinfo=timezone.utc), "2026-11-27"),
    ("2026-10-12", SATURDAY, "2026-10-12"),  # Future is not rewritten to now.
])
def test_signal_date_uses_sessions_not_weekdays(requested, now, expected):
    assert session.resolve_us_signal_date(requested, now=now) == date.fromisoformat(expected)


@pytest.mark.parametrize("now", [
    SATURDAY,
    datetime(2026,10,11,18,tzinfo=timezone.utc),
    datetime(2026,10,12,6,tzinfo=timezone.utc),
])
def test_weekend_until_monday_preopen_is_valid(now):
    day = session.resolve_us_signal_date(None, now=now)
    assert day == date(2026,10,9)
    validate_analysis_window(day, now=now)


def test_explicit_old_date_is_not_advanced_to_hide_expiry():
    now = datetime(2026,10,12,14,tzinfo=timezone.utc)
    day = session.resolve_us_signal_date("2026-10-10", now=now)
    assert day == date(2026,10,9)
    with pytest.raises(ValueError, match="déjà ouvert"):
        validate_analysis_window(day, now=now)


def test_preclose_current_session_and_naive_clock_are_rejected():
    now = datetime(2026,10,9,19,tzinfo=timezone.utc)
    day = session.resolve_us_signal_date("2026-10-09", now=now)
    with pytest.raises(ValueError, match="clôture"):
        validate_analysis_window(day, now=now)
    with pytest.raises(ValueError, match="timezone"):
        session.resolve_us_signal_date(now=datetime(2026,10,10,12))


@pytest.mark.parametrize("phase,flag", [("predict", "--universe-date"), ("risk", "--trade-date"), ("execute", "--date")])
def test_pin_removes_duplicate_and_equal_style_flags(phase, flag):
    command = session.pin_command_date(["python", flag, "2026-10-10", f"{flag}=2026-10-11"], phase, "2026-10-09")
    assert command == ["python", flag, "2026-10-09"]


def test_pin_rejects_a_missing_flag_value():
    with pytest.raises(ValueError, match="Valeur manquante"):
        session.pin_command_date(["python", "--universe-date"], "predict", "2026-10-09")


@pytest.mark.parametrize("step,flag", [("ml_predict", "--universe-date"), ("risk_management", "--trade-date"), ("execution", "--date")])
def test_ihm_outer_and_inner_commands_have_same_friday(step, flag, saturday):
    from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
    options = PipelineLaunchOptions(llm_filter_enabled=True, ml_predict_batch_id="oracle-batch",
        trade_date="2026-10-10", llm_filter_run_id="llm-exact")
    wrapped = build_pipeline_command(step, options)
    inner = json.loads(wrapped[wrapped.index("--command-json")+1])
    assert wrapped[wrapped.index("--trade-date")+1] == "2026-10-09"
    assert inner.count(flag) == 1
    assert inner[inner.index(flag)+1] == "2026-10-09"
    assert wrapped[wrapped.index("--run-id")+1] == "llm-exact"
    if step == "execution":
        assert inner[3] == "paper"


def test_predict_pipeline_prechecks_and_pins_before_oracle(monkeypatch, saturday):
    from service.llm_directional import pipeline
    import database.connection as connection
    calls = []
    monkeypatch.setattr(pipeline, "validate_analysis_window", lambda day: calls.append(("validate", day)))
    monkeypatch.setattr(pipeline, "assert_paper_account", lambda: None)
    monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(pipeline, "Repository", lambda engine: object())
    monkeypatch.setattr(pipeline.subprocess, "run", lambda command, **kw: calls.append(("oracle", command)))
    monkeypatch.setattr(pipeline, "analyze", lambda **kw: calls.append(("gpt", kw["trade_date"])) or {"status": "completed"})
    import database.run_business_summaries as summaries
    monkeypatch.setattr(summaries, "emit_run_summary", lambda summary: None)
    monkeypatch.setattr(sys, "argv", ["pipeline", "--phase", "predict", "--run-id", "llm-test",
        "--trade-date", "2026-10-10", "--batch-id", "oracle-batch", "--command-json",
        json.dumps([sys.executable, "-u", "-m", "modelFactory", "--mode", "predict"])])
    pipeline.main()
    assert calls[0] == ("validate", date(2026,10,9))
    command = calls[1][1]
    assert command[command.index("--universe-date")+1] == "2026-10-09"
    assert calls[2] == ("gpt", "2026-10-09")


def test_predict_preflight_failure_never_touches_db_or_oracle(monkeypatch, saturday):
    from service.llm_directional import pipeline
    import database.connection as connection
    def reject(day):
        raise ValueError("séance suivante déjà ouverte")
    monkeypatch.setattr(pipeline, "validate_analysis_window", reject)
    monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: pytest.fail("No DB"))
    monkeypatch.setattr(pipeline.subprocess, "run", lambda *a, **k: pytest.fail("No Oracle"))
    monkeypatch.setattr(pipeline, "assert_paper_account", lambda: pytest.fail("No broker"))
    monkeypatch.setattr(sys, "argv", ["pipeline", "--phase", "predict", "--run-id", "llm-test",
        "--trade-date", "2026-10-10", "--batch-id", "oracle-batch", "--command-json",
        json.dumps([sys.executable, "-u", "-m", "modelFactory", "--mode", "predict"])])
    with pytest.raises(ValueError, match="déjà ouverte"):
        pipeline.main()


def test_failed_oracle_subprocess_never_calls_gpt(monkeypatch, saturday):
    from service.llm_directional import pipeline
    import database.connection as connection
    import subprocess
    monkeypatch.setattr(pipeline, "validate_analysis_window", lambda day: None)
    monkeypatch.setattr(pipeline, "assert_paper_account", lambda: None)
    monkeypatch.setattr(connection, "get_sqlalchemy_engine", lambda: object())
    monkeypatch.setattr(pipeline, "Repository", lambda engine: object())
    def fail(command, **kwargs):
        assert kwargs["check"] is True
        raise subprocess.CalledProcessError(2, command)
    monkeypatch.setattr(pipeline.subprocess, "run", fail)
    monkeypatch.setattr(pipeline, "analyze", lambda **kw: pytest.fail("No GPT after Oracle failure"))
    monkeypatch.setattr(sys, "argv", ["pipeline", "--phase", "predict", "--run-id", "llm-test",
        "--trade-date", "2026-10-10", "--batch-id", "oracle-batch", "--command-json",
        json.dumps([sys.executable, "-u", "-m", "modelFactory", "--mode", "predict"])])
    with pytest.raises(subprocess.CalledProcessError):
        pipeline.main()


def test_manual_registry_freezes_session_before_command(monkeypatch, saturday):
    from ihm.services import process_registry
    from ihm.services.pipeline_runner import PipelineLaunchOptions
    monkeypatch.setattr(process_registry, "start_managed_run", lambda **kwargs: kwargs)
    result = process_registry.start_pipeline_run("ml_predict", "10. ML Predict",
        PipelineLaunchOptions(llm_filter_enabled=True, ml_predict_batch_id="oracle-batch",
            trade_date="2026-10-10"))
    command = result["command"]
    inner = json.loads(command[command.index("--command-json") + 1])
    assert command[command.index("--trade-date") + 1] == "2026-10-09"
    assert inner[inner.index("--universe-date") + 1] == "2026-10-09"


@pytest.mark.parametrize("outcome", [
    {"status": "error", "reason": "no_predictions"},
    {"status": "completed", "n_rows": 0},
])
def test_oracle_cli_weekend_is_friday_and_zero_rows_is_failure(monkeypatch, saturday, outcome):
    from modelFactory import cli, db_registry, predictor
    from modelFactory.oracle import predict_history, predictions_store
    calls = []
    class Engine:
        @contextmanager
        def connect(self):
            yield self
        def execute(self, *a, **k):
            return SimpleNamespace(scalar=lambda: 0)
    monkeypatch.setattr(cli, "get_sqlalchemy_engine", lambda: Engine())
    monkeypatch.setattr(cli, "configure_root_logging", lambda **k: None)
    monkeypatch.setattr(cli, "apply_reproducibility", lambda *a, **k: {})
    monkeypatch.setattr(db_registry, "detect_batch_training_mode", lambda *a: "per_symbol")
    monkeypatch.setattr(db_registry, "load_symbols_for_source", lambda *a, **k: calls.append(("universe", k["trade_date"])) or ["AAPL"])
    monkeypatch.setattr(predictor, "_batch_has_per_symbol_or_sector", lambda *a: False)
    monkeypatch.setattr(predictor, "_directional_bundle_root", lambda *a: None)
    monkeypatch.setattr(predict_history, "has_oracle_champions", lambda *a: True)
    monkeypatch.setattr(predict_history, "predict_oracle_extreme_history", lambda engine, batch, start, end, **kw: calls.append(("oracle", start, end)) or outcome)
    monkeypatch.setattr(predictions_store, "load_oracle_predictions", lambda *a, **k: pytest.fail("No stale reload"))
    with pytest.raises(SystemExit) as exc:
        cli.main(["--mode", "predict", "--batch-id", "oracle-batch", "--universe-date", "2026-10-10"])
    assert exc.value.code == 2
    assert calls == [("universe", date(2026,10,9)), ("oracle", "2026-10-09", "2026-10-09")]
