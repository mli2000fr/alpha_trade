from copy import deepcopy
from datetime import date, datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

import service.fr.observed_reference_16d as module


@pytest.fixture
def context(tmp_path, monkeypatch):
    state = {"end": "2026-10-04", "last_observed_at": "2026-10-05T19:00:00+00:00"}
    monkeypatch.setattr(module, "master_at", lambda *args: (state, ["MASTER_STALE_OR_WRONG_SESSION",
        "MASTER_CONTINUITY_UNQUALIFIED"], []))
    monkeypatch.setattr(module, "identity_resolution", lambda *args: {
        "mic": "XPAR", "nominal_currency": "EUR", "reasons": [], "source_file": "fixture.zip"})
    calendar = SimpleNamespace(session=lambda day: SimpleNamespace(
        close_at_utc=datetime.combine(day, datetime.min.time(), timezone.utc).replace(hour=16)),
        session_dates=lambda start, end: [d.date() for d in pd.bdate_range(start, end)])
    manifest = {"universe": [{"research_uid": "one", "provider_symbol": "A.PA", "isin": "FRTEST"}]}
    return state, {"root": tmp_path, "calendar": calendar, "manifest": manifest}


def test_one_session_lag_is_diagnostic_not_authorization(context):
    _, kwargs = context
    report = module.select_reference("2026-10-06T09:00:00+02:00", date(2026, 10, 5), **kwargs)
    assert report["status"] == "KNOWN_REFERENCE_DIAGNOSTIC_ONLY"
    assert report["unobserved_sessions"] == ["2026-10-05"]
    assert "MASTER_CONTINUITY_UNQUALIFIED" in report["release_reserves"]
    assert not report["serving_allowed"]
    assert not report["identities"][0]["tradability_at_decision_verified"]


def test_two_session_lag_blocks(context):
    state, kwargs = context
    state["end"] = "2026-10-01"
    report = module.select_reference("2026-10-06T07:00:00+00:00", date(2026, 10, 5), **kwargs)
    assert "REFERENCE_COVERAGE_LAG_TOO_LARGE" in report["diagnostic_blocks"]


def test_old_observation_blocks(context):
    state, kwargs = context
    state["last_observed_at"] = "2026-10-01T00:00:00+00:00"
    report = module.select_reference("2026-10-06T07:00:00+00:00", date(2026, 10, 5), **kwargs)
    assert "REFERENCE_OBSERVATION_TOO_OLD" in report["diagnostic_blocks"]


def test_future_coverage_and_unfinished_feature_session(context):
    state, kwargs = context
    state["end"] = "2026-10-06"
    report = module.select_reference("2026-10-06T07:00:00+00:00", date(2026, 10, 5), **kwargs)
    assert "REFERENCE_COVERS_FUTURE_SESSION" in report["diagnostic_blocks"]
    with pytest.raises(ValueError, match="unfinished"):
        module.select_reference("2026-10-06T07:00:00+00:00", date(2026, 10, 6), **kwargs)


@pytest.mark.parametrize("key,value", [("serving_enabled", True), ("market_code", "US_EQ"),
    ("max_coverage_lag_sessions", 2), ("max_observation_age_hours", 120)])
def test_no_override_to_enable_or_relax_policy(context, key, value):
    _, kwargs = context
    policy = deepcopy(module.load_policy())
    policy[key] = value
    with pytest.raises(ValueError):
        module.select_reference("2026-10-06T07:00:00+00:00", date(2026, 10, 5), policy=policy, **kwargs)
