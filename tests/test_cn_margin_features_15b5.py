from collections import deque

import pandas as pd
import pytest

from modelFactory.cn_margin_features_15b5 import (
    FEATURES,
    attach_targets,
    join_price,
    oracle_pool,
    rolling_row,
    strict_join,
)


def row(index, ratio=0.2):
    return {"instrument_id": 1, "source_session": f"2020-01-{index + 1:02d}",
            "financing_buy_to_amount": ratio, "quality_reasons": [],
            "measures": {"融资余额": 100 + index}}


def test_windows_exact_definition():
    history = deque(maxlen=21)
    for i in range(21):
        result = rolling_row(row(i), i, history)
    assert result[FEATURES[1]] == pytest.approx(0.2)
    assert result[FEATURES[2]] == pytest.approx(120 / 115 - 1)
    assert result[FEATURES[3]] == pytest.approx(0.2)


@pytest.mark.parametrize("failure", ["gap", "missing", "anomaly"])
def test_invalid_window_no_bridge(failure):
    history = deque(maxlen=21)
    for i in range(21):
        if failure == "gap" and i == 10:
            continue
        item = row(i)
        if i == 10 and failure == "missing":
            item["quality_reasons"] = ["MISSING"]
            item["measures"] = None
            item["financing_buy_to_amount"] = None
        if i == 10 and failure == "anomaly":
            item["financing_buy_to_amount"] = 1.47
        result = rolling_row(item, i, history)
    assert result[FEATURES[3]] is None
    assert result[FEATURES[2]] is not None  # older issue no longer in six-row window


def test_zero_initial_balance_not_divided():
    history = deque(maxlen=21)
    for i in range(6):
        item = row(i)
        if i == 0:
            item["measures"]["融资余额"] = 0
        result = rolling_row(item, i, history)
    assert result[FEATURES[2]] is None


def test_asof_strict_and_no_stale_fallback():
    events = pd.DataFrame({"instrument_id": [1, 1, 1], "decision_at": [
        "2020-01-03T07:00:00Z", "2020-01-03T07:00:01Z", "2020-01-04T07:00:01Z"]})
    calendar = pd.DataFrame({"source_session": ["2020-01-01", "2020-01-02"],
                             "margin_available_at": ["2020-01-03T07:00:00Z", "2020-01-04T07:00:00Z"]})
    margins = pd.DataFrame([{"instrument_id": 1, "source_session": "2020-01-01",
                              **dict.fromkeys(FEATURES, 0.2)}])
    result = strict_join(events, margins, calendar)
    assert not result.iloc[0]["margin_common_valid"]
    assert result.iloc[1]["margin_common_valid"]
    assert not result.iloc[2]["margin_common_valid"]
    assert result.iloc[2]["source_session"] == "2020-01-02"


def test_oracle_top20_not_conditioned_on_future_labels():
    events = pd.DataFrame({"instrument_id": range(10), "session_date": ["2020-01-01"] * 10,
                           "oracle_score": range(10), "target_quality_valid": [True] * 8 + [False] * 2})
    assert list(oracle_pool(events)["instrument_id"]) == [9, 8]
    with pytest.raises(ValueError):
        oracle_pool(pd.concat([events, events.iloc[:1]]))


def test_shared_price_columns_verified_not_suffixed():
    event = pd.DataFrame({"session_date": ["2020-01-01"], "instrument_id": [1], "cn_breadth_1": [0.3]})
    price = event.assign(decision_at="2020-01-01T01:30:00Z")
    result = join_price(event, price)
    assert result["cn_breadth_1"].iloc[0] == 0.3
    assert "cn_breadth_1_oracle" not in result
    with pytest.raises(ValueError):
        join_price(event, price.assign(cn_breadth_1=0.4))


def test_unknown_or_invalid_targets_remain_null_not_negative():
    frame = pd.DataFrame({"oracle_decile": pd.Series([1, 10, 5, pd.NA, 10], dtype="Int8"),
                          "target_quality_valid": [True, True, True, False, False]})
    attach_targets(frame)
    assert frame["target_d10"].iloc[:3].tolist() == [0, 1, 0]
    assert frame["target_d10"].iloc[3:].isna().all()
    assert frame["target_d1_vs_d10"].iloc[2:].isna().all()
