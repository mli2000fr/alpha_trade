import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from scripts.research.us_oracle_dominant_path_audit import (
    dominant, evaluate_paths, classify_days, auc_matrix, task_labels,
    frozen_orientation, screen_leads, annual_summary,
)
from tests.test_us_oracle_path_excursions import fixture
from scripts.research.us_oracle_path_excursions import evaluate_symbol


def test_larger_absolute_side_and_ambiguous_ties():
    values = dominant([.25, .25, .25, 0, np.nan], [.10, .30, .25, 0, .1])
    np.testing.assert_allclose(values[:2], [.25, -.30])
    assert np.isnan(values[2:]).all()


def test_path_peak_before_terminal_loss():
    sessions, selected, bars = fixture()
    bars.loc[5, ['open', 'high', 'low', 'close', 'adj_close']] = 125.
    bars.loc[20, ['open', 'high', 'low', 'close', 'adj_close']] = 99.
    selected['future_return'] = -.01
    result = evaluate_paths(selected, bars, sessions, {}).iloc[0]
    assert result.path_qualified
    assert np.isclose(result.path_value, .25)
    assert np.isclose(result.terminal_value, -.01)


@pytest.mark.parametrize('mutation', ['none', 'split', 'missing', 'source', 'identity', 'zero_volume', 'endpoint', 'filled'])
def test_vectorized_qualification_agrees_with_previous_contract(mutation):
    sessions, selected, bars = fixture()
    bars.loc[5, 'high'] = 125.
    if mutation == 'split':
        bars.loc[10:, ['open', 'high', 'low', 'close']] /= 2
    elif mutation == 'missing':
        bars = bars.drop(index=4)
    elif mutation == 'source':
        bars.loc[5, 'data_source'] = 'other'
    elif mutation == 'identity':
        bars.loc[5, 'instrument_id'] = 2
    elif mutation == 'zero_volume':
        bars.loc[5, 'volume'] = 0
    elif mutation == 'endpoint':
        selected['future_return'] = .3
    elif mutation == 'filled':
        bars.loc[5, 'is_filled'] = 1
    original = evaluate_symbol(selected, bars, sessions, {}).iloc[0]
    new = evaluate_paths(selected, bars, sessions, {}).iloc[0]
    assert new.path_qualified == original.path_qualified
    if new.path_qualified:
        assert np.isclose(new.up_excursion, original.up_excursion)
        assert np.isclose(new.down_excursion, original.down_excursion)
    else:
        assert np.isnan(new.path_value)


def test_day_zero_and_day21_excluded_and_exact_calendar():
    sessions, selected, bars = fixture()
    bars.loc[0, 'high'], bars.loc[21, 'high'] = 200., 250.
    result = evaluate_paths(selected, bars, sessions, {}).iloc[0]
    assert result.path_qualified and result.dominant_tie
    bars.loc[20, 'low'] = 90.
    result = evaluate_paths(selected, bars, sessions, {}).iloc[0]
    assert np.isclose(result.path_value, -.1)
    selected['oracle_available_date'] = sessions[22]
    result = evaluate_paths(selected, bars, sessions, {}).iloc[0]
    assert not result.path_qualified and 'CALENDAR' in result.path_flags


def universe_fixture():
    n = 100
    return pd.DataFrame(dict(date=pd.Timestamp('2025-01-02'), symbol=[f'S{i:03d}' for i in range(n)],
        path_qualified=True, path_value=np.arange(1, n + 1) / 100,
        close_path_value=np.arange(1, n + 1) / 100,
        terminal_value=np.arange(1, n + 1) / 100,
        in_pool=np.arange(n) >= 50))


def test_deciles_use_full_universe_not_only_oracle_atr_pool():
    frame = classify_days(universe_fixture())
    assert frame.loc[frame.symbol.eq('S050'), 'path_decile'].iloc[0] == 6
    assert frame[frame.in_pool].path_decile.min() == 6
    assert frame.path_decile.eq(10).sum() == 10
    assert frame.path_decile.eq(1).sum() == 10


