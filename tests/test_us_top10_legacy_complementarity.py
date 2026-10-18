import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_top10_legacy_complementarity import (
    BASELINE, CONFIG, adjust_family, keys, matched_reference, outcomes, pair_diagnostics,
    period_gate, rank_full_ten, recipe, report_statistics, shortlist,
)


def sample(days=2):
    frame = pd.DataFrame(dict(date=np.repeat(pd.bdate_range('2024-01-02', periods=days), 10),
                             symbol=list('ABCDEFGHIJ')*days, oracle_rank=list(range(1, 11))*days,
                             oracle_decile=[1., 10., 5., 1., 10., 5., 5., 5., 5., 5.]*days,
                             terminal_return=np.tile(np.arange(10), days)))
    frame[BASELINE] = np.tile(np.arange(10, dtype=float), days)
    frame['OTHER'] = frame[BASELINE]
    return frame


def test_protocol_small_fixed_family_no_learning():
    cfg = json.loads(CONFIG.read_text())
    assert len(cfg['recipes']) == 6 and cfg['primary_recipe'] == 'MEAN_D10_AVOID_D1'
    assert cfg['selection_count'] == 3
    assert cfg['no_training'] and cfg['no_sql'] and cfg['no_provider_calls']
    assert cfg['no_weight_optimization'] and cfg['not_an_independent_holdout']
    assert all(not c.startswith('E23_') for r in cfg['recipes'] for c in r['components'])


@pytest.mark.parametrize('bad', [np.nan, np.inf, -np.inf])
def test_partial_scores_invalidate_whole_ten_not_survivor_rank(bad):
    frame = sample()
    frame.loc[0, 'OTHER'] = bad
    rank = rank_full_ten(frame, [BASELINE, 'OTHER'])
    assert rank.loc[:9, 'OTHER'].isna().all()
    assert rank.loc[10:, 'OTHER'].notna().all()
    assert rank[BASELINE].notna().all()


def test_ranking_does_not_depend_on_future_outcome():
    frame = sample()
    before = rank_full_ten(frame, [BASELINE, 'OTHER'])
    frame['oracle_decile'] = np.nan
    frame['terminal_return'] = -10000
    pd.testing.assert_frame_equal(before, rank_full_ten(frame, [BASELINE, 'OTHER']))


def test_ties_use_original_oracle_order_no_future_replacement():
    frame = sample(1)
    frame[BASELINE] = 1.
    frame.loc[0, 'oracle_decile'] = np.nan
    chosen = shortlist(frame, frame[BASELINE])
    assert chosen[chosen].index.tolist() == [0, 1, 2]
    result = outcomes(frame, chosen, pd.Series(True, index=frame.index)).iloc[0]
    assert result.selected_count == 3 and result.known_count == 2
    assert not result.complete_labels and result.d1 == 0 and result.d10 == .5


def test_mean_never_neutral_fills_or_skips_missing():
    frame = sample()
    frame.loc[0, 'OTHER'] = np.nan
    score, selected, ready = recipe(frame, dict(kind='mean', components=[BASELINE, 'OTHER']))
    assert score.iloc[:10].isna().all() and not selected.iloc[:10].any()
    assert not ready.iloc[:10].any() and ready.iloc[10:].all()
    assert selected.iloc[10:].sum() == 3


def test_future_filtered_legacy_never_used_in_recipe():
    with pytest.raises(ValueError, match='Future-filtered'):
        recipe(sample(), dict(kind='mean', components=[BASELINE, 'E23_C_SENTIMENT_PATH']))


def test_agreement_can_abstain_and_uses_matched_size_reference():
    frame = sample(1)
    frame['OTHER'] = -frame[BASELINE]
    _, chosen, ready = recipe(frame, dict(kind='intersection', components=[BASELINE, 'OTHER'], top_each=5))
    assert not chosen.any() and ready.all()
    result = outcomes(frame, chosen, ready)
    reference = matched_reference(frame, result.selected_count, frame[BASELINE])
    assert reference.selected_count.eq(0).all() and reference.d10.isna().all()


@pytest.mark.parametrize('count', [1, 2, 3])
def test_matched_reference_does_not_confuse_lower_count_with_selection_gain(count):
    frame = sample()
    counts = pd.Series([count, 0], index=frame.date.drop_duplicates())
    result = matched_reference(frame, counts, frame[BASELINE])
    assert result.selected_count.tolist() == [count, 0]
    assert pd.isna(result.iloc[1].d1)


def test_identical_signals_no_spurious_residual_information():
    frame = sample()
    result = pair_diagnostics(frame, BASELINE, 'OTHER')
    assert np.allclose(result.score_spearman, 1)
    assert result.residual_ic.isna().all()
    assert result.overlap.eq(1).all()
    assert result[['removed_d1', 'lost_d10', 'added_d10', 'introduced_d1']].eq(0).all().all()


def test_replacement_counts_and_full_label_dates_only():
    frame = sample()
    frame['OTHER'] = -frame[BASELINE]
    frame.loc[10, 'oracle_decile'] = np.nan
    result = pair_diagnostics(frame, BASELINE, 'OTHER')
    assert len(result) == 1
    row = result.iloc[0]
    assert row.overlap == 0 and row.added_d10 == 1 and row.introduced_d1 == 1
    assert row.removed_d1 == row.lost_d10 == 0


def test_empty_or_unknown_not_a_zero_failure():
    frame = sample(1)
    frame['oracle_decile'] = np.nan
    result = outcomes(frame, shortlist(frame, frame[BASELINE]), pd.Series(True, index=frame.index))
    assert result.d10.isna().all() and result.known_count.eq(0).all()


def test_gate_requires_both_tails_coverage_and_dates():
    cfg = json.loads(CONFIG.read_text())
    row = dict(coverage=1., evaluated_dates=100, d10_lift=.04, d1_reduction=.02)
    assert period_gate(row, cfg)
    for key, bad in [('coverage', .5), ('evaluated_dates', 10), ('d10_lift', .02), ('d1_reduction', -.02), ('d1_reduction', None)]:
        assert not period_gate({**row, key: bad}, cfg)


def test_duplicate_identity_rejected():
    frame = sample(1)
    with pytest.raises(ValueError, match='duplicate'):
        keys(pd.concat([frame, frame.iloc[:1]]))


def test_unavailable_comparison_kept_in_declared_multiplicity_family():
    result = adjust_family({'a': {'p_raw': .02}, 'b': {'p_raw': .1}, 'missing': {'p_raw': None}})
    assert result['a'] == pytest.approx(.06)
    assert result['b'] == pytest.approx(.2)
    assert result['missing'] is None


def test_no_training_sql_provider_or_broker_in_audit():
    code = Path('scripts/research/us_top10_legacy_complementarity.py').read_text()
    for operation in ('.fit(', '.fit_transform(', 'get_sqlalchemy_engine(', 'create_engine(', 'requests.', 'httpx.', 'OpenAI(', 'submit_order('):
        assert operation not in code


def test_annual_stats_exclude_unknown_labels_without_reranking():
    frame = sample()
    frame.loc[0, 'oracle_decile'] = np.nan
    from scripts.research.us_top10_legacy_complementarity import evaluate
    daily = evaluate(frame, BASELINE)
    row = report_statistics(daily, {})[0]
    assert row['dates_total'] == 2 and row['ready_dates'] == 2 and row['evaluated_dates'] == 1

