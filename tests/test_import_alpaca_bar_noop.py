"""Sprint S2 / A-003 — verrouille la suppression du no-op silencieux.

Quand ``market_data.bars_provider != 'alpaca'``, ``import_alpaca_bar.main``
doit :
- logger un WARNING explicite,
- émettre un ``run_summary`` avec ``warning`` + ``skipped_reason='wrong_provider'``,
- retourner 0 (no-op contrôlé) sans tenter d'appel Alpaca.
"""
from __future__ import annotations

import io
import json
import logging
from contextlib import redirect_stdout

import pytest

from dataIntegrityEngine import import_alpaca_bar


@pytest.fixture()
def force_provider_eodhd(monkeypatch):
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "eodhd")
    yield


def _parse_emitted_summary(stdout: str) -> dict:
    prefix = import_alpaca_bar.RUN_SUMMARY_PREFIX
    lines = [ln for ln in stdout.splitlines() if ln.startswith(prefix)]
    assert lines, f"Aucune ligne run_summary émise (stdout={stdout!r})"
    return json.loads(lines[-1][len(prefix):])


def test_noop_emits_warning_log(force_provider_eodhd, caplog, monkeypatch):
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **_: None)
    caplog.set_level(logging.WARNING, logger=import_alpaca_bar.LOGGER.name)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = import_alpaca_bar.main([])
    assert rc == 0
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("no-op" in r.getMessage().lower() for r in warnings), (
        "Un WARNING explicite doit être loggé quand bars_provider != 'alpaca'."
    )


def test_noop_summary_contains_skipped_reason_and_warning(force_provider_eodhd, monkeypatch):
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **_: None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = import_alpaca_bar.main([])
    assert rc == 0
    payload = _parse_emitted_summary(buf.getvalue())
    assert payload.get("mode") == "noop"
    assert payload.get("warning") == "import_alpaca_bar_skipped_due_to_provider"
    assert payload.get("skipped_reason") == "wrong_provider"
    assert payload.get("bars_provider_active") == "eodhd"
    assert payload.get("targeted_symbols") == 0
    assert payload.get("inserted_bars") == 0


def test_noop_does_not_invoke_alpaca_fetch(force_provider_eodhd, monkeypatch):
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **_: None)

    def _boom(*_a, **_kw):  # pragma: no cover - safety net
        raise AssertionError("import_alpaca_bars ne doit pas être appelé en mode no-op.")

    monkeypatch.setattr(import_alpaca_bar, "import_alpaca_bars", _boom)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = import_alpaca_bar.main([])
    assert rc == 0


def test_provider_alpaca_runs_normally(monkeypatch):
    """Quand bars_provider=alpaca, on doit appeler ``import_alpaca_bars``."""
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "alpaca")
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **_: None)
    called = {}

    def _fake(time_frame, symbols=None):
        called["ok"] = True
        return {
            "run_id": "r1",
            "timeframe": time_frame.db_value,
            "targeted_symbols": 0,
            "successful_symbols": 0,
            "success_ratio": None,
        }

    monkeypatch.setattr(import_alpaca_bar, "import_alpaca_bars", _fake)
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = import_alpaca_bar.main([])
    assert rc == 0
    assert called.get("ok") is True
    payload = _parse_emitted_summary(buf.getvalue())
    assert payload.get("skipped_reason") != "wrong_provider"

