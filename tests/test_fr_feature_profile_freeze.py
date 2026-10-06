from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from modelFactory.fr_feature_profile_freeze import FEATURES, load_policy, qualify, run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def policy():
    value = load_policy(ROOT / "config/features_fr/fr_price_short_v1.yaml")
    value.update(start_date="2025-01-01", end_date="2025-06-30")
    return value


def sample(sessions, symbols=20):
    rows = [
        {
            "decision_session_date": d,
            "research_uid": str(i),
            "research_ready": False,
            "mask_all_features": False,
            "return_60": np.nan,
            "sma200_distance": np.nan,
            **dict.fromkeys(FEATURES, 0.1),
        }
        for d in sessions
        for i in range(symbols)
    ]
    return pd.DataFrame(rows)


def test_short_profile_does_not_reuse_long_masks(policy):
    sessions = pd.bdate_range("2025-01-01", periods=50).strftime("%Y-%m-%d").tolist()
    panel, periods = qualify(sample(sessions), policy, sessions)
    assert panel["profile_row_ready"].all()
    assert panel["offline_qualified"].all()
    assert periods[0]["state"] == "GO_DATA_COVERAGE"
    assert "return_60" not in panel and "research_ready" not in panel


def test_cross_section_counts_complete_rows_only(policy):
    sessions = ["2025-01-02"]
    frame = sample(sessions)
    frame.loc[0, "return_20"] = np.inf
    panel, _ = qualify(frame, policy, sessions)
    assert not panel["profile_row_ready"].any()
    assert panel["profile_complete_count"].eq(19).all()


def test_missing_sessions_in_denominator_and_boundary(policy):
    sessions = pd.bdate_range("2025-01-01", periods=50).strftime("%Y-%m-%d").tolist()
    _, periods = qualify(sample(sessions[:40]), policy, sessions)
    assert periods[0]["ready_session_fraction"] == 0.8
    assert periods[0]["state"] == "GO_DATA_COVERAGE"
    _, periods = qualify(sample(sessions[:39]), policy, sessions)
    assert periods[0]["state"] == "BLOCKED_DATA_COVERAGE"


def test_partial_semester_cannot_confirm(policy):
    policy["end_date"] = "2025-03-31"
    sessions = pd.bdate_range("2025-01-01", periods=50).strftime("%Y-%m-%d").tolist()
    panel, periods = qualify(sample(sessions), policy, sessions)
    assert panel["profile_row_ready"].all()
    assert not panel["offline_qualified"].any()
    assert "PARTIAL_PERIOD" in periods[0]["reasons"]


def test_future_rows_do_not_change_row_masks(policy):
    sessions = ["2025-01-02", "2025-01-03"]
    frame = sample(sessions)
    before, _ = qualify(frame, policy, sessions)
    frame.loc[frame["decision_session_date"].eq(sessions[1]), "return_20"] = np.nan
    after, _ = qualify(frame, policy, sessions)
    pd.testing.assert_series_equal(before["profile_row_ready"].iloc[:20], after["profile_row_ready"].iloc[:20])


def test_duplicate_and_off_calendar_rejected(policy):
    frame = sample(["2025-01-02"])
    with pytest.raises(ValueError, match="dupliquées"):
        qualify(pd.concat([frame, frame]), policy, ["2025-01-02"])
    with pytest.raises(ValueError, match="calendrier"):
        qualify(frame, policy, [])


@pytest.mark.parametrize("mutation", ["features", "benchmark", "gates"])
def test_contract_immutable(tmp_path, mutation):
    policy = load_policy(ROOT / "config/features_fr/fr_price_short_v1.yaml")
    if mutation == "features":
        policy["features"].append("return_60")
    elif mutation == "benchmark":
        policy["benchmark_features_enabled"] = True
    else:
        policy["period_gates"]["min_ready_row_fraction"] = 0.7
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(policy), encoding="utf-8")
    with pytest.raises(ValueError):
        load_policy(path)


def test_source_hash_mismatch_rejected(tmp_path):
    policy = load_policy(ROOT / "config/features_fr/fr_price_short_v1.yaml")
    source = tmp_path / "source.parquet"
    source.write_bytes(b"tampered")
    policy["source_panel"] = str(source)
    path = tmp_path / "profile.yaml"
    path.write_text(yaml.safe_dump(policy), encoding="utf-8")
    with pytest.raises(ValueError, match="Empreinte"):
        run(path, tmp_path / "output")
