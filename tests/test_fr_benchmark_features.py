from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from common.market_calendar import get_market_calendar
from modelFactory.fr_benchmark_features import benchmark_windows, enrich, load_config
from modelFactory.fr_feature_profile_freeze import FEATURES


def fixture_data():
    calendar = get_market_calendar("FR_EQ")
    sessions = [s.session_date.isoformat() for s in calendar.sessions(date(2025, 1, 2), date(2025, 4, 1)) if s.is_open]
    rows, base = [], []
    for i, day in enumerate(sessions[:-1]):
        value = 0.001 * (i % 5 - 2)
        rows.append(
            {
                "source_session_date": day,
                "decision_session_date": sessions[i + 1],
                "benchmark_state": "KNOWN",
                "segment_id": 1,
                "price_return": value,
            }
        )
        at = calendar.session(date.fromisoformat(sessions[i + 1])).open_at_utc.isoformat()
        base.append(
            {
                "source_session_date": day,
                "decision_session_date": sessions[i + 1],
                "research_uid": "one",
                "decision_at": at,
                "max_input_available_at": at,
                **dict.fromkeys(FEATURES, 0.1),
                "return_1": 2 * value,
            }
        )
    return sessions, pd.DataFrame(rows), pd.DataFrame(base)


def test_compound_returns_and_first_complete_window():
    sessions, rows, _ = fixture_data()
    result = benchmark_windows(rows, sessions)
    assert result.iloc[18]["benchmark_return_20"] != result.iloc[18]["benchmark_return_20"]
    assert result.iloc[19]["benchmark_return_20"] == pytest.approx(np.prod(1 + rows["price_return"].iloc[:20]) - 1)


def test_unknown_breaks_window_and_new_segment_warmup():
    sessions, rows, _ = fixture_data()
    rows.loc[20, ["benchmark_state", "segment_id", "price_return"]] = ["UNKNOWN", np.nan, np.nan]
    rows.loc[21:, "segment_id"] = 2
    result = benchmark_windows(rows, sessions)
    assert result.iloc[20:40]["benchmark_return_20"].isna().all()
    assert np.isfinite(result.iloc[40]["benchmark_return_20"])


def test_beta_correlation_and_volatility():
    sessions, rows, base = fixture_data()
    result = enrich(base, benchmark_windows(rows, sessions), sessions)
    assert result["beta20"].iloc[19] == pytest.approx(2)
    assert result["correlation20"].iloc[19] == pytest.approx(1)
    assert result["relative_volatility20"].iloc[19] == pytest.approx(2)
    assert result["residual_return20"].iloc[19] == pytest.approx(0.1 - 2 * result["benchmark_return_20"].iloc[19])


def test_missing_stock_session_not_compressed():
    sessions, rows, base = fixture_data()
    base = base.drop(index=20)
    result = enrich(base, benchmark_windows(rows, sessions), sessions)
    assert result.loc[result["source_session_date"].isin(sessions[21:40]), "beta20"].isna().all()


def test_constant_market_variance_has_no_beta():
    sessions, rows, base = fixture_data()
    rows["price_return"] = 0.001
    result = enrich(base, benchmark_windows(rows, sessions), sessions)
    assert result["beta20"].isna().all()


@pytest.mark.parametrize("problem", ["duplicate", "wrong_date", "reused_segment", "unknown_value"])
def test_invalid_benchmark_rejected(problem):
    sessions, rows, _ = fixture_data()
    if problem == "duplicate":
        rows = pd.concat([rows, rows.iloc[:1]])
    elif problem == "wrong_date":
        rows.loc[0, "decision_session_date"] = sessions[2]
    elif problem == "reused_segment":
        rows.loc[20, ["benchmark_state", "segment_id", "price_return"]] = ["UNKNOWN", np.nan, np.nan]
    else:
        rows.loc[20, "benchmark_state"] = "UNKNOWN"
    with pytest.raises(ValueError):
        benchmark_windows(rows, sessions)


def test_future_benchmark_cannot_change_past_features():
    sessions, rows, base = fixture_data()
    before = enrich(base, benchmark_windows(rows, sessions), sessions)
    rows.loc[30:, "price_return"] = 0.01
    after = enrich(base, benchmark_windows(rows, sessions), sessions)
    pd.testing.assert_frame_equal(before.iloc[:30], after.iloc[:30])


def test_future_availability_rejected():
    sessions, rows, base = fixture_data()
    base.loc[0, "decision_at"] = "2025-01-02T00:00:00+00:00"
    with pytest.raises(ValueError, match="après décision"):
        enrich(base, benchmark_windows(rows, sessions), sessions)


def test_configuration_contract():
    cfg = load_config(Path(__file__).resolve().parents[1] / "config/features_fr/fr_price_benchmark_v1.yaml")
    assert cfg["statistics_window"] == 20
