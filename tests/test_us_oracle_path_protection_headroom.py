import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_path_protection_headroom as audit


def path(ohlc):
    return np.asarray([[*row, 1000, 0, 'ID1'] for row in ohlc], dtype=object)


def dates(n):
    return pd.bdate_range('2024-01-02', periods=n)


def test_stop_precedes_tp_collision():
    p = path([[100, 125, 90, 110]])
    result = audit.resolve_unit(p, dates(1), .15, .20)
    assert result['reason'] == 'initial_stop'
    assert result['value_price'] == 95


def test_gap_stop_not_nominal_loss_cap():
    p = path([[100, 105, 99, 103], [80, 82, 79, 81]])
    result = audit.resolve_unit(p, dates(2), .15, .20)
    assert result['reason'] == 'initial_stop_gap_open'
    assert result['gross_pct'] == pytest.approx(-20)


def test_favorable_gap_limit_no_invented_improvement():
    p = path([[100, 105, 99, 103], [140, 141, 130, 140]])
    result = audit.resolve_unit(p, dates(2), .15, .20)
    assert result['reason'] == 'take_profit_gap_limit'
    assert result['value_price'] == 120


def test_high_cannot_raise_same_session_stop():
    p = path([[100, 105, 98, 102], [103, 118, 100, 110]])
    result = audit.resolve_unit(p, dates(2), .15, .30)
    assert not result['closed']
    assert result['reason'] == 'OPEN_MTM'


def test_trailing_activation_next_session_and_prior_peak():
    p = path([[100, 118, 98, 110], [110, 130, 99, 120]])
    result = audit.resolve_unit(p, dates(2), .15, .30)
    assert result['reason'] == 'trailing_stop'
    assert result['value_price'] == pytest.approx(118*.85)
    assert result['value_price'] >= 95


def test_no_posthumous_future_prices():
    first = path([[100, 110, 94, 100]])
    p = np.concatenate([first, path([[np.nan, np.nan, np.nan, np.nan]])])
    a = audit.resolve_unit(first, dates(1), .15, .20)
    b = audit.resolve_unit(p, dates(2), .15, .20)
    assert a == b


def test_open_mtm_is_not_a_sold_position():
    result = audit.resolve_unit(path([[100, 105, 98, 103]]), dates(1), .15, .20)
    assert not result['closed']
    assert result['net_pct'] == pytest.approx(2.92)
    assert result['liquidation_net_pct'] < result['net_pct']
    assert result['financing_net_pct'] < result['liquidation_net_pct']


@pytest.mark.parametrize('column,value,reason', [
    (4, 0, 'MISSING_OR_NONPOSITIVE_OHLCV'),
    (0, np.nan, 'MISSING_OR_NONPOSITIVE_OHLCV'),
    (5, 1, 'FILLED_BAR'),
    (1, 90, 'INCONSISTENT_OHLC'),
    (6, None, 'MISSING_OR_CHANGED_IDENTITY'),
    (6, 'ID2', 'MISSING_OR_CHANGED_IDENTITY'),
])
def test_window_quality_is_common_to_profiles(column, value, reason):
    p = path([[100, 105, 98, 102], [102, 105, 100, 103]])
    p[1, column] = value
    assert audit.qualify_window(p) == reason


def candidate(day):
    return pd.DataFrame([dict(date=day, symbol='ABC', year=2024, oracle_rank=1,
                             score=.8, selected=True)])


def test_immaturity_excluded_even_when_every_profile_stopped():
    d = dates(3)
    p = path([[100, 105, 98, 102], [100, 105, 90, 95], [90, 95, 80, 85]])
    rows, excluded = audit.build_chunk(candidate(d[0]), {'ABC': p}, d, [], 3)
    assert rows.empty
    assert excluded.reason.tolist() == ['IMMATURE_COMMON_WINDOW']


def test_available_label_is_common_boundary_not_early_exit():
    d = dates(3)
    p = path([[100, 105, 98, 100], [100, 105, 90, 95], [90, 95, 80, 85]])
    rows, excluded = audit.build_chunk(candidate(d[0]), {'ABC': p}, d, [], 2)
    assert excluded.empty
    assert rows.label_available.iloc[0] == d[-1]
    assert rows.REFERENCE_value_date.iloc[0] == d[1]


def test_no_replacement_for_bad_future_and_reserve_ca():
    d = dates(3)
    p = path([[100, 105, 98, 100], [100, 105, 98, 103], [100, 105, 98, 103]])
    events = [dict(source='ABC', day=str(d[-1].date()))]
    rows, excluded = audit.build_chunk(candidate(d[0]), {'ABC': p}, d, events, 2)
    assert rows.empty
    assert excluded.reason.tolist() == ['CORPORATE_ACTION_WINDOW_RESERVED']


def frame(values):
    f = pd.DataFrame(dict(date=dates(len(values)), symbol=['ABC']*len(values), horizon=60))
    for k, name in enumerate(audit.PROFILES):
        f[f'{name}_net_pct'] = [row[k] for row in values]
        f[f'{name}_closed'] = True
    return f


def test_equal_profiles_no_artificial_winner_or_gain():
    f = frame([[2, 2, 2], [-5, -5, -5]])
    summary = audit.summarize(f, dates(2), interval=False)
    assert summary['tied_best_share'] == 1
    assert summary['ceiling_minus_best_constant_mean_pct'] == 0
    assert not summary['material_space_gate']
    assert all(v['best_share'] == pytest.approx(1/3) for v in summary['profiles'].values())


def test_constant_dominates_no_personalization_headroom():
    f = frame([[10, 2, 3], [11, 1, 0]])
    summary = audit.summarize(f, dates(2), interval=False)
    assert summary['best_constant_hindsight'] == 'COURT'
    assert summary['ceiling_minus_best_constant_mean_pct'] == 0
    assert not summary['material_space_gate']


def test_switching_winners_is_hindsight_not_learnability():
    f = frame([[10, 0, 0], [0, 0, 10]])
    summary = audit.summarize(f, dates(2), interval=False)
    assert summary['ceiling_minus_best_constant_mean_pct'] == 5
    assert summary['material_space_gate']
    assert not summary['learnability_proven']
    assert not summary['portfolio_return']


def test_nonoverlap_not_exit_or_outcome_based():
    d = dates(130)
    f = pd.DataFrame(dict(date=d, symbol='ABC', horizon=60, REFERENCE_closed=True))
    result = audit.nonoverlap(f, d)
    assert result.date.tolist() == [d[0], d[60], d[120]]


def test_bootstrap_deterministic_date_blocks():
    f = frame([[10, 0, 0], [0, 0, 10]])
    a = audit.block_interval(f, dates(2))
    assert a == audit.block_interval(f, dates(2))
    assert a['distinct_blocks'] == 1
    assert not a['predictive_significance']


def test_invalid_matrix_fails_closed():
    with pytest.raises(ValueError, match='nonfinite'):
        audit.ceiling_arrays(frame([[10, np.nan, 0]]))


def test_missing_weights_exception_is_only_for_known_original_models():
    assert audit.missing_archived_model('artifacts/models/model-factory-20261014052407-a4bd20/oracle_path/report.json')
    assert not audit.missing_archived_model('artifacts/models/new-model/oracle_path/report.json')
    assert not audit.missing_archived_model('artifacts/research/prices.parquet')
    assert not audit.missing_archived_model('backtesting/simulator.py')
