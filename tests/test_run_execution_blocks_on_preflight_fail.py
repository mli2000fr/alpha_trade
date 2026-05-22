"""S11.4 — Régression : `run_execution.run("live", ...)` doit refuser de démarrer
si `run_preflight` retourne `passed=False`.

Couvre :
- Mode live + preflight failed → `SystemExit(2)` et aucun ordre soumis.
- Mode live + preflight OK → continue (échoue plus loin sur l'absence de DB
  réelle, ce qu'on intercepte explicitement).
- Mode live + `--skip-preflight` → ne lance pas le preflight, continue.
- Mode paper → preflight non lancé.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest


@pytest.fixture
def run_execution_module(monkeypatch, tmp_path):
    """Charge `run_execution` avec PROJECT_ROOT redirigé vers tmp_path."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    monkeypatch.setenv("LOGIN_DB", "x")
    monkeypatch.setenv("PASSWORD_DB", "y")
    monkeypatch.setenv("ALPHA_TRADE_LIVE_SECRET_POLICY", "env")
    if "run_execution" in sys.modules:
        del sys.modules["run_execution"]
    import run_execution

    monkeypatch.setattr(run_execution, "PROJECT_ROOT", tmp_path)
    # Évite l'I/O DB et bypass abort_missing_env / configure_root_logging.
    monkeypatch.setattr(run_execution, "abort_missing_env", lambda **kw: None)
    monkeypatch.setattr(run_execution, "configure_root_logging", lambda **kw: None)
    return run_execution


def _make_fake_preflight(passed: bool):
    """Construit un module fake `execution_engine.preflight` pour DI."""

    class _Check:
        def __init__(self, name, status, message):
            self.name = name
            self.status = status
            self.message = message

    class _Report:
        def __init__(self, ok: bool):
            self.passed = ok
            self.checks = (
                [_Check("env_db", "ok", "ok")]
                if ok
                else [_Check("alpaca_key", "fail", "missing ALPACA_API_KEY")]
            )

        def to_dict(self):
            return {"passed": self.passed, "checks": [c.__dict__ for c in self.checks]}

    fake_module = types.ModuleType("execution_engine.preflight")
    fake_module.run_preflight = lambda **kw: _Report(passed)
    return fake_module


def test_run_aborts_on_preflight_fail(run_execution_module, monkeypatch):
    fake_preflight = _make_fake_preflight(passed=False)
    monkeypatch.setitem(sys.modules, "execution_engine.preflight", fake_preflight)

    with pytest.raises(SystemExit) as excinfo:
        run_execution_module.run(
            mode="live",
            run_id=None,
            trade_date=None,
            debug=False,
            account_id="default",
        )
    assert excinfo.value.code == 2


def test_skip_preflight_flag_bypasses_check(run_execution_module, monkeypatch, capsys):
    """Avec skip_preflight=True, on ne lance PAS run_preflight."""
    called = {"n": 0}

    def _spy(**kw):
        called["n"] += 1
        raise AssertionError("ne devrait pas être appelé")

    fake_module = types.ModuleType("execution_engine.preflight")
    fake_module.run_preflight = _spy
    monkeypatch.setitem(sys.modules, "execution_engine.preflight", fake_module)
    monkeypatch.setenv("ALPHA_TRADE_LIVE_APPROVAL_TOKEN", "test-token")
    import execution_engine.db_io as execution_db_io

    def _stop_repo(*args, **kwargs):
        raise RuntimeError("stop after skip-preflight")

    monkeypatch.setattr(execution_db_io, "ExecutionRepository", _stop_repo)

    # On force un arrêt déterministe juste après la branche preflight.
    with pytest.raises(RuntimeError, match="stop after skip-preflight"):
        run_execution_module.run(
            mode="live",
            run_id=None,
            trade_date=None,
            debug=False,
            account_id="default",
            skip_preflight=True,
            approval_token="test-token",
        )
    assert called["n"] == 0
    err = capsys.readouterr().err
    assert "skip-preflight" in err.lower() or "checks live sont contourn" in err.lower()


def test_paper_mode_does_not_invoke_preflight(run_execution_module, monkeypatch):
    """En paper mode, le preflight live n'est jamais lancé (vérifié par inspection
    du code path : la branche n'est traversée que si ``mode == 'live'``).

    On utilise un fake `run_preflight` qui set un flag ; même si la suite plante
    plus tard sur un I/O DB, le flag doit rester False.
    """
    called = {"n": 0}

    def _spy(**kw):
        called["n"] += 1
        return type("R", (), {"passed": True, "checks": [], "to_dict": lambda self: {}})()

    fake_module = types.ModuleType("execution_engine.preflight")
    fake_module.run_preflight = _spy
    monkeypatch.setitem(sys.modules, "execution_engine.preflight", fake_module)
    import execution_engine.db_io as execution_db_io

    def _stop_repo(*args, **kwargs):
        raise RuntimeError("stop in paper mode")

    monkeypatch.setattr(execution_db_io, "ExecutionRepository", _stop_repo)

    with pytest.raises(RuntimeError, match="stop in paper mode"):
        run_execution_module.run(
            mode="paper",
            run_id=None,
            trade_date=None,
            debug=False,
            account_id="default",
        )
    assert called["n"] == 0, "preflight ne doit pas être invoqué en mode paper"


def test_simulate_mode_warns_on_preflight_fail_but_does_not_abort(run_execution_module, monkeypatch, capsys):
    fake_preflight = _make_fake_preflight(passed=False)
    monkeypatch.setitem(sys.modules, "execution_engine.preflight", fake_preflight)
    import execution_engine.db_io as execution_db_io

    def _stop_repo(*args, **kwargs):
        raise RuntimeError("stop after simulate-preflight")

    monkeypatch.setattr(execution_db_io, "ExecutionRepository", _stop_repo)

    with pytest.raises(RuntimeError, match="stop after simulate-preflight"):
        run_execution_module.run(
            mode="simulate",
            run_id=None,
            trade_date=None,
            debug=False,
            account_id="default",
        )

    err = capsys.readouterr().err
    assert "Preflight simulate en mode dégradé" in err
    assert "[WARN]" in err


