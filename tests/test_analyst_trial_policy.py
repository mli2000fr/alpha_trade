from datetime import datetime

import pytest

from analyst_research.trial_policy import trial_skip_reason
from scripts import collect_yahoo_analyst_snapshots as cli
from ihm.services.batch_management import load_market_batch_specs

CONFIG = {
    "enabled": True, "status": "ACTIVE_RESEARCH_TRIAL_RIGHTS_UNCONFIRMED",
    "timezone": "Europe/Paris", "trial_start_date": "2026-10-10",
    "trial_end_date_exclusive": "2026-11-10",
}

@pytest.mark.parametrize("instant,reason", [
    ("2026-10-09T21:59:59+00:00", "TRIAL_NOT_STARTED"),
    ("2026-10-09T22:00:00+00:00", None),
    ("2026-11-09T22:59:59+00:00", None),
    ("2026-11-09T23:00:00+00:00", "TRIAL_EXPIRED"),
])
def test_paris_trial_boundaries_and_dst(instant, reason):
    assert trial_skip_reason(CONFIG, now=datetime.fromisoformat(instant)) == reason

@pytest.mark.parametrize("updates", [
    {"trial_start_date": None}, {"trial_end_date_exclusive": None},
    {"trial_end_date_exclusive": "bad"}, {"timezone": "bad/zone"},
    {"trial_start_date": "2026-12-01"},
])
def test_invalid_trial_fails_closed(updates):
    assert trial_skip_reason({**CONFIG, **updates}) == "INVALID_TRIAL_WINDOW"

def test_other_collectors_have_no_implicit_trial():
    assert trial_skip_reason({"status": "ACTIVE"}) is None

def test_expired_cli_stops_before_db_and_universe(monkeypatch, capsys):
    monkeypatch.setattr(cli, "load_batch_config", lambda: {"analyst_snapshot_collection": CONFIG})
    monkeypatch.setattr(cli, "trial_skip_reason", lambda cfg: "TRIAL_EXPIRED")
    def forbidden(*args, **kwargs):
        pytest.fail("Expired trial must stop before DB or provider access")
    for name in ("resolve_universe", "run_collection", "AnalystSnapshotRepository"):
        monkeypatch.setattr(cli, name, forbidden)
    assert cli.main(["--symbols", "AAPL", "--write-db"]) == 0
    assert "SKIPPED_TRIAL_EXPIRED" in capsys.readouterr().out

def test_catalog_activates_us_analyst_with_manual_stop():
    spec = next(s for s in load_market_batch_specs("US_EQ") if s.name == "analyst_snapshot_collection")
    assert spec.enabled and spec.runnable
    assert spec.raw_config["rights_status"] == "UNCONFIRMED_YAHOO_PERMISSION"
    assert spec.raw_config["status"] == "ACTIVE_RESEARCH_RIGHTS_UNCONFIRMED"
    assert "trial_start_date" not in spec.raw_config
    assert "trial_end_date_exclusive" not in spec.raw_config
    for instant in ("2026-11-10T00:00:00+01:00", "2027-01-01T00:00:00+01:00"):
        assert trial_skip_reason(spec.raw_config, now=datetime.fromisoformat(instant)) is None
    assert spec.symbols_file == "config/univers_batch/univers_filtred_tradable.txt"
