import numpy as np
import pandas as pd
import pytest

from scripts.research import us_h10_h20_common_data as s
from scripts.research import us_h10_price_readiness as q
from modelFactory.oracle_path.labels import symbol_paths
from tests.test_us_tradable_symbol_reliability import bars


def sample():
    f = bars(90).rename_axis('date').reset_index(); f['symbol'] = 'A'; f['adj_close'] = f.close
    return f


def test_h20_target_identical_to_original_on_same_prices():
    f = sample(); days = pd.DatetimeIndex(f.date)
    a, _, _ = s.symbol_targets(f, days, horizon=20, start=days[0], end=days[-1])
    b, _ = symbol_paths(f, days, start=days[0], end=days[-1], registry={})
    pd.testing.assert_frame_equal(a, b)


def test_h10_ignores_later_peak_and_availability_is_next_session():
    f = sample(); f[['open', 'close', 'adj_close']] = 100.; f.high = 101.; f.low = 99.
    f.loc[15, 'high'] = 160.
    a, _, _ = s.symbol_targets(f, f.date, horizon=10, start=f.date.iloc[0], end=f.date.iloc[-1])
    b, _, _ = s.symbol_targets(f, f.date, horizon=20, start=f.date.iloc[0], end=f.date.iloc[-1])
    assert a.path_amplitude.iloc[0] == pytest.approx(.01)
    assert b.path_amplitude.iloc[0] == pytest.approx(.6)
    assert a.oracle_available_date.iloc[0] == f.date.iloc[11]


def test_future_missing_does_not_delete_observable_j():
    f = sample(); f.loc[10, 'is_filled'] = 1
    a, _, _ = s.symbol_targets(f, f.date, horizon=20, start=f.date.iloc[0], end=f.date.iloc[-1])
    assert a.date.iloc[0] == f.date.iloc[0]
    assert not a.path_qualified.iloc[0] and np.isnan(a.path_amplitude.iloc[0])


def test_past_guard_not_triggered_before_observation():
    f = pd.DataFrame(dict(date=pd.to_datetime(['2026-05-29', '2026-06-01']), symbol='A', x=1.))
    assert s.feature_eligible(f, [dict(symbol='A', start='2026-06-01')], ['x']).tolist() == [True, False]


def test_price_reserve_never_fabricates_an_event_return():
    f = sample(); cutoff = f.date.iloc[20]
    a, _, _ = s.symbol_targets(f, f.date, horizon=10, start=f.date.iloc[0], end=f.date.iloc[-1], price_reserve=dict(start=cutoff))
    assert a.path_qualified.iloc[0]
    assert not a.path_qualified.iloc[10]
    assert np.isnan(a.path_amplitude.iloc[10])


def test_common_dates_504_126_with_common_h20_embargo():
    days = pd.bdate_range('2016-01-01', '2026-09-30')
    f = s.frozen_annual_dates(days, 2025)
    assert len(f['train']) == 504 and len(f['val']) == 126
    assert days.get_loc(f['train'][-1])+21 < days.get_loc(f['val'][0])
    assert days.get_loc(f['val'][-1])+21 < days.get_loc(f['test'][0])
    assert not set(f['test']) & set(f['train'])


def test_only_official_uniform_factor_allowed_not_nearest_arbitrary_ratio():
    a = sample().head(1)
    good = a.copy(); good[q.FIELDS] = good[q.FIELDS]*.1
    bad = a.copy(); bad[q.FIELDS] = bad[q.FIELDS]*.13
    assert q.factors_against_sip(a, good, .1).corroborated.all()
    assert not q.factors_against_sip(a, bad, .1).corroborated.any()


def test_normalization_preserves_value_and_does_not_clip_shock():
    a = sample().head(3); a.loc[1, ['open', 'high', 'low', 'close', 'adj_close']] *= .1
    b = q.normalize_rows(a, np.array([.5, .5, .5]))
    np.testing.assert_allclose(a.close*a.volume, b.close*b.volume)
    np.testing.assert_allclose(a.close.pct_change().iloc[1:], b.close.pct_change().iloc[1:])
    with pytest.raises(ValueError): q.normalize_rows(a, [1, 0, 1])
