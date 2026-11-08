from unittest.mock import patch

import pandas as pd
import pytest

from backtesting.cli._impl import _build_parser
from ihm.services.backtesting_runner import BacktestRunOptions, build_backtesting_command
from modelFactory.predictor import CascadePrediction, apply_cascade_to_predictions, cascade_select


DAY = "2025-01-02"
CONFIG = {"top_pct": .20, "min_prob_classification": .55,
          "min_prob_regression": .55, "oracle_atr_enabled": False}


def scores(n=100):
    return {f"S{i:03}": float(n-i) for i in range(n)}


@pytest.mark.parametrize("top_n", [10, 20, 50])
def test_fixed_count_survives_percentile_cutoff_and_orders_by_oracle(top_n):
    with patch("modelFactory.predictor.load_cascade_config", return_value=CONFIG):
        selected = cascade_select(DAY, "batch", {}, rank_mode="extreme_gate",
            oracle_rank_map={DAY: scores()}, extreme_gate_pct=.10,
            extreme_gate_top_n=top_n, extreme_gate_per_symbol="bypass")
    assert [s for _, s, _ in selected] == list(scores())[:top_n]


def test_fixed_count_ties_are_deterministic_and_small_universe_is_not_padded():
    tied = {f"S{i:03}": 1. for i in reversed(range(15))}
    with patch("modelFactory.predictor.load_cascade_config", return_value=CONFIG):
        selected = cascade_select(DAY, "batch", {}, rank_mode="extreme_gate",
            oracle_rank_map={DAY: tied}, extreme_gate_top_n=10, extreme_gate_per_symbol="bypass")
        small = cascade_select(DAY, "batch", {}, rank_mode="extreme_gate",
            oracle_rank_map={DAY: scores(3)}, extreme_gate_top_n=50, extreme_gate_per_symbol="bypass")
    assert [s for _, s, _ in selected] == sorted(tied)[:10]
    assert len(small) == 3


def test_atr_filters_requested_pool_without_refilling_or_reranking():
    atr = {s: 1. for s in scores()}
    atr.update({"S000": 100., "S009": 99., "S010": 98.})
    # A second ATR population fills ranks above the cutoff. Ranking ATR only
    # inside TOP10 would admit most of the tied values and change the result.
    atr.update({f"S{i:03}": float(i) for i in range(70, 90)})
    with patch("modelFactory.predictor.load_cascade_config", return_value=CONFIG):
        selected = cascade_select(DAY, "batch", {}, rank_mode="extreme_gate",
            oracle_rank_map={DAY: scores()}, extreme_gate_top_n=10,
            extreme_gate_per_symbol="bypass", oracle_atr_enabled=True, oracle_atr_values=atr)
    assert [s for _, s, _ in selected] == ["S000", "S009"]


def test_per_symbol_veto_does_not_admit_rank_eleven():
    preds = {s: CascadePrediction(s, long_prob=.9 if s != "S000" else .1, short_prob=.1)
             for s in scores()}
    with patch("modelFactory.predictor.load_cascade_config", return_value=CONFIG):
        selected = cascade_select(DAY, "batch", preds, rank_mode="extreme_gate",
            oracle_rank_map={DAY: scores()}, extreme_gate_top_n=10)
    assert [s for _, s, _ in selected] == list(scores())[1:10]


@pytest.mark.parametrize("policy,expected", [
    ("top20_then_filter", list(scores())[5:10]),
    ("filter_then_top20", list(scores())[5:15]),
])
def test_fixed_count_respects_tradable_policy(policy, expected):
    with patch("modelFactory.predictor.load_cascade_config", return_value=CONFIG):
        selected = cascade_select(DAY, "batch", {}, rank_mode="extreme_gate",
            oracle_rank_map={DAY: scores()}, extreme_gate_top_n=10, extreme_gate_per_symbol="bypass",
            oracle_tradable_policy=policy, oracle_tradable_symbols=set(list(scores())[5:]))
    assert [s for _, s, _ in selected] == expected


@pytest.mark.parametrize("pct,count", [(.10, 11), (.20, 21)])
def test_percentile_keeps_existing_inclusive_threshold(pct, count):
    with patch("modelFactory.predictor.load_cascade_config", return_value=CONFIG):
        selected = cascade_select(DAY, "batch", {}, rank_mode="extreme_gate",
            oracle_rank_map={DAY: scores()}, extreme_gate_pct=pct, extreme_gate_per_symbol="bypass")
    assert len(selected) == count


def test_dataframe_cascade_uses_fixed_count_separately_each_day():
    other = "2025-01-03"
    frame = pd.DataFrame([dict(trade_date=day, symbol=s, predicted_side="long",
        proba_long=.8, proba_short=.1, proba_flat=.1) for day in (DAY, other) for s in scores()])
    with patch("modelFactory.predictor.load_cascade_config", return_value=CONFIG):
        result = apply_cascade_to_predictions(frame, "batch", rank_mode="extreme_gate",
            oracle_rank_map={DAY: scores(), other: {s: -v for s,v in scores().items()}},
            extreme_gate_top_n=20, extreme_gate_per_symbol="bypass")
    active = result[result.predicted_side.eq("long")]
    assert set(active[active.trade_date.eq(DAY)].symbol) == set(list(scores())[:20])
    assert set(active[active.trade_date.eq(other)].symbol) == set(list(scores())[-20:])


@pytest.mark.parametrize("mode", ["ml", "extreme_gate", "extreme_gate_directional"])
@pytest.mark.parametrize("top_n,pct", [(None,.10), (None,.20), (10,.20), (20,.20), (50,.20)])
def test_scope_command_parser_roundtrip_including_automatic_oracle_mode(mode, top_n, pct):
    command = build_backtesting_command("run", BacktestRunOptions(start=DAY,
        cascade_rank_mode=mode, extreme_gate_top_n=top_n, extreme_gate_pct=pct))
    args = _build_parser().parse_args(command[command.index("run"):])
    assert args.extreme_gate_top_n == top_n
    assert args.extreme_gate_pct == (pct if top_n is None else None)


def test_selector_changes_and_persists_through_real_streamlit_reruns():
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_string('''
import streamlit as st
from ihm.components.backtest_oracle_scope import render_oracle_scope
st.session_state["scope_result"] = render_oracle_scope("ml")
''').run()
    assert not app.exception
    assert app.session_state["scope_result"] == (.20, 20)
    for selection, expected in [("top10pct",(.10,None)), ("top10",(.20,10)),
                                ("top20",(.20,20)), ("top50",(.20,50)), ("top20pct",(.20,None))]:
        app.selectbox(key="bt_run_oracle_scope").set_value(selection).run()
        assert not app.exception
        assert app.session_state["scope_result"] == expected
        app.run()
        assert app.session_state["scope_result"] == expected


def test_invalid_fixed_count_is_not_silently_used_as_percentile():
    with pytest.raises(ValueError, match="TOP Oracle"):
        cascade_select(DAY, "batch", {}, extreme_gate_top_n=0)
    with pytest.raises(SystemExit):
        _build_parser().parse_args(["run", "--start", DAY, "--extreme-gate-top-n", "0"])
