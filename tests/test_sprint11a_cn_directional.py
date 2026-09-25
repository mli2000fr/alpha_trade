"""Contrats anti-fuite du diagnostic directionnel CN Sprint 11-A."""

from __future__ import annotations

import pandas as pd
import pytest

from modelFactory.cn_directional_diagnostic import (
    DEFAULT_CONFIG,
    combine_oos,
    counts,
    load_protocol,
    metrics,
    policy_masks,
    prepare_pool,
)


def _predictions() -> pd.DataFrame:
    values = []
    for index in range(20):
        values.append({
            "market_code": "CN_A",
            "session_date": pd.Timestamp("2023-06-01"),
            "instrument_id": f"CN{index:03}",
            "board_code": "SH_MAIN",
            "cn_breadth_1": 0.55,
            "target_quality_valid": index != 19,
            "oracle_decile": pd.NA if index == 19 else (1 if index < 4 else 10 if index >= 16 else 5),
            "future_return": float(index - 10) / 100 if index != 19 else float("nan"),
            "execution_data_eligible": index != 19,
            "oracle_top20": True,
            "baseline_score": float(index),
            "rank_score": float(index),
        })
    return pd.DataFrame(values)


def test_protocol_explicitly_exploratory_and_not_serving() -> None:
    config = load_protocol(DEFAULT_CONFIG)
    assert config["evidence_level"] == "exploratory_not_independent_confirmation"
    assert config["decision_gate"] == "none_exploratory"
    assert not config["serving_enabled"] and not config["backtest_enabled"]


def test_model_predictions_must_have_same_labels_and_pool() -> None:
    first = _predictions()
    second = first.copy()
    second["rank_score"] = -second["rank_score"]
    combined = combine_oos(first, second)
    assert len(combined) == 20
    assert combined["score_lightgbm"].iloc[0] == -combined["score_catboost"].iloc[0]
    second.loc[0, "oracle_top20"] = False
    with pytest.raises(RuntimeError, match="oracle_top20"):
        combine_oos(first, second)


def test_top_selection_is_before_label_filter() -> None:
    first = _predictions()
    second = first.copy()
    combined = combine_oos(first, second)
    pool, audit = prepare_pool(combined, minimum=20)
    masks = policy_masks(pool, load_protocol(DEFAULT_CONFIG))
    # Le meilleur score est précisément un label invalide ; il occupe sa
    # place dans TOP10 au lieu d'être remplacé a posteriori.
    selected = pool.loc[masks["lightgbm_long_top10"]]
    assert len(selected) == 2
    assert selected["instrument_id"].tolist() == ["CN018", "CN019"]
    assert int(selected["target_quality_valid"].sum()) == 1
    assert audit["pool_rows"] == 20


def test_veto_and_metrics_use_fixed_pool_denominator() -> None:
    first = _predictions()
    pool, _ = prepare_pool(combine_oos(first, first.copy()), minimum=20)
    masks = policy_masks(pool, load_protocol(DEFAULT_CONFIG))
    all_counts = counts(pool, masks["oracle_all"])
    veto_counts = counts(pool, masks["reversal_veto_bottom20"])
    result = metrics(veto_counts, all_counts)
    assert result["selected"] == 16
    assert result["coverage"] == 0.8
    # Le veto réversion écarte les quatre scores les plus hauts (D10).
    assert result["d10_retention"] < 1
    assert result["d1_retention"] == 1
