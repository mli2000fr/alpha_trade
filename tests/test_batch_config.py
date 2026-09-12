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
    )
    for name in files:
        content = (WINDOWS / name).read_text(encoding="utf-8")
        assert "batch.yaml" in content, name
        assert "config.yaml" not in content, name