def test_same_paired_denominator_and_missing_never_replaced():
    source = universe_fixture()
    source.loc[99, 'path_value'] = np.nan
    result = classify_days(source)
    assert not result.loc[99, 'paired_qualified']
    assert np.isnan(result.loc[99, 'terminal_decile'])
    assert np.isnan(result.loc[99, 'path_decile'])
    assert np.isclose(result.daily_coverage.iloc[0], .99)
    source.loc[:9, 'path_qualified'] = False
    assert not classify_days(source).audit_eligible.any()


def test_auc_ties_constant_and_monotonic_alias_invariance():
    labels = np.asarray([0] * 5 + [1] * 5)
    values = np.column_stack([np.arange(10), np.ones(10), [0, 1, 0, 1, 1, 0, 1, 1, 0, 1]])
    auc = auc_matrix(labels, values)
    expected = [roc_auc_score(labels, values[:, i]) for i in range(3)]
    np.testing.assert_allclose(auc, expected)
    ranked = pd.DataFrame(values).rank(pct=True).to_numpy()
    np.testing.assert_allclose(auc_matrix(labels, ranked), auc)
    with pytest.raises(ValueError, match='Nonfinite'):
        auc_matrix(labels, values * np.nan)


def test_orientation_ignores_future_and_unmatured_development():
    data = pd.DataFrame(dict(date=pd.to_datetime(['2022-11-01', '2022-12-30', '2025-01-01']),
        available_date=pd.to_datetime(['2022-12-01', '2023-02-01', '2025-02-01']),
        target='path', task='D1_VS_D10', feature='feature', raw_auc=[.4, 1., 1.]))
    assert frozen_orientation(data).orientation.iloc[0] == -1


def test_task_sign_is_distinct_from_daily_tail_class():
    data = pd.DataFrame(dict(path_decile=[1., 5., 10.], path_value=[-.2, .01, .3]))
    keep, y = task_labels(data, 'path', 'D1_VS_D10')
    np.testing.assert_array_equal(keep, [True, False, True])
    np.testing.assert_array_equal(y, [0, 1])
    keep, y = task_labels(data, 'path', 'SIGN')
    assert keep.all()
    np.testing.assert_array_equal(y, [0, 1, 1])


def test_registry_break_and_duplicate_prices_reserved():
    from modelFactory.oracle.security_continuity import SecurityDiscontinuity
    sessions, selected, bars = fixture()
    registry = {'TEST': (SecurityDiscontinuity('TEST', sessions[5], sessions[6], 'fixture'),)}
    result = evaluate_paths(selected, bars, sessions, registry).iloc[0]
    assert not result.path_qualified and 'KNOWN_IDENTITY_BREAK' in result.path_flags
    with pytest.raises(ValueError, match='Duplicate'):
        evaluate_paths(selected, pd.concat([bars, bars.iloc[:1]]), sessions, {})


def test_constant_market_feature_stays_at_chance_each_day():
    labels = np.asarray([0] * 20 + [1] * 10)
    # Pooled days could appear correlated with class prevalence; intra-date no.
    np.testing.assert_allclose(auc_matrix(labels, np.full((30, 2), 7.)), [.5, .5])


def test_screen_never_selects_feature_using_confirmation_auc():
    daily = pd.DataFrame(dict(date=pd.to_datetime(['2022-11-01'] * 12),
        available_date=pd.to_datetime(['2022-12-01'] * 12), target='path', task='D1_VS_D10',
        feature=[f'f{i}' for i in range(12)], auc=np.arange(12) / 100 + .50))
    annual = pd.DataFrame([dict(target='path', task='D1_VS_D10', feature=f'f{i}',
        year=year, mean_daily_auc=.9 if i == 0 else .55, ci_low=.51, days=100)
        for i in range(12) for year in [2023, 2024, 2025, 2026]])
    leads = screen_leads(annual, daily, list(daily.feature))
    assert len(leads) == 10 and 'f0' not in [row['feature'] for row in leads]


def test_annual_confirmation_never_flips_frozen_orientation():
    daily = pd.DataFrame(dict(date=pd.date_range('2025-01-01', periods=10),
        available_date=pd.date_range('2025-02-01', periods=10), target='path', task='SIGN',
        feature='f', raw_auc=.9, observations=100, positives=50, negatives=50))
    orientation = pd.DataFrame([dict(target='path', task='SIGN', feature='f', orientation=-1)])
    annual, _ = annual_summary(daily, orientation)
    assert np.isclose(annual.mean_daily_auc.iloc[0], .1)
