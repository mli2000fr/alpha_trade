from __future__ import annotations

from pathlib import Path

import yaml

from common.config_loader import load_batch_config, resolve_batch_config_path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "scripts" / "windows"
BATCH_SECTIONS = {
    "market_cap_sync",
    "earnings_calendar_sync",
    "analyst_snapshot_collection",
    "daily_bars_sync", "security_master_snapshot", "corporate_actions_sync",
    "sec_edgar_incremental", "pit_data_quality_daily", "borrow_status_snapshot",
    "business_quant_analyst_snapshot", "oracle_options_indicative_snapshot",
    "oracle_opening_window_sync", "sec_corporate_events_normalize",
    "sec_institutional_ownership_normalize", "fred_alfred_vintage_sync",
    "finra_short_volume_sync", "auction_imbalance_sync",
    "securities_lending_sync", "official_options_nbbo_sync",
}


def test_batch_configuration_is_separated_from_application_config() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    application = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

    assert set(batch) == BATCH_SECTIONS
    assert BATCH_SECTIONS.isdisjoint(application)
    assert load_batch_config() == batch
    assert resolve_batch_config_path() == ROOT / "batch.yaml"


def test_all_batch_launchers_and_installers_read_batch_yaml() -> None:
    files = (
        "market_cap_sync_launcher.ps1",
        "install_market_cap_sync_task.ps1",
        "earnings_calendar_launcher.ps1",
        "install_earnings_calendar_task.ps1",
        "analyst_snapshot_launcher.ps1",
        "install_analyst_snapshot_task.ps1",
        "forward_pit_launcher.ps1",
        "install_forward_pit_task.ps1",
        "install_all_forward_pit_tasks.ps1",
    )
    for name in files:
        content = (WINDOWS / name).read_text(encoding="utf-8")
        assert "batch.yaml" in content, name
        assert "config.yaml" not in content, name


def test_batch_uninstaller_is_scoped_and_preserves_data() -> None:
    content = (WINDOWS / "uninstall_scheduled_batch_task.ps1").read_text(encoding="utf-8")
    assert "ValidatePattern('^AlphaTrade-" in content
    assert "Unregister-ScheduledTask -TaskName $TaskName" in content
    assert "State -eq 'Running'" in content
    assert "données, journaux et la configuration batch.yaml sont conservés" in content


def test_installer_executable_lines_are_safe_for_windows_powershell_51() -> None:
    files = (
        "install_market_cap_sync_task.ps1",
        "install_earnings_calendar_task.ps1",
        "install_analyst_snapshot_task.ps1",
        "install_forward_pit_task.ps1",
        "uninstall_scheduled_batch_task.ps1",
        "market_cap_sync_launcher.ps1",
        "earnings_calendar_launcher.ps1",
        "analyst_snapshot_launcher.ps1",
        "forward_pit_launcher.ps1",
    )
    unsafe = set("—→←“”‘’")
    for name in files:
        lines = (WINDOWS / name).read_text(encoding="utf-8").splitlines()
        executable_lines = (line for line in lines if not line.lstrip().startswith("#"))
        assert not any(character in line for line in executable_lines for character in unsafe), name


def test_every_batch_has_ui_catalogue_metadata() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    for name, config in batch.items():
        assert config.get("priority") in {"P0", "P1", "P2", "P3", "P4"}, name
        assert str(config.get("description") or "").strip(), name
        assert "tables" in config, name
        if not config.get("enabled", True):
            assert str(config.get("activation_requirement") or "").strip(), name
            assert len(config.get("unlock_steps") or []) >= 2, name


def test_every_symbol_scoped_batch_uses_stable_tradable_universe() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    expected = "config/univers_batch/univers_filtred_tradable.txt"
    names = (
        "market_cap_sync",
        "earnings_calendar_sync",
        "analyst_snapshot_collection",
        "daily_bars_sync",
        "pit_data_quality_daily",
        "borrow_status_snapshot",
        "business_quant_analyst_snapshot",
        "oracle_options_indicative_snapshot",
        "oracle_opening_window_sync",
        "finra_short_volume_sync",
        "auction_imbalance_sync",
        "securities_lending_sync",
        "official_options_nbbo_sync",
    )
    for name in names:
        assert batch[name]["symbols_file"] == expected
        assert "max_symbols" not in batch[name]


def test_options_batch_is_active_research_only_and_never_top20_scoped() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    options = batch["oracle_options_indicative_snapshot"]
    assert options["enabled"] is True
    assert options["status"] == "ACTIVE_RESEARCH_ONLY"
    assert options["provider"] == "alpaca"
    assert options["feed"] == "indicative"
    assert options["symbols_file"] == "config/univers_batch/univers_filtred_tradable.txt"
    assert options["target_dtes"] == "5,10,20"
    assert "max_symbols" not in options
    assert "oracle_batch_id" not in options


def test_non_symbol_batches_declare_why_they_are_not_universe_filtered() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    expected_scopes = {
        "security_master_snapshot": "market_wide_discovery",
        "corporate_actions_sync": "market_wide",
        "sec_edgar_incremental": "market_wide_filings",
        "sec_corporate_events_normalize": "raw_sec_filings",
        "sec_institutional_ownership_normalize": "raw_sec_filings",
        "fred_alfred_vintage_sync": "macro_series",
    }
    for name, scope in expected_scopes.items():
        assert batch[name]["universe_scope"] == scope
        assert "symbols_file" not in batch[name]


def test_generic_powershell_scripts_preserve_python_utf8_literal() -> None:
    for name in ("install_forward_pit_task.ps1", "forward_pit_launcher.ps1"):
        content = (WINDOWS / name).read_text(encoding="utf-8")
        assert "encoding=''utf-8''" in content, name
        assert 'encoding="utf-8"' not in content, name


def test_generic_powershell_scripts_guard_optional_batch_properties() -> None:
    installer = (WINDOWS / "install_forward_pit_task.ps1").read_text(encoding="utf-8")
    launcher = (WINDOWS / "forward_pit_launcher.ps1").read_text(encoding="utf-8")
    assert "function Get-ConfigValue" in installer
    assert "Get-ConfigValue $cfg 'run_minutes' ''" in installer
    assert "function Get-ConfigValue" in launcher
    for field in ("log_file", "enabled", "status", "timezone", "run_days", "run_hours", "run_minutes"):
        assert f"Get-ConfigValue $cfg '{field}'" in launcher
