from __future__ import annotations

from pathlib import Path

import yaml

from common.config_loader import load_batch_config, resolve_batch_config_path

ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "scripts" / "windows"
BATCH_SECTIONS = {
    "ml_artifacts_backup",
    "db_core_backup", "db_news_raw_backup",
    "market_cap_sync",
    "earnings_calendar_sync",
    "latest_quotes_sync",
    "analyst_snapshot_collection",
    "daily_bars_sync", "security_master_snapshot", "corporate_actions_sync",
    "sec_edgar_incremental", "pit_data_quality_daily", "borrow_status_snapshot",
    "business_quant_analyst_snapshot", "oracle_options_indicative_snapshot",
    "oracle_opening_window_sync", "sec_corporate_events_normalize",
    "sec_institutional_ownership_normalize", "fred_alfred_vintage_sync",
    "finra_short_volume_sync", "auction_imbalance_sync",
    "securities_lending_sync", "official_options_nbbo_sync",
    "options_delayed_bars_sync", "option_contract_adjustment_sync",
}


def test_batch_configuration_is_separated_from_application_config() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    application = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))

    assert set(batch) == BATCH_SECTIONS
    assert BATCH_SECTIONS.isdisjoint(application)
    assert load_batch_config() == batch
    assert resolve_batch_config_path() == ROOT / "batch.yaml"
    assert "RETAILSMSA" in batch["fred_alfred_vintage_sync"]["series"].split(",")
    assert "RETAILSMS" not in batch["fred_alfred_vintage_sync"]["series"].split(",")
    quality = batch["pit_data_quality_daily"]
    assert quality["enabled"] is False
    assert quality["status"] == "MANUAL_CONTROL_ONLY"
    assert "aucune donnée externe" in quality["description"]
    assert quality["supervision_dependencies"].split(",") == [
        "sec_edgar_incremental",
        "finra_short_volume_sync",
        "fred_alfred_vintage_sync",
    ]
    assert "peuvent tourner en parallèle" in quality["execution_notice"]
    assert "après leur fin" in quality["execution_notice"]
    sec = batch["sec_edgar_incremental"]
    assert sec["download_primary_documents"] is True
    assert sec["download_exhibits"] is True
    assert sec["exhibit_type_prefixes"] == "EX-99"
    assert sec["max_exhibits_per_filing"] > 0
    assert sec["max_exhibit_bytes"] < 64 * 1024 * 1024
    assert "pas encore transformées en features" in sec["research_notice"]
    assert sec["max_submission_bytes"] < 64 * 1024 * 1024
    assert sec["max_primary_document_bytes"] < 64 * 1024 * 1024
    assert sec["submission_probe_bytes"] <= sec["max_submission_bytes"]


def test_each_scheduled_batch_has_at_most_one_daily_execution_time() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    for name, config in batch.items():
        hours = [item.strip() for item in str(config.get("run_hours") or "").split(",") if item.strip()]
        minutes = [item.strip() for item in str(config.get("run_minutes") or "").split(",") if item.strip()]
        assert len(hours) <= 1, f"{name}: plusieurs run_hours configurés"
        assert len(minutes) <= 1, f"{name}: plusieurs run_minutes configurées"


def test_non_reconstructible_snapshots_have_one_conditional_recovery() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    snapshots = {
        "security_master_snapshot",
        "market_cap_sync",
        "analyst_snapshot_collection",
        "borrow_status_snapshot",
        "oracle_options_indicative_snapshot",
        "options_delayed_bars_sync",
        "option_contract_adjustment_sync",
    }
    for name in snapshots:
        config = batch[name]
        recovery_hours = str(config.get("recovery_run_hours") or "").split(",")
        recovery_minutes = str(config.get("recovery_run_minutes") or "").split(",")
        assert len([value for value in recovery_hours if value.strip()]) == 1, name
        assert len([value for value in recovery_minutes if value.strip()]) == 1, name
        assert float(config["recovery_success_lookback_hours"]) > 0, name

    for name, config in batch.items():
        if name not in snapshots:
            assert "recovery_run_hours" not in config, name


def test_market_sensitive_batch_timezones_are_explicit() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    new_york_batches = {
        "borrow_status_snapshot",
        "business_quant_analyst_snapshot",
        "oracle_options_indicative_snapshot",
        "options_delayed_bars_sync",
        "oracle_opening_window_sync",
        "finra_short_volume_sync",
    }
    for name in new_york_batches:
        assert batch[name]["timezone"] == "America/New_York"
    assert batch["earnings_calendar_sync"]["timezone"] == "Europe/Paris"
    assert batch["analyst_snapshot_collection"]["timezone"] == "Europe/Paris"


def test_ml_artifacts_backup_is_weekly_and_excludes_catboost_logs() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    backup = batch["ml_artifacts_backup"]
    assert backup["enabled"] is True
    assert backup["timezone"] == "Europe/Paris"
    assert backup["run_days"] == "6"
    assert backup["run_hours"] == "1"
    assert backup["artifacts_dir"] == "artifacts/models"
    assert backup["dest_dir"] == "backups/ml"
    assert backup["keep"] == 5
    assert "catboost_info" in backup["execution_notice"]
    assert "exclu" in backup["execution_notice"]


def test_database_backups_have_disjoint_scopes_and_expected_schedules() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    core = batch["db_core_backup"]
    news = batch["db_news_raw_backup"]

    assert core["run_days"] == "0" and core["run_hours"] == "1"
    assert core["exclude_tables"] == "news_raw"
    assert "include_tables" not in core
    assert core["keep"] == 5
    assert news["run_days"] == "0" and news["run_hours"] == "18"
    assert news["first_weekday_of_month"] is True
    assert news["include_tables"] == "news_raw"
    assert "exclude_tables" not in news
    assert news["include_routines"] is False
    assert news["keep"] == 3
    assert core["archive_prefix"] != news["archive_prefix"]


