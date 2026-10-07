"""US collector rights blocks stop before SQL or provider access."""

from dataclasses import replace
from pathlib import Path

import pytest

from ihm.services import batch_management
from scripts import collect_yahoo_analyst_snapshots as analyst
from service.forward_pit import batch


ROOT = Path(__file__).resolve().parents[1]
BLOCKS = [
    ("analyst_snapshot_collection", "BLOCKED_YAHOO_AUTOMATED_ACCESS"),
    ("fred_alfred_vintage_sync", "BLOCKED_FRED_ARCHIVE_ML_RIGHTS"),
    ("finra_short_volume_sync", "BLOCKED_FINRA_PREDICTIVE_USE"),
]


@pytest.mark.parametrize("name,status", BLOCKS)
def test_us_block_is_visible_and_enabled_toggle_cannot_unlock(name, status):
    spec = next(s for s in batch_management.load_market_batch_specs("US_EQ") if s.name == name)
    assert spec.status == status
    assert not spec.enabled and not spec.runnable
    assert spec.research_notice and spec.activation_requirement and spec.unlock_steps
    assert not replace(spec, enabled=True).runnable


@pytest.mark.parametrize("name,status", BLOCKS[1:])
@pytest.mark.parametrize("enabled", [False, True])
def test_forward_direct_cli_stops_before_sql_and_handler(monkeypatch, name, status, enabled):
    monkeypatch.setattr(batch, "load_batch_config", lambda path: {name: {"enabled": enabled, "status": status}})

    def forbidden(*args, **kwargs):
        pytest.fail("Rights block must stop before SQL/provider access")

    monkeypatch.setattr(batch, "get_sqlalchemy_engine", forbidden)
    monkeypatch.setitem(batch.HANDLERS, name, forbidden)
    result, outcome = batch.execute(name, dry_run=True)
    assert result == "SKIPPED_" + status
    assert outcome.details["reason"] == status
    assert outcome.requested == outcome.received == outcome.persisted == 0


@pytest.mark.parametrize("enabled", [False, True])
def test_analyst_direct_cli_cannot_collect_when_blocked(monkeypatch, capsys, enabled):
    monkeypatch.setattr(analyst, "load_batch_config", lambda: {
        "analyst_snapshot_collection": {"enabled": enabled, "status": BLOCKS[0][1]}})

    def forbidden(*args, **kwargs):
        pytest.fail("Blocked analyst CLI must not resolve universe or collect")

    monkeypatch.setattr(analyst, "resolve_universe", forbidden)
    monkeypatch.setattr(analyst, "run_collection", forbidden)
    monkeypatch.setattr(analyst, "AnalystSnapshotRepository", forbidden)
    assert analyst.main(["--symbols", "AAPL", "--write-db", "--resume"]) == 0
    assert "SKIPPED_BLOCKED_YAHOO_AUTOMATED_ACCESS" in capsys.readouterr().out


@pytest.mark.parametrize("name", ["forward_pit_launcher.ps1", "analyst_snapshot_launcher.ps1"])
def test_windows_launchers_check_rights_before_schedule_or_force(name):
    source = (ROOT / "scripts/windows" / name).read_text(encoding="utf-8-sig")
    guard = source.index(".StartsWith('BLOCKED_')")
    assert guard < source.index("$isRecovery = $false")

