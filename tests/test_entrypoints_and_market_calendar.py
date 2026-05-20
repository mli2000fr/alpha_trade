from __future__ import annotations

import importlib.util
import runpy
import subprocess
import sys
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

import common.market_calendar as market_calendar
import corporate_actions.cli
import event_sentiment.cli
import execution_engine.cli
import risk_management.cli
from backtesting import cli as backtesting_cli

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_PY_PATH = str(PROJECT_ROOT / "run.py")
STREAMLIT_APP_PATH = str(PROJECT_ROOT / "ihm" / "app.py")


def test_is_trading_day_falls_back_to_weekday_logic_when_calendar_missing(monkeypatch) -> None:
    monkeypatch.setattr(market_calendar, "_get_nyse_calendar", lambda: None)

    assert market_calendar.is_trading_day(date(2026, 4, 29)) is True
    assert market_calendar.is_trading_day(date(2026, 5, 2)) is False


def test_nyse_session_dates_uses_calendar_schedule_when_available(monkeypatch) -> None:
    class _FakeCalendar:
        def schedule(self, start_date, end_date):
            assert start_date == date(2026, 4, 27)
            assert end_date == date(2026, 4, 29)
            return pd.DataFrame(index=pd.to_datetime(["2026-04-27", "2026-04-28", "2026-04-29"]))

    monkeypatch.setattr(market_calendar, "_get_nyse_calendar", lambda: _FakeCalendar())

    sessions = market_calendar.nyse_session_dates(date(2026, 4, 27), date(2026, 4, 29))

    assert sessions == [date(2026, 4, 27), date(2026, 4, 28), date(2026, 4, 29)]


def test_get_last_date_marche_walks_back_until_previous_open_day(monkeypatch) -> None:
    monkeypatch.setattr(market_calendar, "is_trading_day", lambda d: d.weekday() < 5)

    assert market_calendar.getLastDateMarche(date(2026, 5, 4)) == date(2026, 5, 1)


def test_backtesting_dunder_main_invokes_cli_main(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(backtesting_cli, "main", lambda: calls.append("called"))

    runpy.run_module("backtesting.__main__", run_name="__main__")

    assert calls == ["called"]


def test_corporate_actions_dunder_main_invokes_cli_main(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(corporate_actions.cli, "main", lambda: calls.append("called"))

    runpy.run_module("corporate_actions.__main__", run_name="__main__")

    assert calls == ["called"]


def test_event_sentiment_dunder_main_invokes_cli_main(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(event_sentiment.cli, "main", lambda: calls.append("called"))

    runpy.run_module("event_sentiment.__main__", run_name="__main__")

    assert calls == ["called"]


def test_execution_engine_dunder_main_invokes_cli_main(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(execution_engine.cli, "main", lambda: calls.append("called"))

    runpy.run_module("execution_engine.__main__", run_name="__main__")

    assert calls == ["called"]


def test_risk_management_dunder_main_exits_with_cli_return_code(monkeypatch) -> None:
    monkeypatch.setattr(risk_management.cli, "main", lambda: 7)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_module("risk_management.__main__", run_name="__main__")

    assert exc_info.value.code == 7


def test_run_py_launches_streamlit_app(monkeypatch) -> None:
    calls: list[tuple[list[str], bool, str | None]] = []
    sleep_guard_calls: list[str] = []

    @contextmanager
    def _fake_prevent_windows_sleep():
        sleep_guard_calls.append("enter")
        try:
            yield True
        finally:
            sleep_guard_calls.append("exit")

    def _fake_run(command: list[str], check: bool, cwd: str | None = None) -> None:
        calls.append((command, check, cwd))
        return None

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "streamlit" else None)
    monkeypatch.setattr("common.windows_sleep_guard.prevent_windows_sleep", _fake_prevent_windows_sleep)
    monkeypatch.setattr(subprocess, "run", _fake_run)

    runpy.run_path(RUN_PY_PATH, run_name="__main__")

    assert calls == [([
        sys.executable,
        "-m",
        "streamlit",
        "run",
        STREAMLIT_APP_PATH,
    ], True, str(PROJECT_ROOT))]
    assert sleep_guard_calls == ["enter", "exit"]


def test_run_py_exits_with_clear_message_when_streamlit_is_missing(monkeypatch, capsys) -> None:
    @contextmanager
    def _fake_prevent_windows_sleep():
        yield True

    calls: list[str] = []

    def _fake_run(command: list[str], check: bool, cwd: str | None = None) -> None:
        calls.append("called")

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None if name == "streamlit" else None)
    monkeypatch.setattr("common.windows_sleep_guard.prevent_windows_sleep", _fake_prevent_windows_sleep)
    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(RUN_PY_PATH, run_name="__main__")

    assert exc_info.value.code == 1
    assert "Streamlit n'est pas installé" in capsys.readouterr().out
    assert calls == []


def test_run_py_propagates_streamlit_process_return_code(monkeypatch, capsys) -> None:
    @contextmanager
    def _fake_prevent_windows_sleep():
        yield True

    def _raise_failure(command: list[str], check: bool, cwd: str | None = None) -> None:
        raise subprocess.CalledProcessError(returncode=3, cmd=command)

    monkeypatch.setattr(importlib.util, "find_spec", lambda name: object() if name == "streamlit" else None)
    monkeypatch.setattr("common.windows_sleep_guard.prevent_windows_sleep", _fake_prevent_windows_sleep)
    monkeypatch.setattr(subprocess, "run", _raise_failure)

    with pytest.raises(SystemExit) as exc_info:
        runpy.run_path(RUN_PY_PATH, run_name="__main__")

    assert exc_info.value.code == 3
    assert "Lancement Streamlit échoué" in capsys.readouterr().out

