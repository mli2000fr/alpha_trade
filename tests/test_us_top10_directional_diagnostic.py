import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_directional_hierarchy_diagnostic import ARMS, causal_training, target
from scripts.research.us_top10_directional_diagnostic import (
    CONFIG, ORACLE, block_test, period_pass, reference_metrics, selection_metrics, top10_only,
)


@pytest.fixture
def cfg():
    return json.loads(CONFIG.read_text())


def frame(count=20, days=1):
    result = pd.DataFrame({'date': np.repeat(pd.bdate_range('2020-01-01', periods=days), count),
                           'symbol': [f'S{i:02}' for i in range(count)]*days,
                           'oracle_rank': list(range(1, count+1))*days,
                           'oracle_decile': ([1, 10]+[5]*(count-2))*days})
    for arm in ARMS:
        result[arm] = np.tile(np.arange(count)/count, days)
    return result


def test_config_explicit_top10_not_percent_or_top50(cfg):
    assert cfg['training_top_titles'] == cfg['evaluation_top_titles'] == 10
    assert cfg['primary_selection_count'] == 3
    assert cfg['trajectory_sessions'] == [5, 10]
    assert cfg['practical_tasks'] == ['D10_VS_REST', 'D1_VS_REST']
    assert not cfg['automatic_promotion']


def test_top10_keeps_unknowns_never_replaces_with_11():
    f = frame()
    f.loc[0, 'oracle_decile'] = np.nan
    result = top10_only(f)
    assert len(result) == 10 and result.oracle_rank.max() == 10
    assert result.iloc[0].symbol == 'S00' and pd.isna(result.iloc[0].oracle_decile)


@pytest.mark.parametrize('problem', ['duplicate_symbol', 'duplicate_rank', 'missing', 'fractional'])
def test_top10_invalid_keys_fail_closed(problem):
    f = frame()
    if problem == 'duplicate_symbol':
        f.loc[1, 'symbol'] = 'S00'
    elif problem == 'duplicate_rank':
        f.loc[1, 'oracle_rank'] = 1
    elif problem == 'fractional':
        f['oracle_rank'] = f.oracle_rank.astype(float)
        f.loc[8, 'oracle_rank'] = 9.5
    else:
        f = f.drop(index=0)
    with pytest.raises(ValueError):
        top10_only(f)


def test_top3_has_middle_deciles_and_unknowns_before_evaluation():
    f = top10_only(frame())
    f['oracle_decile'] = f.oracle_decile.astype(float)
    f.loc[f.oracle_rank.ge(8), 'oracle_decile'] = [5., np.nan, 1.]
    rows = selection_metrics(f, [3])
    chosen = rows.loc[rows.arm.eq('GLOBAL_J')].iloc[0]
    assert chosen.selected_count == 3 and chosen.known_count == 2
    assert chosen.d1 == .5 and chosen.d10 == 0
    assert chosen.label_coverage == 2/3


def test_original_oracle_order_baseline_does_not_use_directional_score():
    f = top10_only(frame())
    rows = selection_metrics(f, [3])
    original = rows.loc[rows.arm.eq(ORACLE)].iloc[0]
    assert original.d1_count == original.d10_count == 1
    assert original.selected_count == original.known_count == 3


def test_all_ten_selection_matches_pool_for_every_arm():
    f = top10_only(frame(days=3))
    rows = selection_metrics(f, [10])
    assert rows.d1.eq(.1).all() and rows.d10.eq(.1).all()
    assert rows.selected_count.eq(10).all()


@pytest.mark.parametrize('count', [0, 11, True, 3.5])
def test_illegal_selection_counts_rejected(count):
    with pytest.raises(ValueError):
        selection_metrics(top10_only(frame()), [count])


def test_test_dates_do_not_enter_train_and_only_top10_can_be_trained():
    f = top10_only(frame(days=3))
    f['oracle_available_date'] = pd.Timestamp('2020-01-31')
    f.loc[f.date.eq(pd.Timestamp('2020-01-01')), 'oracle_available_date'] = pd.Timestamp('2020-01-15')
    train = causal_training(f, '2020-01-31')
    assert len(train) == 10 and train.oracle_rank.max() == 10
    assert target(train, 'D10_VS_REST').notna().all()  # includes all middle deciles
    assert target(train, 'D1_VS_D10').notna().sum() == 2


def test_reference_prior_constant_auc_and_brier_defined_without_tail_discard():
    f = top10_only(frame(days=2))
    f.loc[f.oracle_rank.isin([3, 4]), 'oracle_decile'] = [10, 1]*2
    rows = reference_metrics(f, 'D10_VS_REST', .2)
    constant = rows.loc[rows.arm.eq('TRAIN_PRIOR')]
    assert constant.auc.eq(.5).all()
    assert np.allclose(constant.brier, .16)


def test_insufficient_classes_not_invented_for_auc():
    f = top10_only(frame())
    rows = reference_metrics(f, 'D10_VS_REST', .1)
    assert rows.auc.isna().all()  # min two positives per day
    assert rows.brier.notna().all()


def test_sign_flip_reproducible_and_low_support_not_significant(cfg):
    calendar = pd.bdate_range('2020-01-01', periods=10*63)
    delta = pd.Series(.03, index=calendar)
    first = block_test(delta, calendar, cfg)
    assert first == block_test(delta, calendar, cfg)
    assert first['p_raw'] < .05 and first['mean_delta'] > 0
    assert block_test(delta.iloc[:63], calendar, cfg)['p_raw'] is None
    assert block_test(delta.iloc[:10], calendar, cfg)['blocks'] == 0


def test_gate_rejects_more_d10_if_more_d1_or_bad_probabilities(cfg):
    good = dict(auc=.56, auc_gain=.03, brier_gain=.01, target_lift=.05, opposite_lift=-.01, dates=100)
    assert period_pass(good, cfg)
    assert not period_pass({**good, 'opposite_lift': .01}, cfg)
    assert not period_pass({**good, 'brier_gain': -.01}, cfg)
    assert not period_pass({**good, 'auc_gain': None}, cfg)


def test_research_script_has_no_live_call_path():
    code = Path('scripts/research/us_top10_directional_diagnostic.py').read_text()
    for forbidden in ('get_sqlalchemy_engine', 'requests.', 'subprocess.', 'execute_approved'):
        assert forbidden not in code
