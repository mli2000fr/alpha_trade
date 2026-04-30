"""IHM provider switch (Phase 6 plan §5.6 + addendum 2026-04-29).

Vérifie que l'étape pipeline ``import_alpaca_bar`` route dynamiquement vers
``import_eodhd_bar`` quand ``market_data.bars_provider == 'eodhd'``.
"""
from __future__ import annotations

from ihm.services import pipeline_runner
from ihm.services import process_registry


def test_resolve_bars_provider_default_alpaca(monkeypatch):
    monkeypatch.setattr(
        "common.config_loader.load_config",
        lambda: {"market_data": {"bars_provider": "alpaca"}},
    )
    assert pipeline_runner._resolve_bars_provider_for_ihm() == "alpaca"


def test_resolve_bars_provider_eodhd(monkeypatch):
    monkeypatch.setattr(
        "common.config_loader.load_config",
        lambda: {"market_data": {"bars_provider": "EODHD"}},
    )
    assert pipeline_runner._resolve_bars_provider_for_ihm() == "eodhd"


def test_resolve_bars_provider_config_failure_falls_back_to_alpaca(monkeypatch):
    def _boom():
        raise RuntimeError("config indispo")
    monkeypatch.setattr("common.config_loader.load_config", _boom)
    assert pipeline_runner._resolve_bars_provider_for_ihm() == "alpaca"


def test_pipeline_command_for_alpaca_uses_alpaca_module(monkeypatch):
    """Quand provider=alpaca, l'étape import_alpaca_bar appelle bien le module Alpaca."""
    monkeypatch.setattr(pipeline_runner, "_resolve_bars_provider_for_ihm", lambda: "alpaca")
    cmd = _build_command(monkeypatch, "import_alpaca_bar")
    assert cmd[-1] == "dataIntegrityEngine.import_alpaca_bar"
    assert "--write" not in cmd


def test_pipeline_command_for_eodhd_routes_to_eodhd_module(monkeypatch):
    """Phase 6 : provider=eodhd -> import_eodhd_bar --write."""
    monkeypatch.setattr(pipeline_runner, "_resolve_bars_provider_for_ihm", lambda: "eodhd")
    cmd = _build_command(monkeypatch, "import_alpaca_bar")
    assert "dataIntegrityEngine.import_eodhd_bar" in cmd
    assert "--write" in cmd


# ---------------------------------------------------------------------------
# Étape auxiliaire B3 — backfill historique EODHD
# ---------------------------------------------------------------------------


def test_eodhd_backfill_history_step_is_registered():
    aux_keys = [s.key for s in pipeline_runner.get_pipeline_auxiliary_steps()]
    assert "eodhd_backfill_history" in aux_keys


def test_eodhd_backfill_history_default_command_is_write():
    from ihm.services.pipeline_runner import (
        PipelineLaunchOptions,
        build_pipeline_command,
    )
    cmd = build_pipeline_command("eodhd_backfill_history", PipelineLaunchOptions())
    assert "dataIntegrityEngine.backfill_eodhd_history" in cmd
    assert "--years" in cmd
    assert "30" in cmd  # default years
    assert "--write" in cmd
    assert "--resume" in cmd


def test_eodhd_backfill_history_write_mode_with_explicit_symbols():
    from ihm.services.pipeline_runner import (
        PipelineLaunchOptions,
        build_pipeline_command,
    )
    options = PipelineLaunchOptions(
        eodhd_backfill_years=10,
        eodhd_backfill_symbols="AAPL, NVDA, MSFT",
        eodhd_backfill_resume=False,
        eodhd_backfill_write=True,
    )
    cmd = build_pipeline_command("eodhd_backfill_history", options)
    assert "--write" in cmd
    assert "--no-resume" in cmd
    assert "10" in cmd
    assert "--symbols" in cmd
    assert "AAPL" in cmd and "NVDA" in cmd and "MSFT" in cmd


def test_start_pipeline_run_for_b3_propagates_write_flag(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_start_managed_run(**kwargs):
        captured.update(kwargs)

        class _Record:
            run_id = "test-run"

        return _Record()

    monkeypatch.setattr(process_registry, "start_managed_run", _fake_start_managed_run)

    from ihm.services.pipeline_runner import PipelineLaunchOptions

    options = PipelineLaunchOptions(
        eodhd_backfill_write=True,
        eodhd_backfill_resume=True,
        eodhd_backfill_years=5,
    )
    process_registry.start_pipeline_run(
        "eodhd_backfill_history",
        "B3. Backfill historique EODHD",
        options,
    )

    command = captured["command"]
    assert isinstance(command, list)
    assert "dataIntegrityEngine.backfill_eodhd_history" in command
    assert "--write" in command
    assert "--resume" in command


def test_corporate_actions_step_description_mentions_provider_routing():
    """La description IHM ne doit plus dire 'Alpaca uniquement' (Phase 6)."""
    steps = {s.key: s for s in pipeline_runner.get_pipeline_steps()}
    desc = steps["corporate_actions_sync"].desc.lower()
    assert "alpaca uniquement" not in desc
    assert "eodhd" in desc


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_command(monkeypatch, step_key: str) -> list[str]:
    from ihm.services.pipeline_runner import (
        PipelineLaunchOptions,
        build_pipeline_command,
    )
    options = PipelineLaunchOptions()
    return build_pipeline_command(step_key, options)


