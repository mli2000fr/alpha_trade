from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
WINDOWS = ROOT / "scripts" / "windows"


def test_market_cap_sync_config_contract() -> None:
    config = yaml.safe_load((ROOT / "batch.yaml").read_text(encoding="utf-8"))
    sync = config["market_cap_sync"]
    expected = {
        "run_hours": "11,23",
        "run_days": "1,4",
        "symbols_file": "config/univers_batch/univers_filtred_tradable.txt",
        "provider": "sec_edgar_then_yahoo_then_finnhub",
        "primary_provider": "sec",
        "fallback_providers": "yahoo_finance,finnhub",
        "sec_lookback_days": 30,
        "max_age_days": 365,
        "min_coverage_ratio": 0.95,
        "log_file": "log/batch/market_cap_sync.txt",
    }
    assert {key: sync[key] for key in expected} == expected
    assert sync["priority"] == "P0"
    assert sync["tables"] == "stock_fundamentals_daily"
    assert str(sync["description"]).strip()


def test_market_cap_sync_scripts_exist_and_are_hardened() -> None:
    for name in (
        "market_cap_sync_launcher.ps1",
        "install_market_cap_sync_task.ps1",
        "uninstall_market_cap_sync_task.ps1",
    ):
        content = (WINDOWS / name).read_text(encoding="utf-8")
        assert "Set-StrictMode" in content
        assert "$ErrorActionPreference = 'Stop'" in content
        assert "Invoke-Expression" not in content


def test_market_cap_launcher_delegates_to_common_forward_pit_runner() -> None:
    content = (WINDOWS / "market_cap_sync_launcher.ps1").read_text(encoding="utf-8")
    assert "forward_pit_launcher.ps1" in content
    assert "market_cap_sync" in content
    assert "[switch]$IgnoreRunDays" in content
    assert "'-Force'" in content


def test_market_cap_installer_uses_weekly_config_and_ignores_overlap() -> None:
    content = (WINDOWS / "install_market_cap_sync_task.ps1").read_text(encoding="utf-8")
    assert "batch.yaml" in content
    assert "config.yaml" not in content
    assert "New-ScheduledTaskTrigger -Weekly" in content
    assert "MultipleInstances IgnoreNew" in content
    assert "AlphaTrade-MarketCapSync" in content
