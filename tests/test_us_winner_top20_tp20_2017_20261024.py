from dataclasses import asdict
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from scripts.research import us_winner_top20_tp20_2017_20261024 as study
from scripts.research.us_winner_sl3_tp7_tr3_open11_audit_20261023 import scalar_exit


def test_tp_is_the_only_configuration_change():
    p = study.capacity.read_json(study.BASELINE/'protocol.json')
    before = asdict(study.capacity.configuration(p))
    with study.replay_context():
        after = asdict(study.capacity.configuration(p))
    assert before['exec_config']['winner_pyramiding']['take_profit_pct'] is None
    assert after['exec_config']['winner_pyramiding']['take_profit_pct'] == .2
    after['exec_config']['winner_pyramiding']['take_profit_pct'] = None
    assert before == after


def test_context_restores_the_sealed_experiment_even_after_error():
    root, profile = study.capacity.ROOT, study.capacity.PROFILE
    with pytest.raises(RuntimeError):
        with study.replay_context():
            assert study.capacity.ROOT == study.ROOT
            assert study.capacity.PROFILE['take_profit_pct'] == .2
            raise RuntimeError('test')
    assert study.capacity.ROOT == root and study.capacity.PROFILE is profile


@pytest.mark.parametrize('opening,high,low,reason,price', [
    (100., 121., 99., 'TP', 120.),
    (130., 132., 129., 'TP_GAP_CAPPED', 120.),
    (100., 125., 94., 'STOP', 95.),
])
def test_unchanged_scalar_tp_gap_and_collision_contract(opening, high, low, reason, price):
    stamp = pd.Timestamp(datetime(2017, 7, 3, 14, tzinfo=timezone.utc))
    path = pd.DataFrame([dict(bar_timestamp=stamp, bar_end_timestamp=stamp+timedelta(minutes=5),
                             open=opening, high=high, low=low, close=opening)])
    result = scalar_exit(path, stamp, 100., stamp+timedelta(days=30), sl=.05, tp=.2, trail=None)
    assert result[1:] == (price, reason)


def test_matched_comparisons_are_by_coverage_arm_not_best_result():
    old, new = {}, {}
    for arm in study.capacity.ARMS:
        old[arm] = dict(arm=arm, return_pct=10., max_drawdown_pct=-6., final_equity=4400.,
                        average_gross_capital=1000., win_pct=30.)
        new[arm] = dict(old[arm], return_pct=11., final_equity=4440., max_drawdown_pct=-7.)
    rows, deltas = study.comparison_rows(old, new)
    assert len(rows) == 4
    assert [r['variant'] for r in rows] == ['NO_TP', 'TP20', 'NO_TP', 'TP20']
    assert all(d['return_delta_pp'] == 1. and d['drawdown_delta_pp'] == -1. for d in deltas)
