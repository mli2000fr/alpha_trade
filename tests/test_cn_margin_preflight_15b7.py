import json

import pandas as pd
import pytest

from modelFactory.cn_margin_preflight_15b7 import historical_xshe_ids, task_gate
from modelFactory.cn_oracle_walk_forward import _sha

CFG = {"directional": {"minimum_train_sessions_after_purge": 504,
                        "minimum_validation_sessions_after_label_purge": 100},
       "evaluation": {"min_dates_per_fold": 60, "min_rows_per_task_per_fold": 500,
                      "min_symbols_per_task_per_fold": 20}}


def sample():
    days = pd.bdate_range("2021-01-01", "2025-12-31")
    calendar = {day: day + pd.Timedelta(hours=1) for day in days}
    rows = []
    for day in days:
        for symbol in range(20):
            rows.append({"session_date": day, "decision_at": calendar[day],
                         "instrument_id": symbol,
                         "available_at_utc": day + pd.offsets.BDay(21) + pd.Timedelta(hours=1),
                         "evaluation_common_valid": True,
                         "target_d10": symbol % 2,
                         "target_d1_vs_d10": symbol % 2})
    return pd.DataFrame(rows), calendar


def test_all_actual_gates_require_four_partitions_and_two_classes():
    frame, calendar = sample()
    for semester in ("2024H1", "2024H2", "2025H1", "2025H2"):
        result = task_gate(frame, task="D1_VS_D10", semester=semester,
                           full_calendar=calendar, cfg=CFG)
        assert result["all_gates_pass"]
        assert result["partitions"]["train"]["dates"] >= 504
        assert result["partitions"]["validation"]["dates"] >= 100


def test_rejects_one_class_in_test():
    frame, calendar = sample()
    frame.loc[frame.session_date.dt.year.eq(2024) & frame.session_date.dt.month.le(6),
              "target_d10"] = 1
    result = task_gate(frame, task="D10_VS_REST", semester="2024H1",
                       full_calendar=calendar, cfg=CFG)
    assert not result["all_gates_pass"]
    assert not result["checks"]["both_classes_every_partition"]


def test_rejects_label_available_at_decision():
    frame, calendar = sample()
    frame.loc[frame.index[0], "available_at_utc"] = frame.loc[frame.index[0], "decision_at"]
    with pytest.raises(ValueError, match="Future label already"):
        task_gate(frame, task="D10_VS_REST", semester="2024H1",
                  full_calendar=calendar, cfg=CFG)


def test_missing_common_data_not_imputed():
    frame, calendar = sample()
    frame.loc[frame.session_date.dt.year.eq(2024) & frame.session_date.dt.month.le(6),
              "evaluation_common_valid"] = False
    result = task_gate(frame, task="D10_VS_REST", semester="2024H1",
                       full_calendar=calendar, cfg=CFG)
    assert not result["checks"]["test_dates"]
    assert not result["all_gates_pass"]


def test_xshe_denominator_includes_never_margin_eligible(tmp_path):
    b4 = tmp_path / "b4"
    b5 = tmp_path / "b5"
    b4.mkdir()
    b5.mkdir()
    snapshot = b4 / "reference_snapshot.json"
    snapshot.write_text(json.dumps({"instruments": [
        {"instrument_id": 1, "local_symbol": "000001"},
        {"instrument_id": 2, "local_symbol": "000002"}]}), encoding="utf-8")
    state = b4 / "state.json"
    state.write_text(json.dumps({"reference_sha256": _sha(snapshot),
                                 "contract": {"config_sha256": "same"}}), encoding="utf-8")
    (b5 / "report.json").write_text(json.dumps({"b4_state_sha256": _sha(state),
                                                 "protocol_sha256": "same"}), encoding="utf-8")
    assert historical_xshe_ids(b5, b4) == {1, 2}
    snapshot.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="Changed"):
        historical_xshe_ids(b5, b4)
