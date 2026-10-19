import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_holding_horizons as s
from scripts.research import us_tradable_tp10_variants as old
from tests.test_us_tradable_symbol_reliability import bars


def flat(n=26):
    b = bars(n); b[['open', 'close']] = 100.; b.high = 101.; b.low = 99.
    return b


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
@pytest.mark.parametrize('sl', [.10, None])
def test_h20_every_original_field_exact(side, sl):
    b = bars(90); positions = np.arange(70)
    actual = s.paths(b, positions, side, horizon=20, sl=sl)
    expected = old.paths(b, positions, side, tp=.1, sl=sl)
    for field in expected: np.testing.assert_array_equal(actual[field], expected[field])


@pytest.mark.parametrize('horizon', [5, 10, 20])
@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
def test_entry_j1_and_expiry_close_n(horizon, side):
    b = flat(); b.iloc[0, b.columns.get_loc('open')] = 500.
    b.loc[b.index[horizon], ['open', 'high', 'low', 'close']] = [100., 106., 99., 105.]
    result = s.paths(b, [0], side, horizon=horizon, sl=None)
    assert result['entry_price'][0] == 100.
    assert result['exit_price'][0] == 105.
    assert result['exit_session'][0] == horizon
    assert result['outcome'][0] == 'TIMEOUT'
    assert result['terminal_signed_return'][0] == pytest.approx(.05 if side == 'LONG' else -.05)


@pytest.mark.parametrize('horizon', [5, 10])
def test_future_after_expiry_cannot_change_outcome(horizon):
    a = flat(); expected = s.paths(a, [0], 'LONG', horizon=horizon, sl=None)
    a.loc[a.index[horizon+1]:, ['open', 'high', 'low', 'close']] = [100., 300., 1., 200.]
    actual = s.paths(a, [0], 'LONG', horizon=horizon, sl=None)
    for field in actual: np.testing.assert_array_equal(actual[field], expected[field])


@pytest.mark.parametrize('horizon', [5, 10, 20])
def test_last_day_tp_counts_next_day_does_not(horizon):
    a = flat(); a.loc[a.index[horizon], 'high'] = 110.
    assert s.paths(a, [0], 'LONG', horizon=horizon)['tp_first'][0]
    a.loc[a.index[horizon], 'high'] = 101.; a.loc[a.index[horizon+1], 'high'] = 110.
    assert not s.paths(a, [0], 'LONG', horizon=horizon)['tp_first'][0]


@pytest.mark.parametrize('side', ['LONG', 'SHORT'])
def test_collision_stop_first_and_no_sl_distinct(side):
    a = flat(); a.loc[a.index[1], ['high', 'low']] = [110., 90.]
    stopped = s.paths(a, [0], side, horizon=5)
    free = s.paths(a, [0], side, horizon=5, sl=None)
    assert stopped['sl_first'][0] and stopped['ambiguity'][0]
    assert free['tp_first'][0] and not free['sl_first'][0]


def test_open_resolves_collision_limit_no_improvement():
    a = flat(); a.loc[a.index[2], ['open', 'high', 'low', 'close']] = [115., 120., 80., 90.]
    r = s.paths(a, [0], 'LONG', horizon=5)
    assert r['tp_first'][0] and not r['ambiguity'][0]
    assert r['exit_price'][0] == pytest.approx(110.)


def test_stop_gap_not_capped_and_mae_excludes_after_exit_low():
    a = flat(); a.loc[a.index[2], ['open', 'high', 'low', 'close']] = [75., 76., 50., 60.]
    r = s.paths(a, [0], 'LONG', horizon=5)
    assert r['gap_stop'][0] and r['path_return'][0] == pytest.approx(-.25)
    assert r['mae_through_exit_bar'][0] == pytest.approx(.25)


@pytest.mark.parametrize('horizon', [0, 21, True, 5.0])
def test_invalid_horizon_refused(horizon):
    with pytest.raises(ValueError): s.paths(flat(), [0], 'LONG', horizon=horizon)


def test_incomplete_window_and_fractional_position_refused():
    with pytest.raises(ValueError): s.paths(flat(5), [0], 'LONG', horizon=5)
    with pytest.raises(ValueError): s.paths(flat(), [.5], 'LONG', horizon=5)


def test_membership_unchanged_when_short_horizon_outcome_changes():
    f = pd.DataFrame(dict(date=pd.to_datetime(['2025-01-02']), symbol=['A'], side=['LONG'], net_outcome=[-.5]))
    reference = f[s.KEYS].assign(symbol_pass=True, opposite_pass=False, chosen_side=True, rebalance_date=pd.Timestamp('2025-01-02'))
    a = s.align_memberships(f, reference); b = s.align_memberships(f.assign(net_outcome=.5), reference)
    pd.testing.assert_frame_equal(a[s.FLAGS], b[s.FLAGS])
    with pytest.raises(ValueError): s.align_memberships(f, reference.iloc[:0])


def test_shorter_holding_does_not_change_twenty_session_spacing():
    from scripts.research import us_tradable_symbol_reliability as base
    days = pd.bdate_range('2025-01-01', periods=45)
    f = pd.DataFrame(dict(date=days[:22], entry_date=days[1:23], last_path_date=days[20:42],
        holding_last_date=days[5:27], symbol='A', side='LONG'))
    result = base.independent_fast(f)
    assert result.date.tolist() == [days[0], days[20]]
