from __future__ import annotations

from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parent.parent
WINDOWS = ROOT / "scripts" / "windows"


def test_market_cap_sync_config_contract() -> None:
    config = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
    sync = config["market_cap_sync"]
    assert sync == {
        "run_hours": "11,23",
        "run_days": "1,4",
        "symbols_file": "config/univers/univers_filtred_equities.txt",
        "providers": "yahoo_finance,finnhub",
        "log_file": "log/batch/market_cap_sync.txt",
    }


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


def test_market_cap_launcher_runs_both_sources_and_is_fail_closed() -> None:
    content = (WINDOWS / "market_cap_sync_launcher.ps1").read_text(encoding="utf-8")
    assert "modelFactory.fundamental_features" in content
    assert "yahoo_finance,finnhub" in content
    assert "symbols_file est obligatoire" in content
    assert "univers introuvable" in content
    assert "active-tradable" not in content
    assert "AlphaTradeMarketCapSync" in content
    assert "::alpha_trade_run_summary::" in content
    assert "Send-MarketCapNotification" in content
    assert "scripts\\send_batch_email.py" in content
    assert "email/Telegram" in content
    assert "--warning" in content
    assert "-Status 'ERROR'" in content


def test_market_cap_installer_uses_weekly_config_and_ignores_overlap() -> None:
    content = (WINDOWS / "install_market_cap_sync_task.ps1").read_text(encoding="utf-8")
    assert "New-ScheduledTaskTrigger -Weekly" in content
    assert "MultipleInstances IgnoreNew" in content
    assert "AlphaTrade-MarketCapSync" in content
