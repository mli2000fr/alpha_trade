import numpy as np
import pandas as pd
import pytest
import yaml

from modelFactory.cn_margin_calendar_15b6 import (
    CONFIG,
    bounds,
    directional_calendar,
    load_protocol,
    split_extension,
)


def frame():
    dates = pd.bdate_range("2018-01-01", "2021-12-31")
    return pd.DataFrame({"session_date": dates, "instrument_id": np.arange(len(dates)),
                         "decision_at": dates + pd.Timedelta(hours=1),
                         "available_at_utc": dates + pd.Timedelta(days=30, hours=1),
                         "target_quality_valid": True, "oracle_extreme20": np.arange(len(dates)) % 2})


def test_oracle_extension_split_never_uses_future_labels():
    train, val, test, info = split_extension(frame(), "2021H1")
    assert info["train_sessions_after_purge_and_sampling"] >= 504
    assert train.available_at_utc.max() < pd.Timestamp(info["train_boundary_decision"])
    assert val.available_at_utc.max() < pd.Timestamp(info["validation_boundary_decision"])
    assert test.session_date.min() >= pd.Timestamp("2021-01-01")
    assert test.session_date.max() <= pd.Timestamp("2021-06-30")
    assert not set(train.instrument_id).intersection(test.instrument_id)


def test_early_extension_and_training_sample_insufficiency_rejected():
    with pytest.raises(ValueError, match="prior sessions"):
        split_extension(frame(), "2020H1")
    with pytest.raises(ValueError, match="cap lost"):
        split_extension(frame(), "2021H1", cap=100)


def test_duplicate_and_invalid_semester_rejected():
    value = frame()
    with pytest.raises(ValueError, match="Duplicate"):
        split_extension(pd.concat([value, value.iloc[:1]]), "2021H1")
    with pytest.raises(ValueError):
        bounds("2022H1")


def test_directional_calendar_has_two_disjoint_twenty_session_gaps():
    dates = pd.bdate_range("2021-01-01", "2024-06-30")
    result = directional_calendar(list(dates), "2024H1")
    prior = dates[dates < "2024-01-01"]
    assert result["validation_start"] == str(prior[-146].date())
    assert result["validation_end"] == str(prior[-21].date())
    assert result["train_end"] == str(prior[-167].date())
    assert result["calendar_gate_only"]
    assert not result["row_and_label_purge_gate_proven"]


def test_short_history_is_upper_bound_not_training_permission():
    dates = pd.bdate_range("2023-01-01", "2024-01-01")
    result = directional_calendar(list(dates), "2024H1")
    assert not result["calendar_gate_only"]
    assert not result["row_and_label_purge_gate_proven"]


def test_protocol_fixed_and_upstream_unchanged(tmp_path):
    cfg = load_protocol()
    assert cfg["evaluation"]["primary_hypotheses"] == 12
    assert cfg["directional"]["models"] == ["logistic", "lightgbm"]
    modified = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    modified["oracle_extension"]["horizon"] = 5
    path = tmp_path / "changed.yaml"
    path.write_text(yaml.safe_dump(modified), encoding="utf-8")
    with pytest.raises(ValueError, match="parameters"):
        load_protocol(path)
