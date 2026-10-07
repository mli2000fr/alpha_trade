"""Sprint 13-B : sélection sans labels et synthèse qui échoue fermée."""

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from modelFactory.cn_economic_preflight import SAFE_COLUMNS
from modelFactory.cn_economic_replay_13b import (
    aggregate_runs,
    eligible_signal_dates,
    make_intents,
    select_momentum,
)


def test_signal_window_uses_fill_linked_horizon_and_hash_priority():
    days = [date(2024, 1, 2) + timedelta(days=offset) for offset in range(30)]
    eligible = eligible_signal_dates(days)
    assert days[8] in eligible
    assert days[9] not in eligible
    frame = pd.DataFrame({"session_date": [days[0]], "instrument_id": [7]})
    first = make_intents(frame, semester="2024H1", seed=0, valid_dates=eligible,
                         ticket=Decimal("10000"), policy="oracle_all")
    second = make_intents(frame, semester="2024H1", seed=0, valid_dates=eligible,
                          ticket=Decimal("10000"), policy="oracle_all")
    assert first == second
    assert first[0].signal_date == days[0]
    assert first[0].budget_cny == Decimal("10000")


def test_momentum_uses_same_universe_without_oracle_gate_or_future_labels():
    frame = pd.DataFrame({
        "market_code": ["CN_A"] * 20,
        "session_date": ["2024-03-04"] * 20,
        "instrument_id": list(range(20)),
        "board_code": ["SH_MAIN"] * 20,
        "oracle_top20": [False] * 20,
        "baseline_score": list(range(20)),
        "rank_score": [0.0] * 20,
    })[SAFE_COLUMNS]
    selected = select_momentum(frame)
    assert set(selected["instrument_id"]) == {16, 17, 18, 19}
    with pytest.raises(ValueError, match="invalide"):
        select_momentum(frame.assign(future_return=1.0))


def test_aggregate_refuses_mean_if_any_run_is_unresolved():
    base = {"policy": "oracle_all", "scenario": "base", "cost_profile": "cn_a_research",
            "economic_result_valid": True, "marked_return_proxy": 0.05,
            "unresolved_instruments": {}}
    summary = aggregate_runs({"valid": base, "blocked": {
        **base, "economic_result_valid": False, "marked_return_proxy": 0.9,
        "unresolved_instruments": {7: "FACTOR_EVENT_UNRESOLVED"},
    }})
    item = summary["oracle_all__base__cn_a_research"]
    assert item["blocked_runs"] == 1
    assert item["mean_semester_marked_return_only_if_all_valid"] is None
