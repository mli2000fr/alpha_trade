from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from modelFactory.cn_oracle_aggregate import _monthly_bootstrap
from modelFactory.cn_oracle_walk_forward import (
    DEFAULT_CONFIG,
    Protocol,
    _top_rows,
    fold_metrics,
    score_metrics,
    semester_bounds,
    split_fold,
)


def test_protocol_is_cn_only_and_fixed(tmp_path: Path) -> None:
    protocol = Protocol.load(DEFAULT_CONFIG)
    assert protocol.raw["market_code"] == "CN_A"
    assert protocol.raw["horizons"] == [5, 10, 15, 20]
    invalid = tmp_path / "protocol.yaml"
    invalid.write_text(DEFAULT_CONFIG.read_text(encoding="utf-8").replace(
        "market_code: CN_A", "market_code: US"
    ), encoding="utf-8")
    with pytest.raises(ValueError, match="CN_A"):
        Protocol.load(invalid)
    with pytest.raises(ValueError):
        semester_bounds("2026H1")


def test_split_purges_unavailable_labels_and_keeps_test() -> None:
    dates = pd.bdate_range("2019-01-01", "2022-06-30")
    frame = pd.DataFrame({
        "session_date": dates,
        "instrument_id": np.arange(len(dates)),
        "decision_at": dates + pd.Timedelta(hours=1),
        "available_at_utc": dates + pd.Timedelta(days=10, hours=1),
        "target_quality_valid": True,
    })
    train, val, test, split = split_fold(
        frame, test_semester="2022H1", validation_sessions=126,
        min_train_sessions=504, max_train_rows=100000,
    )
    assert split["test_start"] == "2022-01-01"
    assert test["session_date"].min() >= pd.Timestamp("2022-01-01")
    assert train["available_at_utc"].max() < val["decision_at"].min()
    assert val["available_at_utc"].max() < test["decision_at"].min()
    assert not set(train["session_date"]).intersection(test["session_date"])


def _evaluation_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2022-01-03", periods=40)
    rows = []
    for day in dates:
        for instrument in range(20):
            extreme = instrument < 4
            rows.append({
                "session_date": day, "instrument_id": instrument,
                "target_quality_valid": True, "oracle_extreme20": extreme,
                "oracle_decile": 1 if instrument < 2 else 10 if instrument < 4 else 5,
                "future_return": 0.10 if extreme else 0.01,
                "oracle_score": 1.0 - instrument / 20,
                "baseline_score": instrument / 20,
                "board_code": "SH_MAIN", "cn_breadth_1": 0.45,
                "execution_data_eligible": True,
            })
    return pd.DataFrame(rows)


def test_top20_and_monthly_bootstrap_compare_paired_days() -> None:
    frame = _evaluation_frame()
    selected = _top_rows(frame, "oracle_score", 0.20)
    assert len(selected) == 160
    assert selected["oracle_extreme20"].all()
    model = score_metrics(frame, score="oracle_score", top_pct=0.20)
    baseline = score_metrics(frame, score="baseline_score", top_pct=0.20)
    assert model["precision_top20"] == 1.0
    assert baseline["precision_top20"] == 0.0
    ci = _monthly_bootstrap(frame, top_pct=0.20, repetitions=100,
                            alpha=0.05 / 8, seed=1)
    assert ci["months"] == 2
    assert ci["lower_fwer_bound"] > 0


def test_fold_metrics_uses_same_paired_population() -> None:
    frame = _evaluation_frame()
    frame.loc[frame["instrument_id"].eq(0), "baseline_score"] = np.nan
    result = fold_metrics(frame, Protocol.load(DEFAULT_CONFIG))
    assert result["model"]["rows"] == result["baseline_atr"]["rows"]
    assert result["model"]["rows"] == 760
    assert result["paired_evaluation_coverage"] == 0.95
