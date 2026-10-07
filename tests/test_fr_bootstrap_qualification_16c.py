from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

import service.fr.bootstrap_qualification_16c as module


@pytest.fixture
def setup(tmp_path, monkeypatch):
    days = [day.date() for day in pd.bdate_range("2026-09-07", "2026-10-05")]
    cutoff = datetime(2026, 10, 6, 19, tzinfo=timezone.utc)
    collection = {"market_code": "FR_EQ", "status": "COLLECTED_PENDING_QUALIFICATION",
                  "finished_at": "2026-10-06T18:30:00+00:00", "end_date": "2026-10-05",
                  "stages": {"bars": {"requested_count": 1, "failed_count": 0},
                             "actions": {"failed_count": 0}}}
    monkeypatch.setattr(module, "read_json", lambda *args: collection)
    monkeypatch.setattr(module, "observed_payloads", lambda *args: ([], []))
    monkeypatch.setattr(module, "master_at", lambda *args: ({}, ["MASTER_CONTINUITY_UNQUALIFIED"], []))
    monkeypatch.setattr(module, "identity_reasons", lambda *args: [])
    monkeypatch.setattr(module, "action_checks", lambda *args: [])
    rows = [{"source_session_date": day, "open": 100 + i, "close": 101 + i,
             "high": 102 + i, "low": 99 + i, "volume": 1000 + i, "raw_sha256": "a" * 64}
            for i, day in enumerate(days)]
    monkeypatch.setattr(module, "select_bars", lambda *args: (rows, []))
    calendar = SimpleNamespace(
        session=lambda day: SimpleNamespace(close_at_utc=datetime(2026, 10, 5, 16, tzinfo=timezone.utc)),
        previous_session=lambda day, nth: days[0], session_dates=lambda *args: days)
    manifest = {"universe": [{"research_uid": "one", "provider_symbol": "A.PA"}]}
    kwargs = {"root": tmp_path, "audit_at": cutoff, "calendar": calendar, "manifest": manifest}
    return tmp_path / "artifacts/fr/research/bootstrap", kwargs, collection


def test_numeric_readiness_is_not_serving(setup):
    bootstrap, kwargs, _ = setup
    report = module.qualify(bootstrap, **kwargs)
    assert report["numeric_features_ready_count"] == 1
    assert report["local_checks_without_global_reserves_passed_count"] == 1
    assert report["servable_count"] == 0
    assert report["audit_role"] == "BOOTSTRAP_WINDOW_AUDIT_NOT_DECISION_REPLAY"
    assert "MASTER_CONTINUITY_UNQUALIFIED" in report["global_reserves"]
    assert not report["serving_enabled"] and not report["sql_writes"]


def test_observation_after_cutoff_rejected(setup):
    bootstrap, kwargs, _ = setup
    kwargs["audit_at"] = datetime(2026, 10, 6, 7, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="unavailable"):
        module.qualify(bootstrap, **kwargs)


def test_partial_collection_remains_visible(setup):
    bootstrap, kwargs, collection = setup
    collection["status"] = "PARTIAL_COLLECTION"
    collection["stages"]["bars"]["failed_count"] = 1
    report = module.qualify(bootstrap, **kwargs)
    assert {"PARTIAL_COLLECTION", "COLLECTION_STAGE_FAILURE_OR_MISSING"} <= set(report["global_reserves"])


def test_per_symbol_action_failure_does_not_erase_numeric_features(setup, monkeypatch):
    bootstrap, kwargs, _ = setup
    monkeypatch.setattr(module, "action_checks", lambda *args: ["UNQUALIFIED_DIV_IN_FEATURE_WINDOW"])
    report = module.qualify(bootstrap, **kwargs)
    assert report["numeric_features_ready_count"] == 1
    assert report["local_checks_without_global_reserves_passed_count"] == 0
    assert report["reason_counts"]["UNQUALIFIED_DIV_IN_FEATURE_WINDOW"] == 1


def test_wrong_market_and_naive_time_rejected(setup):
    bootstrap, kwargs, collection = setup
    collection["market_code"] = "US_EQ"
    with pytest.raises(ValueError, match="Completed FR"):
        module.qualify(bootstrap, **kwargs)
    kwargs["audit_at"] = datetime(2026, 10, 6)
    with pytest.raises(ValueError, match="timezone"):
        module.qualify(bootstrap, **kwargs)
