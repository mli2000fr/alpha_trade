import numpy as np
import pandas as pd
import pytest
from scipy.stats import spearmanr

from scripts.research import us_oracle_path_trend_ranking_20261022 as s


def bars(closes):
    c = np.asarray(closes, dtype=float)
    o = np.r_[100., c[:-1]]
    return np.column_stack([o, np.maximum(o, c)+1, np.minimum(o, c)-1, c])


def test_path_not_terminal_return():
    a = s.path_metrics(bars([120]*19+[100]))
    assert a['long_area_pct'] == pytest.approx(19.)
    assert a['long_terminal_pct'] == pytest.approx(0.)
    assert a['long_persistence_pct'] == 95
    assert a['long_peak_session'] == 1


def test_same_peak_different_path():
    a = s.path_metrics(bars([120]*19+[100]))
    b = s.path_metrics(bars([100]*19+[120]))
    assert a['long_peak_close_pct'] == pytest.approx(b['long_peak_close_pct'])
    assert a['long_area_pct'] > b['long_area_pct']


def test_retracement_before_peak_not_after():
    a = s.path_metrics(bars([90, 110, 120]+[70]*17))
    assert a['long_adverse_before_peak_close_pct'] == pytest.approx(10)
    assert a['long_peak_session'] == 3
    assert a['long_mae_intraday_pct'] >= 30


def test_peak_tie_uses_first():
    a = s.path_metrics(bars([110, 80, 110]+[100]*17))
    assert a['long_peak_session'] == 1
    assert a['long_adverse_before_peak_close_pct'] == 0


def test_all_down_includes_entry_peak_zero():
    a = s.path_metrics(bars([90]*20))
    assert a['long_peak_session'] == 0
    assert a['long_peak_close_pct'] == 0
    assert a['long_adverse_before_peak_close_pct'] == 0
    assert a['short_persistence_pct'] == 100
    assert a['short_area_pct'] == pytest.approx(-a['long_area_pct'])


def test_same_day_extreme_order_is_bounds():
    x = np.tile([100, 105, 95, 101.], (20, 1))
    x[5] = [100, 130, 70, 110]
    a = s.path_metrics(x)
    assert a['long_adverse_before_high_day_lower_pct'] == pytest.approx(5)
    assert a['long_adverse_before_high_day_upper_pct'] == pytest.approx(30)


@pytest.mark.parametrize('case', ['short', 'nan', 'zero', 'invalid'])
def test_invalid_path(case):
    x = bars([100]*20)
    if case == 'short':
        x = x[:19]
    elif case == 'nan':
        x[2, 3] = np.nan
    elif case == 'zero':
        x[2, 3] = 0
    else:
        x[2, 1] = 80
    with pytest.raises(ValueError):
        s.path_metrics(x)


def test_purge_by_label_availability():
    assert s.period_for('2021-12-01', '2021-12-31') == 'DISCOVERY'
    assert s.period_for('2021-12-01', '2022-01-01') == 'PURGED_DISCOVERY'
    assert s.period_for('2022-12-01', '2023-01-01') == 'PURGED_VALIDATION'
    assert s.period_for('2026-09-30', pd.NaT) == 'IMMATURE'


def candidate_frame():
    rows = []
    for day in pd.date_range('2020-01-01', periods=4):
        for i in range(10):
            row = dict(date=day, symbol=f'S{i:02}', score=1-i/10, oracle_rank=i+1,
                       momentum_20=float(i), nonoverlap=True, constant=5,
                       long_area_pct=float(i%3), short_area_pct=-float(i%3))
            row.update({side+'_'+m: float(i) for side in ('long', 'short') for m in s.METRICS if side+'_'+m not in row})
            rows.append(row)
    return pd.DataFrame(rows)