def test_generic_launcher_enforces_first_weekday_of_month() -> None:
    content = (WINDOWS / "forward_pit_launcher.ps1").read_text(encoding="utf-8")
    assert "first_weekday_of_month" in content
    assert "$now.Day -gt 7" in content
    assert "-not $Force" in content


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
        assert isinstance(config.get("enabled"), bool), name
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
        "latest_quotes_sync",
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
        "options_delayed_bars_sync",
    )
    for name in names:
        assert batch[name]["symbols_file"] == expected
        assert "max_symbols" not in batch[name]


def test_latest_quotes_batch_uses_safe_idempotent_catchup_window() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    quotes = batch["latest_quotes_sync"]
    assert quotes["enabled"] is True
    assert quotes["priority"] == "P0"
    assert quotes["provider"] == "alpaca_iex"
    assert quotes["timezone"] == "America/New_York"
    assert quotes["run_hours"] == "17"
    assert quotes["run_minutes"] == "15"
    assert quotes["lookback_days"] == 7
    assert quotes["batch_size"] == 200
    assert "stock_quote_snapshots" in quotes["tables"]
    assert batch["sec_edgar_incremental"]["lookback_days"] == 7
    assert batch["oracle_opening_window_sync"]["lookback_days"] == 7


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



def test_delayed_option_batches_are_explicitly_research_only() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    bars = batch["options_delayed_bars_sync"]
    occ = batch["option_contract_adjustment_sync"]
    nbbo = batch["official_options_nbbo_sync"]
    assert bars["enabled"] is True
    assert bars["status"] == "ACTIVE_RESEARCH_ONLY"
    assert bars["symbols_file"] == "config/univers_batch/univers_filtred_tradable.txt"
    assert "UNVERIFIED_OPRA" in bars["research_notice"]
    assert occ["enabled"] is True
    assert occ["universe_scope"] == "market_wide_options_adjustments"
    assert nbbo["enabled"] is False
    assert nbbo["status"] == "BLOCKED_FREE_NO_NBBO_SOURCE"

def test_opening_window_batch_uses_delayed_sip_on_full_stable_universe() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    opening = batch["oracle_opening_window_sync"]
    assert opening["enabled"] is True
    assert opening["status"] == "ACTIVE_RESEARCH_ONLY"
    assert opening["provider"] == "alpaca"
    assert opening["feed"] == "sip"
    assert opening["adjustment"] == "raw"
    assert opening["symbols_file"] == "config/univers_batch/univers_filtred_tradable.txt"
    assert opening["window_start"] == "04:00"
    assert opening["window_end"] == "10:30"
    assert opening["minimum_sip_delay_minutes"] >= 16
    assert "max_symbols" not in opening


def test_non_symbol_batches_declare_why_they_are_not_universe_filtered() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    expected_scopes = {
        "security_master_snapshot": "market_wide_discovery",
        "corporate_actions_sync": "market_wide",
        "sec_edgar_incremental": "market_wide_filings",
        "sec_corporate_events_normalize": "raw_sec_filings",
        "sec_institutional_ownership_normalize": "raw_sec_filings",
        "fred_alfred_vintage_sync": "macro_series",
        "option_contract_adjustment_sync": "market_wide_options_adjustments",
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
    assert "Get-ConfigValue $cfg 'recovery_run_minutes' ''" in installer
    assert "function Get-ConfigValue" in launcher
    for field in ("log_file", "enabled", "status", "timezone", "run_days", "run_hours", "run_minutes"):
        assert f"Get-ConfigValue $cfg '{field}'" in launcher
    assert "service.forward_pit.recovery_gate" in launcher
    assert "gate-unavailable-run-anyway" in launcher


def test_generic_installer_builds_task_name_without_spaces() -> None:
    installer = (WINDOWS / "install_forward_pit_task.ps1").read_text(encoding="utf-8")
    assert "}) -join '')" in installer
    assert "$TaskName = 'AlphaTrade-' + $suffix" in installer


def test_securities_lending_batch_explains_provider_blocker_in_ui() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    lending = batch["securities_lending_sync"]
    notice = lending["research_notice"]

    assert lending["enabled"] is False
    assert lending["status"] == "PENDING_PROVIDER"
    assert lending["provider"] == "Aucun fournisseur validé"
    assert "aucune source gratuite validée" in notice.lower()
    for provider in (
        "IBKR TWS/API", "IBKR Public Shortstock FTP", "Eulerpool", "Alpaca",
        "Tradier", "iBorrowDesk", "ChartExchange", "MyAllies", "ORTEX",
        "Orbisa", "S3 Partners",
    ):
        assert provider in notice


def test_auction_imbalance_batch_stays_blocked_while_poc_is_not_scheduled() -> None:
    batch = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    auction = batch["auction_imbalance_sync"]
    assert auction["enabled"] is False
    assert auction["status"] == "BLOCKED_NO_FREE_OFFICIAL_FEED"
    assert auction["tables"] == ""
    assert "Nasdaq NOII" in auction["research_notice"]
    assert "NYSE" in auction["research_notice"]
    assert "nyse_auction_history_poc" in auction["research_notice"]
    assert "LAISSER DÉSACTIVÉ" in auction["research_notice"]
    assert "aucune collecte quotidienne" in auction["research_notice"]
    assert "HTTP 429 après 51 réponses" in auction["research_notice"]
