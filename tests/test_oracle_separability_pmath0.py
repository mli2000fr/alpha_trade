import numpy as np
import pandas as pd

from modelFactory.oracle_separability_pmath0 import (
    TARGET,
    attach_task,
    balanced_by_date,
    empirical_test,
    holm_adjust,
    hp_bayes_error_bounds,
    hp_divergence,
    mst_edges,
    permute_within_date,
)


def test_frozen_task_populations_and_labels():
    frame = pd.DataFrame({"oracle_decile": range(1, 11)})
    tails = attach_task(frame, "D1_VS_D10")
    assert tails["oracle_decile"].tolist() == [1, 10]
    assert tails[TARGET].tolist() == [0, 1]
    assert attach_task(frame, "D10_VS_REST")[TARGET].sum() == 1
    assert attach_task(frame, "D1_VS_REST")[TARGET].sum() == 1


def test_balancing_is_inside_each_date():
    frame = pd.DataFrame({
        "date": [pd.Timestamp("2025-01-01")] * 5 + [pd.Timestamp("2025-01-02")] * 4,
        "symbol": list("ABCDEFGHI"),
        TARGET: [0, 0, 0, 1, 1, 0, 0, 0, 1],
    })
    result = balanced_by_date(frame, max_per_class=10, seed=7)
    counts = result.groupby(["date", TARGET]).size().unstack(fill_value=0)
    assert (counts[0] == counts[1]).all()
    assert counts.loc[pd.Timestamp("2025-01-01"), 0] == 2
    assert counts.loc[pd.Timestamp("2025-01-02"), 0] == 1


def test_permutation_preserves_daily_class_counts():
    labels = np.array([0, 0, 1, 1, 0, 1])
    dates = pd.to_datetime(["2025-01-01"] * 4 + ["2025-01-02"] * 2)
    result = permute_within_date(labels, dates, np.random.default_rng(3))
    for date in pd.unique(dates):
        mask = dates == date
        assert result[mask].sum() == labels[mask].sum()


def test_hp_divergence_and_bounds_are_bounded():
    values = np.array([[0.0], [0.1], [3.0], [3.1]])
    labels = np.array([0, 0, 1, 1])
    divergence = hp_divergence(labels, mst_edges(values))
    lower, upper = hp_bayes_error_bounds(divergence)
    assert 0.0 <= divergence <= 1.0
    assert 0.0 <= lower <= upper <= 0.5


def test_empirical_pvalue_and_holm_are_conservative():
    result = empirical_test(10.0, [0.0, 1.0, 2.0, 3.0])
    assert result["p_value"] == 0.2
    adjusted = holm_adjust({"a": 0.01, "b": 0.04, "c": 0.20})
    assert adjusted["a"] == 0.03
    assert adjusted["b"] == 0.08
    assert adjusted["c"] == 0.20