def test_original_membership_before_future_outcomes():
    a = candidate_frame()
    s.validate_top10(a)
    original = s.select(a, 'momentum_20', 1, 3)
    a['long_area_pct'] = np.arange(len(a))[::-1]*100
    pd.testing.assert_frame_equal(original, s.select(a, 'momentum_20', 1, 3))
    assert original.symbol.unique().tolist() == ['S09', 'S08', 'S07']
    assert s.select(a, 'momentum_20', 1, 3, 'short').symbol.unique().tolist() == ['S00', 'S01', 'S02']


def test_no_top11_replacement_or_duplicate():
    a = candidate_frame()
    with pytest.raises(ValueError):
        s.validate_top10(a[a.symbol.ne('S09')])
    with pytest.raises(ValueError):
        s.validate_top10(pd.concat([a, a.iloc[:1]]))


def test_rank_ic_matches_scalar_spearman_and_constant_missing():
    a = candidate_frame()
    actual = s.daily_ic(a, ['momentum_20', 'constant'])
    g = a.iloc[:10]
    assert actual.momentum_20.iloc[0] == pytest.approx(spearmanr(g.momentum_20, g.long_area_pct).statistic)
    assert actual.constant.isna().all()


def test_policy_area_ceiling_not_return():
    a = candidate_frame()
    r = s.policy_statistics(a, 'momentum_20', 1, 3)
    assert r['rows'] == 12 and r['dates'] == 4
    assert r['no_portfolio_returns']
    assert r['hindsight_area_ceiling_not_strategy'] >= r['metrics']['area_pct']['selected']


def test_gate_requires_retracement_and_persistence_not_area_only():
    good = {'dates': 100, 'metrics': {'area_pct': {'delta_oracle': 1},
            'persistence_pct': {'delta_oracle': 0}, 'adverse_before_peak_close_pct': {'delta_oracle': 0}}}
    assert s.period_gate({'3': good, '5': good}, 30)
    good['metrics']['adverse_before_peak_close_pct']['delta_oracle'] = .01
    assert not s.period_gate({'3': good, '5': good}, 30)


def grid_case():
    days = pd.bdate_range('2020-01-01', periods=40)
    a = pd.DataFrame({'open': 100., 'high': 105., 'low': 95., 'close': 101.,
                      'volume': 10., 'instrument_id': '1', 'is_filled': 0,
                      'data_source': 'eodhd_eod', 'data_adjustment': 'split'}, index=days)
    return days, a


@pytest.mark.parametrize('change,reason', [
    ('missing', 'MISSING_OR_NONPOSITIVE_PATH'), ('filled', 'FILLED_PATH'),
    ('source', 'UNKNOWN_OR_CHANGED_DATA_SOURCE'), ('identity', 'UNKNOWN_OR_CHANGED_INSTRUMENT_ID'),
    ('basis', 'NOT_SPLIT_BASIS')])
def test_path_quality_no_fill_or_mixed_source(change, reason):
    days, a = grid_case()
    assert s.qualify_path(a, 0, days, 'S', {}) == ''
    if change == 'missing':
        a.iloc[5, a.columns.get_loc('close')] = np.nan
    if change == 'filled':
        a.iloc[5, a.columns.get_loc('is_filled')] = 1
    if change == 'source':
        a.iloc[5, a.columns.get_loc('data_source')] = 'alpaca_iex'
    if change == 'identity':
        a.iloc[5, a.columns.get_loc('instrument_id')] = '2'
    if change == 'basis':
        a.data_adjustment = 'raw'
    assert s.qualify_path(a, 0, days, 'S', {}) == reason


def test_full_window_and_knowledge_cutoff():
    days, a = grid_case()
    assert s.qualify_path(a, 25, days, 'S', {}) == 'IMMATURE_J21'
    future = pd.bdate_range('2026-10-01', periods=40)
    a.index = future
    assert s.qualify_path(a, 0, future, 'S', {}) == 'IMMATURE_J21'


def test_safe_saving_refuses_overwrite(tmp_path):
    p = tmp_path/'report.json'
    s.save(p, {'ok': True})
    with pytest.raises(FileExistsError):
        s.save(p, {'ok': False})
