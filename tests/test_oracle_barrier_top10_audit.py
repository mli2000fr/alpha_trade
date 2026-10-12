"""Research selections retain future unknowns and compare sides on identical rows."""
import numpy as np
import pandas as pd
import pytest

from modelFactory.oracle_barrier import ANY_SCORE, ANY_TARGET, SCORES, TARGETS
from modelFactory.oracle_barrier.train import annotate_direction
from scripts.research.us_oracle_barrier_top10_audit import (
    POLICIES, block_intervals, daily_counts, score_diagnostics, select_top, summarize, validate_frame,
)


def sample():
    frame = pd.DataFrame({"date": pd.to_datetime(["2020-01-06"] * 4 + ["2020-01-07"] * 4),
        "symbol": ["A", "B", "C", "D"] * 2, "fold_start": "2020-01-06",
        SCORES["long"]: [.9, .7, .1, .5, .4, .3, .2, .5],
        SCORES["short"]: [.2, .8, .6, .5, .2, .4, .3, .5],
        TARGETS["long"]: [np.nan, 0., 1., 0., 1., 0., 0., 0.],
        TARGETS["short"]: [np.nan, 1., 0., 0., 0., 1., 0., 0.],
        "long_outcome": ["UNQUALIFIED", "SL", "TP", "EXPIRED", "TP", "SL", "SL", "EXPIRED"],
        "short_outcome": ["UNQUALIFIED", "TP", "SL", "EXPIRED", "SL", "TP", "SL", "EXPIRED"]})
    frame[ANY_TARGET] = frame[list(TARGETS.values())].max(axis=1).where(frame[list(TARGETS.values())].notna().all(axis=1))
    # Only annotate_direction's required return diagnostics; they are not audited as PnL.
    frame["long_gross_return"] = frame["short_gross_return"] = 0.
    return annotate_direction(frame, .55)


def inputs():
    return {"universe": ["A", "B", "C", "D"], "research_direction": {"min_score": .55}}, {
        "direction": {"rows": 8}, "folds": [{"fold_start": "2020-01-06", "test_end": "2020-01-07",
            "val_start": "2019-07-01", "heads": {side: {"status": "TRAINED",
                "train_available_max": "2019-06-28", "val_available_max": "2020-01-03"} for side in ("long", "short")}}]}


def test_unknown_top_candidate_kept_not_replaced():
    top = select_top(sample(), "LONG_TOP10", top_n=2)
    assert top.symbol.tolist() == ["A", "B", "D", "A"]
    assert top.selection_rank.tolist() == [1, 2, 1, 2]
    assert pd.isna(top.audit_target.iloc[0])
    result = summarize(top)
    assert result["selected"] == 4 and result["evaluated"] == 3
    assert result["unknown"] == 1 and result["tp_rate"] == pytest.approx(1 / 3)


def test_frozen_threshold_preserves_abstentions_not_backfilled():
    frame = sample()
    top = select_top(frame, "MAX_TOP10_FROZEN_THRESHOLD", top_n=2)
    assert top.symbol.tolist() == ["A", "B", "D", "A"]
    assert top.audit_direction.tolist() == ["LONG", "SHORT", "ABSTAIN", "ABSTAIN"]
    result = summarize(top)
    assert result["selected"] == 4 and result["chosen"] == 2 and result["abstain"] == 2
    assert result["evaluated"] == 1 and result["tp"] == 1 and result["unknown"] == 1


def test_argmax_is_explicit_diagnostic_and_ties_abstain():
    frame = sample()
    before = frame.copy(deep=True)
    top = select_top(frame, "MAX_TOP10_ARGMAX_DIAGNOSTIC", top_n=2)
    assert top.audit_direction.tolist() == ["LONG", "SHORT", "ABSTAIN", "LONG"]
    pd.testing.assert_frame_equal(frame, before)
    result = summarize(top)
    assert result["paired"] == 2
    assert result["paired_tp_rate"] == 1.
    assert result["paired_always_long_tp_rate"] == .5
    assert result["paired_always_short_tp_rate"] == .5
    assert result["paired_delta_vs_long"] == .5


def test_rank_tie_uses_symbol_not_future_result():
    frame = sample().sample(frac=1, random_state=42)
    frame[SCORES["long"]] = .8
    top = select_top(frame, "LONG_TOP10", top_n=2)
    assert top.symbol.tolist() == ["A", "B", "A", "B"]


@pytest.mark.parametrize("policy", POLICIES)
def test_count_conservation(policy):
    top = select_top(sample(), policy, top_n=3)
    r = summarize(top)
    assert r["selected"] == r["tp"] + r["sl"] + r["expired"] + r["unknown"] + r["abstain"]
    assert r["chosen"] == r["long"] + r["short"]
    assert r["evaluated"] == r["tp"] + r["sl"] + r["expired"]
    assert r["unknown"] == r["unqualified"] + r["ambiguous"]


def test_descriptive_block_intervals_deterministic_and_keep_pairs():
    daily = daily_counts(select_top(sample(), "LONG_TOP10", top_n=4))
    a = block_intervals(daily, block=1, repetitions=100)
    b = block_intervals(daily, block=1, repetitions=100)
    assert a == b
    assert a["paired_delta_vs_long"]["lower"] == 0.
    assert a["paired_delta_vs_long"]["upper"] == 0.


def test_all_abstain_intervals_missing_not_fake_zero_success():
    frame = sample()
    top = select_top(frame[frame.date.eq(pd.Timestamp("2020-01-07"))], "MAX_TOP10_FROZEN_THRESHOLD", top_n=4)
    r = summarize(top, bootstrap=True)
    assert r["tp_rate"] is None and r["evaluated"] == 0
    assert r["block_bootstrap_95pct"]["tp_rate"]["lower"] is None
    assert r["block_bootstrap_95pct"]["tp_rate"]["valid_replicates"] == 0


def test_validate_archive_and_reject_duplicate_corrupt_direction_score_or_label():
    protocol, report = inputs()
    frame = sample()
    validate_frame(frame, protocol, report)
    with pytest.raises(ValueError, match="Duplicate"):
        validate_frame(pd.concat([frame, frame.iloc[:1]]), protocol, report)
    for column, value, message in [("research_direction", "SHORT", "direction"),
        (ANY_SCORE, .01, "maximum"), (SCORES["long"], np.inf, "scores"),
        (TARGETS["long"], 1., "qualification")]:
        corrupt = frame.copy()
        corrupt.loc[0, column] = value
        with pytest.raises(ValueError, match=message):
            validate_frame(corrupt, protocol, report)


def test_availability_must_precede_test():
    protocol, report = inputs()
    report["folds"][0]["heads"]["short"]["val_available_max"] = "2020-01-06"
    with pytest.raises(ValueError, match="purge"):
        validate_frame(sample(), protocol, report)


def test_reliability_bins_keep_zero_and_one_and_do_not_fit_calibration():
    frame = sample()
    frame.loc[1, SCORES["long"]] = 0.
    frame.loc[2, SCORES["long"]] = 1.
    before = frame.copy(deep=True)
    result = score_diagnostics(frame)["long"]
    assert result["evaluated"] == 7
    assert sum(row["count"] for row in result["bins"]) == 7
    assert result["bins"][0]["count"] == result["bins"][9]["count"] == 1
    assert result["mean_score"] == pytest.approx(frame[SCORES["long"]].iloc[1:].mean())
    assert 0 <= result["brier"] <= 1 and 0 <= result["fixed_10bin_ece"] <= 1
    pd.testing.assert_frame_equal(frame, before)
