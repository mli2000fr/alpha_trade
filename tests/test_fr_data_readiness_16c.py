from datetime import date, datetime, timezone
from types import SimpleNamespace

import pytest

import service.fr.data_readiness_16c as module


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module, "reserve_audit", lambda: {"publication_continuity_confirmed": False})
    cfg = {"enabled": True, "status": "ACTIVE_RESEARCH",
           "identities_file": "artifacts/fr/identities.gz"}
    monkeypatch.setattr(module, "load_section", lambda *args: cfg)
    monkeypatch.setattr(module, "get_market_calendar", lambda *args, **kwargs: SimpleNamespace(
        session=lambda day: SimpleNamespace(close_at_utc=datetime(2020, 1, 2, tzinfo=timezone.utc))))
    return tmp_path / "artifacts/fr/research/data_readiness_16c/test", cfg


def test_isolation_lookback_and_no_promotion(environment, monkeypatch):
    output, cfg = environment
    calls = []
    def collector(config, stats, **kwargs):
        calls.append(kwargs["root"])
        assert config["lookback_days"] == 31
        assert not kwargs["resume"]
        stats.update(received_count=1, persisted_count=1)
    monkeypatch.setattr(module, "collect", collector)
    monkeypatch.setattr(module, "corporate", collector)
    report = module.run(output, date(2020, 1, 2))
    assert report["status"] == "COLLECTED_PENDING_QUALIFICATION"
    assert not report["sql_writes"] and not report["serving_enabled"]
    assert all(path.is_relative_to(output) for path in calls)
    assert (output / "report.json").exists() and not (output / ".lock").exists()
    assert "lookback_days" not in cfg
    with pytest.raises(ValueError, match="Existing run"):
        module.run(output, date(2020, 1, 2))


def test_collection_error_visible_and_actions_still_collected(environment, monkeypatch):
    output, _ = environment
    monkeypatch.setattr(module, "collect", lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("bad response")))
    monkeypatch.setattr(module, "corporate", lambda *args, **kwargs: None)
    report = module.run(output, date(2020, 1, 2))
    assert report["status"] == "PARTIAL_COLLECTION"
    assert report["stages"]["bars"]["failed_count"] == 1
    assert report["stages"]["actions"]["status"] == "COLLECTED_NOT_QUALIFIED"


def test_disabled_collector_never_called(environment, monkeypatch):
    output, cfg = environment
    cfg["enabled"] = False
    monkeypatch.setattr(module, "collect", lambda *args, **kwargs: pytest.fail("disabled collector called"))
    with pytest.raises(ValueError, match="disabled or blocked"):
        module.run(output, date(2020, 1, 2))
    assert (output / "report.json").exists()
    assert not (output / ".lock").exists()


def test_future_and_outside_scope_rejected(environment):
    output, _ = environment
    with pytest.raises(ValueError, match="already closed"):
        module.run(output, date(2099, 1, 1))
    assert not output.exists()
    with pytest.raises(ValueError, match="Isolated FR"):
        module.run(output.parents[3] / "outside", date(2020, 1, 2))
