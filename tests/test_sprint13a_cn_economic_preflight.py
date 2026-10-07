"""Sprint 13-A : sélection PIT et audit d'événements sans labels futurs."""

from datetime import date, timedelta

import pandas as pd
import pytest

from modelFactory.cn_economic_preflight import (
    DEFAULT_CONFIG,
    SAFE_COLUMNS,
    audit_exposure,
    load_protocol,
    select_policies,
)


def _frame() -> pd.DataFrame:
    return pd.DataFrame([
        ["CN_A", "2024-03-04", 1, "SH_MAIN", True, -0.3, 0.9],
        ["CN_A", "2024-03-04", 2, "SZ_MAIN", True, 0.1, 0.5],
        ["CN_A", "2024-03-04", 3, "SH_MAIN", True, 0.4, 0.1],
        ["CN_A", "2024-03-05", 4, "SH_MAIN", False, 0.0, 0.8],
    ], columns=SAFE_COLUMNS)


def test_protocol_is_frozen_and_not_an_economic_go():
    protocol = load_protocol(DEFAULT_CONFIG)
    assert protocol["source_horizon"] == 20
    assert protocol["economic_go_allowed_at_13a"] is False
    assert protocol["preflight_gate"]["max_unclassified_action_exposure_fraction"] == 0.05


def test_policy_masks_use_only_safe_columns_before_any_label_filter():
    pool, masks = select_policies(_frame(), minimum=3)
    assert set(pool["instrument_id"]) == {1, 2, 3}
    assert set(pool.loc[masks["oracle_all"], "instrument_id"]) == {1, 2, 3}
    assert set(pool.loc[masks["reversal_veto_bottom20"], "instrument_id"]) == {1, 2}
    assert set(pool.loc[masks["lightgbm_veto_bottom20"], "instrument_id"]) == {1, 2}
    assert set(pool.loc[masks["lightgbm_long_top20"], "instrument_id"]) == {1}
    with pytest.raises(ValueError, match="Schéma"):
        select_policies(_frame().assign(future_return=0.5), minimum=3)


def test_action_window_is_entry_through_scheduled_exit_inclusive():
    sessions = [date(2024, 1, 2) + timedelta(days=offset) for offset in range(25)]
    candidates = pd.DataFrame({
        "session_date": [sessions[0], sessions[0], sessions[0], sessions[4]],
        "instrument_id": [1, 2, 3, 4],
    })
    audit = audit_exposure(
        candidates, sessions=sessions,
        action_dates={1: [sessions[1]], 2: [sessions[21]], 3: [sessions[22]],
                      4: [sessions[0]]},
        delistings={2: sessions[10], 3: None},
    )
    assert audit == {
        "selected_candidates": 4, "full_scheduled_path": 3,
        "censored_exit": 1, "action_exposed": 2,
        "entry_action_exposed": 1, "delisting_exposed": 1,
        "action_exposure_fraction": 0.666667, "full_path_fraction": 0.75,
    }


def test_missing_market_session_fails_closed():
    sessions = [date(2024, 1, 2) + timedelta(days=offset) for offset in range(25)]
    with pytest.raises(ValueError, match="absent du calendrier"):
        audit_exposure(pd.DataFrame({"session_date": [date(2023, 1, 1)],
                                     "instrument_id": [1]}), sessions=sessions,
                       action_dates={}, delistings={})
