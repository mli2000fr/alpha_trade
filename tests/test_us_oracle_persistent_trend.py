import numpy as np
import pandas as pd
import pytest

from scripts.research.us_oracle_persistent_trend import trend_features, qualify_candidates


def daily(direction=1, n=160):
    days = pd.bdate_range('2025-01-01', periods=n)
    close = 100*np.exp(direction*np.arange(n)*.003)
    return pd.DataFrame(dict(open=close, close=close, high=close*1.01, low=close*.99,
                             volume=10000., is_filled=0), index=days)


@pytest.mark.parametrize('direction,accepted,rejected', [(1, 'long_pass', 'short_pass'), (-1, 'short_pass', 'long_pass')])
def test_mirrored_trends_and_warmup(direction, accepted, rejected):
    f = trend_features(daily(direction))
    assert not f.qualified.iloc[:59].any()
    assert f[accepted].iloc[59:].all()
    assert not f[rejected].any()


def test_adx_does_not_invent_direction_or_strength_for_flat_prices():
    f = trend_features(daily(0))
    assert f.qualified.iloc[-1]
    assert not f.long_pass.any() and not f.short_pass.any()


@pytest.mark.parametrize('kind', ['missing', 'filled', 'invalid_ohlc', 'infinite'])
def test_gap_restarts_warmup_never_forward_filled(kind):
    g = daily()
    if kind == 'missing':
        g.loc[g.index[80], 'close'] = np.nan
    elif kind == 'filled':
        g.loc[g.index[80], 'is_filled'] = 1
    elif kind == 'infinite':
        g.loc[g.index[80], 'high'] = np.inf
    else:
        g.loc[g.index[80], 'low'] = g.high.iloc[80]+10
    f = trend_features(g)
    assert not f.qualified.iloc[80:140].any()
    assert f.long_pass.iloc[140]


def test_future_changes_cannot_change_past_trend():
    g = daily(); before = trend_features(g)
    g.iloc[110:, g.columns.get_loc('close')] = 1.
    after = trend_features(g)
    pd.testing.assert_frame_equal(before.iloc[:110], after.iloc[:110])


def test_gate_uses_prior_session_not_current_daily_close():
    g = daily(); sessions = g.index
    day = sessions[100]
    candidates = pd.DataFrame([dict(pair_id=1, symbol='TEST', side='buy', year=2025,
        oracle_date=sessions[95], decision_time=day.tz_localize('America/New_York')+pd.Timedelta(hours=10))])
    source = g.rename_axis('date').reset_index().assign(symbol='TEST')
    before = qualify_candidates(candidates, source, sessions)
    assert before.accepted.iloc[0] and before.source_date.iloc[0] == sessions[99]
    source.loc[source.date.ge(day), ['open', 'high', 'low', 'close']] = 1.
    pd.testing.assert_frame_equal(before, qualify_candidates(candidates, source, sessions))


def test_missing_prior_session_blocks_instead_of_stale_asof():
    g = daily(); sessions = g.index; day = sessions[100]
    candidates = pd.DataFrame([dict(pair_id=1, symbol='TEST', side='buy', year=2025,
        oracle_date=sessions[95], decision_time=day.tz_localize('America/New_York')+pd.Timedelta(hours=10))])
    source = g.rename_axis('date').reset_index().assign(symbol='TEST')
    source = source[source.date.ne(sessions[99])]
    result = qualify_candidates(candidates, source, sessions)
    assert not result.accepted.iloc[0]
    assert result.reason.iloc[0] == 'MISSING_OR_INSUFFICIENT_DAILY'


def test_duplicate_daily_identity_rejected():
    source = daily().rename_axis('date').reset_index().assign(symbol='TEST')
    c = pd.DataFrame([dict(symbol='TEST')])
    with pytest.raises(ValueError, match='Ambiguous'):
        qualify_candidates(c, pd.concat([source, source.iloc[:1]]), daily().index)
