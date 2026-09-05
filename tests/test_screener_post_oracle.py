from __future__ import annotations

import pandas as pd
import pytest

from modelFactory import screener_post_oracle as audit


def test_config_preregisters_h3_h10_h20() -> None:
    config = audit.ScreenerAuditConfig()
    assert config.horizons == (3, 10, 20)
    assert config.pool_pct == pytest.approx(0.20)


def test_merge_screener_asof_never_reads_future_and_marks_stale() -> None:
    pool = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-05", "2024-01-12", "2024-01-20"]),
        "symbol": ["AAA", "AAA", "AAA"],
    })
    snapshots = pd.DataFrame({
        "symbol": ["AAA", "AAA"],
        "snapshot_date": pd.to_datetime(["2024-01-04", "2024-01-15"]),
        "created_at": pd.to_datetime(["2024-01-04 22:00", "2024-01-15 22:00"]),
        "trend_score": [0.2, 0.9],
    })
    result = audit.merge_screener_asof(
        pool, snapshots, feature_columns=["trend_score"], max_age_days=7,
    ).sort_values("date")
    assert result["trend_score"].tolist() == [0.2, 0.2, 0.9]
    assert result["snapshot_age_days"].tolist() == [1, 8, 5]
    assert result["screener_snapshot_fresh"].tolist() == [True, False, True]


def test_missing_values_are_not_imputed_to_zero() -> None:
    pool = pd.DataFrame({"date": [pd.Timestamp("2024-01-05")], "symbol": ["AAA"]})
    snapshots = pd.DataFrame(columns=["symbol", "snapshot_date", "created_at", "short_score"])
    result = audit.merge_screener_asof(
        pool, snapshots, feature_columns=["short_score"], max_age_days=7,
    )
    assert pd.isna(result.loc[0, "short_score"])
    assert not bool(result.loc[0, "screener_snapshot_present"])


def test_attach_outcome_builds_three_zone_events() -> None:
    date = pd.Timestamp("2024-01-05")
    base = pd.DataFrame({"date": [date] * 3, "symbol": ["A", "B", "C"]})
    panel = pd.DataFrame({
        "date": [date] * 3, "symbol": ["A", "B", "C"], "horizon": [10] * 3,
        "future_return": [0.04, 0.0, -0.04],
        "future_return_excess_spy": [0.04, 0.0, -0.04],
        "future_return_sector_residual": [0.04, 0.0, -0.04],
    })
    result = audit.attach_outcome(
        base, panel, horizon=10, up_threshold=0.03, down_threshold=-0.03,
        max_abs_future_return=10.0,
    )
    assert result["true_long"].tolist() == [True, False, False]
    assert result["true_short"].tolist() == [False, False, True]


def test_attach_outcome_rejects_impossible_corporate_action_return() -> None:
    date = pd.Timestamp("2024-01-05")
    base = pd.DataFrame({"date": [date], "symbol": ["BAD"]})
    panel = pd.DataFrame({
        "date": [date], "symbol": ["BAD"], "horizon": [20],
        "future_return": [2000.0], "future_return_excess_spy": [2000.0],
        "future_return_sector_residual": [2000.0],
    })
    result = audit.attach_outcome(
        base, panel, horizon=20, up_threshold=0.03, down_threshold=-0.03,
        max_abs_future_return=10.0,
    )
    assert not bool(result.loc[0, "target_quality_valid"])
    assert pd.isna(result.loc[0, "future_return"])
    assert pd.isna(result.loc[0, "true_long"])


def _rule_frame(periods: int = 140) -> pd.DataFrame:
    rows = []
    for day_index, date in enumerate(pd.bdate_range("2023-01-02", periods=periods)):
        for symbol_index in range(10):
            score = symbol_index / 9
            future_return = (score - 0.5) * 0.10
            rows.append({
                "date": date, "symbol": f"S{symbol_index}", "score": score,
                "future_return": future_return,
                "true_long": future_return >= 0.03,
                "true_short": future_return <= -0.03,
                "screener_snapshot_fresh": True,
                "horizon": 3,
            })
    return pd.DataFrame(rows)


def test_discover_rule_finds_opposite_long_and_short_orientations() -> None:
    frame = _rule_frame()
    long_rule = audit.discover_rule(frame, "score", "long", 0.20)
    short_rule = audit.discover_rule(frame, "score", "short", 0.20)
    assert long_rule is not None and long_rule["orientation"] == "high"
    assert short_rule is not None and short_rule["orientation"] == "low"
    assert long_rule["metrics"]["return_lift"] > 0
    assert short_rule["metrics"]["return_lift"] > 0


def test_walk_forward_keeps_long_and_short_verdicts_independent() -> None:
    frame = _rule_frame(periods=100)
    config = audit.ScreenerAuditConfig(
        horizons=(3,), min_train_dates=30, val_dates=15, test_dates=15,
        step_dates=15, max_splits=3, min_feature_coverage=0.1,
    )
    folds, summary, decisions = audit.run_walk_forward_rules(frame, ["score"], config)
    assert not folds.empty
    assert set(summary["side"]) == {"long", "short"}
    assert set(summary["development_verdict"]) == {"CANDIDATE_DEVELOPMENT"}
    assert {"score__long", "score__short"}.issubset(decisions.columns)
    assert decisions[["score__long", "score__short"]].any().all()


def test_feature_coverage_separates_absolute_and_conditional_coverage() -> None:
    frame = pd.DataFrame({
        "score": [1.0, 2.0, None, None],
        "screener_snapshot_fresh": [True, True, False, False],
    })
    result = audit.feature_coverage(frame, ["score"], {"score": "predictive"}).iloc[0]
    assert result["coverage"] == pytest.approx(0.5)
    assert result["coverage_given_fresh"] == pytest.approx(1.0)


def test_snapshot_presence_summary_reports_filter_lift() -> None:
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2024-01-02"] * 4),
        "symbol": ["A", "B", "C", "D"], "horizon": [10] * 4,
        "future_return": [0.05, 0.04, -0.04, -0.03],
        "true_long": [True, True, False, False],
        "true_short": [False, False, True, True],
        "screener_snapshot_fresh": [True, True, False, False],
    })
    summary = audit.snapshot_presence_summary(frame)
    overall_long = summary[(summary["period"] == "ALL") & (summary["side"] == "long")].iloc[0]
    assert overall_long["effective_retention"] == pytest.approx(0.5)
    assert overall_long["return_lift"] > 0
