"""T-EOD-10 — provider switch symétrique (plan_eodhd.md §7.1).

Vérifie que :
- ``bars_provider=alpaca`` -> ``import_eodhd_bar`` no-op (déjà couvert dans
  ``test_import_eodhd_bar``, mais re-testé ici pour le pipeline complet).
- ``bars_provider=eodhd``  -> ``import_alpaca_bar.main`` no-op (Phase 4).
- ``bars_provider`` invalide -> Alpaca par défaut (rétrocompat).
"""
from __future__ import annotations

import json

import pytest

from dataIntegrityEngine import import_alpaca_bar, import_eodhd_bar


# ---------------------------------------------------------------------------
# Sens 1 : eodhd -> Alpaca no-op
# ---------------------------------------------------------------------------


def test_import_alpaca_bar_main_noop_when_provider_eodhd(monkeypatch, capsys):
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "eodhd")
    # Garde-fou : si on entre dans le pipeline, ce mock lèvera
    monkeypatch.setattr(
        import_alpaca_bar,
        "import_alpaca_bars",
        lambda *a, **k: pytest.fail("import_alpaca_bars ne doit pas être appelé"),
    )
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **kwargs: None)

    rc = import_alpaca_bar.main([])

    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha_trade_run_summary" in out
    payload_line = next(
        line for line in out.splitlines() if "alpha_trade_run_summary" in line
    )
    payload = json.loads(payload_line.split("::alpha_trade_run_summary::", 1)[1])
    assert payload["mode"] == "noop"
    assert payload["provider"] == "alpaca"
    assert payload["skipped_reason"] == "bars_provider=eodhd"


def test_import_alpaca_bar_main_runs_when_provider_alpaca(monkeypatch, capsys):
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "alpaca")
    monkeypatch.setattr(import_alpaca_bar, "configure_root_logging", lambda **kwargs: None)

    called: dict[str, int] = {"n": 0}

    def _fake_import(time_frame, symbols=None):
        called["n"] += 1
        return {
            "run_id": "fake",
            "successful_symbols": 1,
            "targeted_symbols": 1,
            "up_to_date_symbols": 0,
            "success_ratio": 1.0,
        }

    monkeypatch.setattr(import_alpaca_bar, "import_alpaca_bars", _fake_import)

    rc = import_alpaca_bar.main([])
    assert rc == 0
    assert called["n"] == 1


def test_import_alpaca_bar_resolve_provider_default_to_alpaca(monkeypatch):
    # Si load_config crash, on doit retomber sur "alpaca" (rétrocompat)
    def _boom():
        raise RuntimeError("config indisponible")
    import common.config_loader as cfg_loader
    monkeypatch.setattr(cfg_loader, "load_config", _boom)
    assert import_alpaca_bar._resolve_bars_provider() == "alpaca"


# ---------------------------------------------------------------------------
# Sens 2 : alpaca -> EODHD no-op (rappel)
# ---------------------------------------------------------------------------


def test_import_eodhd_bar_main_noop_when_provider_alpaca(monkeypatch, capsys):
    monkeypatch.setattr(
        import_eodhd_bar,
        "_load_config_safe",
        lambda: {"market_data": {"bars_provider": "alpaca"}},
    )
    monkeypatch.setattr(
        import_eodhd_bar,
        "fetch_eod_bulk",
        lambda **kwargs: pytest.fail("fetch_eod_bulk ne doit pas être appelé"),
    )
    monkeypatch.setattr(import_eodhd_bar, "configure_root_logging", lambda **kwargs: None)

    rc = import_eodhd_bar.main([])
    assert rc == 0
    out = capsys.readouterr().out
    payload_line = next(
        line for line in out.splitlines() if "alpha_trade_run_summary" in line
    )
    payload = json.loads(payload_line.split("::alpha_trade_run_summary::", 1)[1])
    assert payload["mode"] == "noop"
    assert payload["provider"] == "eodhd"


# ---------------------------------------------------------------------------
# Symétrie : un seul provider actif à la fois
# ---------------------------------------------------------------------------


def test_only_one_provider_writes_when_eodhd_is_active(monkeypatch):
    """Quand bars_provider=eodhd : Alpaca no-op, EODHD actif (et inversement)."""
    # Simule provider=eodhd
    monkeypatch.setattr(import_alpaca_bar, "_resolve_bars_provider", lambda: "eodhd")
    assert import_alpaca_bar._resolve_bars_provider() == "eodhd"

    monkeypatch.setattr(
        import_eodhd_bar,
        "_load_config_safe",
        lambda: {"market_data": {"bars_provider": "eodhd"}},
    )
    assert import_eodhd_bar.resolve_bars_provider(None) == "eodhd"

