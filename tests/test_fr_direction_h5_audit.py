import numpy as np
import pandas as pd
import pytest

from modelFactory.fr_direction_h5_audit import evaluate, load_config, rank_selection, verdict
from service.fr.universe_contract_6a import ROOT


def frame():
    return pd.DataFrame(
        {
            "decision_session_date": "2024-01-01",
            "research_uid": [f"u{i}" for i in range(10)],
            "provider_symbol": [f"S{i}" for i in range(10)],
            "future_return": np.linspace(-0.1, 0.1, 10),
            "decile": [1, 1, 3, 4, 5, 6, 7, 8, 10, 10],
            "return_5": np.arange(10),
        }
    )


def config():
    return load_config(ROOT / "config/research_fr/direction_h5_audit_v1.yaml")


def test_perfect_direction_and_relative_baseline():
    metrics, daily, bands = evaluate(frame(), "return_5", config())
    assert metrics["tail_auc"] == 1
    assert daily.iloc[0].precision_d10 == daily.iloc[0].precision_d1 == 1
    assert daily.iloc[0].ic == pytest.approx(1)
    assert daily.iloc[0].base_d10 == 0.2
    assert len(bands) == 5
    assert not metrics["support_admitted"]


def test_tail_membership_is_not_return_sign():
    f = frame()
    f["future_return"] = np.linspace(0.01, 0.1, 10)
    _, daily, _ = evaluate(f, "return_5", config())
    assert daily.iloc[0].precision_d1 == 1
    assert daily.iloc[0].short_positive_fraction == 0
    assert daily.iloc[0].short_return < 0


def test_selection_without_targets_and_order_invariance():
    f = frame().drop(columns=["decile", "future_return"])
    a = rank_selection(f, "return_5", 0.2, 17)
    b = rank_selection(f.sample(frac=1, random_state=8), "return_5", 0.2, 17)
    pd.testing.assert_frame_equal(a, b)
    assert a.research_uid.tolist() == ["u9", "u8"]


def test_equal_scores_disjoint():
    f = frame()
    f["return_5"] = 0.0
    high = rank_selection(f, "return_5", 0.2, 17)
    low = rank_selection(f, "return_5", 0.2, 17, ascending=True)
    assert set(high.research_uid).isdisjoint(low.research_uid)
    metrics, _, _ = evaluate(f, "return_5", config())
    assert metrics["means"]["ic"] is None


def test_invalid_scores_and_keys_fail():
    f = frame()
    f.loc[0, "return_5"] = np.nan
    with pytest.raises(ValueError, match="Nonfinite"):
        rank_selection(f, "return_5", 0.2, 17)
    with pytest.raises(ValueError, match="duplicate"):
        rank_selection(pd.concat([frame(), frame()]), "return_5", 0.2, 17)


def test_support_block_is_not_scientific_rejection():
    metrics, _, _ = evaluate(frame(), "return_5", config())
    results = [{"fold": f, "score": s, "metrics": metrics} for f in [4, 5, 6] for s in config()["scores"]]
    assert all(r["verdict"] == "BLOCKED_DIRECTION_SUPPORT" for r in verdict(results, config()).values())


def test_unknown_decile_not_negative_and_does_not_change_selection():
    f = frame()
    f["decile"] = f.decile.astype("Int64")
    f.loc[9, "decile"] = pd.NA
    metrics, days, _ = evaluate(f, "return_5", config())
    assert metrics["support"]["unknown_deciles"] == 1
    assert days.iloc[0].long_count == 2
    assert days.iloc[0].long_decile_known == 1
    assert days.iloc[0].precision_d10 == 1
    assert metrics["tail_auc"] == 1
