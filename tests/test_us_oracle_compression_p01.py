from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts.research import us_oracle_compression_p01 as study


def session(closes, start='2026-01-05 14:30Z'):
    stamps = pd.date_range(start, periods=len(closes), freq='5min')
    return pd.DataFrame(dict(bar_timestamp=stamps, bar_end_timestamp=stamps+pd.Timedelta(minutes=5),
        open=closes, close=closes, high=np.asarray(closes)+.2, low=np.asarray(closes)-.2,
        session_tag='regular'))


def test_bands_warmup_population_std_and_wilder_seed():
    frame = session([100.]*23+[105.,106.,106.])
    f = study.bands(frame)
    assert not f.ready.iloc[:19].any() and f.ready.iloc[19:].all()
    assert f.atr.iloc[19] == pytest.approx(.4)
    assert f.atr.iloc[23] == pytest.approx((.4*19+5.2)/20)
    assert f.bb_upper.iloc[23] == pytest.approx(frame.close.iloc[4:24].mean()+2*frame.close.iloc[4:24].std(ddof=0))
    assert f.inside.iloc[19:23].all() and f.release.iloc[23]


def test_future_changes_do_not_change_indicator_prefix():
    a = session([100.]*23+[105.,106.,106.])
    b = pd.concat([a, session([900.,1.], start='2026-01-05 16:40Z')], ignore_index=True)
    pd.testing.assert_frame_equal(study.bands(a), study.bands(b).iloc[:len(a)])


def test_new_session_does_not_inherit_previous_squeeze_or_warmup():
    assert not study.bands(session([100.]*10, start='2026-01-06 14:30Z')).ready.any()
    assert not study.session_signals(session([100.,105.,106.,106.], start='2026-01-06 14:30Z'), 101).get('P01')


def test_release_precedes_confirmed_breakout_and_fill_next_open():
    frame = session([100.]*23+[105.,106.,106.])
    signals = study.session_signals(frame, 101)
    assert set(signals) == set(study.ARMS)
    r = signals['P01']
    assert r['release_bar'] == r['cross_bar'] == frame.bar_timestamp.iloc[23]
    assert r['signal_bar'] == frame.bar_timestamp.iloc[24]
    assert r['timestamp'] == frame.bar_timestamp.iloc[25]
    assert r['price'] == 106


def test_fill_price_not_used_to_pick_signal():
    a = session([100.]*23+[105.,106.,106.]); b = a.copy()
    b.loc[25, ['open','high','low','close']] = [400.,410.,390.,400.]
    x, y = study.session_signals(a, 101)['P01'], study.session_signals(b, 101)['P01']
    assert x['timestamp'] == y['timestamp'] and x['release_bar'] == y['release_bar']
    assert x['price'] != y['price']  # native gap rule may later reject, never look ahead here


def test_last_bar_confirmation_not_filled_next_session():
    assert study.session_signals(session([100.]*23+[105.,106.]), 101) == {}


def test_early_breakout_only_in_unwarmed_winner_control():
    signals = study.session_signals(session([100.,102.,103.,103.]), 101)
    assert set(signals) == {'WINNER'}


def features(n=20, release=5):
    f = pd.DataFrame(dict(inside=[False]*n, release=[False]*n))
    f.loc[release, 'release'] = True
    return f


@pytest.mark.parametrize('age,allowed', [(0,True),(6,True),(7,False)])
def test_release_expiration_is_in_bars_not_calendar_days(age, allowed):
    assert (study.release_for_cross(features(), 5+age) is not None) == allowed


def test_future_release_cannot_qualify_old_cross():
    assert study.release_for_cross(features(release=10), 9) is None


def test_new_squeeze_invalidates_old_release():
    f = features(); f.loc[7, 'inside'] = True
    assert study.release_for_cross(f, 8) is None


def test_minimum_three_inside_bars_before_release():
    # Only two warmed inside bars before a sudden expansion.
    f = study.bands(session([100.]*21+[105.,106.,106.]))
    assert not f.release.iloc[21]


def test_scalar_stop_gap_and_no_retroactive_peak():
    a = session([100.,110.,105.]); a.loc[0, ['high','low']] = [120.,99.]
    a.loc[1, 'low'] = 100.
    assert study.scalar_exit_cents(a, 0, a.bar_timestamp.iloc[2], {}) == (1,102.,'INTRABAR')
    a.loc[1, ['open','high','low','close']] = [80.,81.,79.,80.]
    assert study.scalar_exit_cents(a, 0, a.bar_timestamp.iloc[2], {}) == (1,80.,'OPEN')


def test_scalar_stop_cent_rounding_and_horizon_open():
    a = session([100.123,100.123]); a.loc[0, 'low'] = 93.
    assert study.scalar_exit_cents(a, 0, a.bar_timestamp.iloc[1], {}) == (0,93.11,'INTRABAR')
    b = session([100.,101.])
    assert study.scalar_exit_cents(b, 0, b.bar_timestamp.iloc[1], {}) == (1,101.,'OPEN')


def test_initial_stop_uses_exact_shared_winner_expression_at_half_cent():
    f=session([151.5,140.]); f.loc[0,'low']=140.
    assert study.scalar_exit_cents(f,0,f.bar_timestamp.iloc[1],{}) == (0,140.89,'INTRABAR')
    fake=SimpleNamespace(state=SimpleNamespace(positions={'A':SimpleNamespace(entry_price=151.5,peak_high=151.5)}))
    assert study.CentLedger.known_stop(fake,'A') == 140.89


def test_missing_scan_session_stops_all_arms_no_late_reselection():
    schedule = study.history.calendar_frame()
    r = SimpleNamespace(oracle_date=pd.Timestamp('2025-01-03'), symbol='A')
    found, why = study.select_entries(r, {}, schedule)
    assert found == {} and why == 'MISSING_ENTRY_SCAN_SESSION'


def test_common_maturity_exclusion_applies_before_early_stop_results():
    schedule = study.history.calendar_frame()
    row = SimpleNamespace(symbol='A')
    found = {'P01':dict(date=pd.Timestamp('2026-09-15'))}
    assert study.common_reservation(row, found, {}, schedule, pd.DataFrame()) == 'COMMON_H20_IMMATURE'


def test_no_signal_is_zero_opportunity_not_dropped_from_checks():
    f = pd.DataFrame(dict(year=[2025,2025], P01_signal=[False,True], symbol=['A','B'],
        oracle_date=pd.to_datetime(['2025-01-02','2025-02-03']), P01=[0.,2.],
        WARMUP_CONTROL=[-4.,1.], P01_cost25=[0.,1.], WARMUP_CONTROL_cost25=[-5.,0.]))
    c = study.opportunity_checks(f)[0]
    assert c['opportunities'] == 2 and c['p01_signals'] == 1
    assert c['mean_opportunity_increment_pp'] == 2.5


def test_fee_auditor_supports_stress_and_separate_cent_exit():
    auditor = study.specialize_cost_auditor()
    assert auditor is not study.risk.base.run_case
    auditor.__globals__['scalar_exit'] = study.scalar_exit_cents
    assert auditor.__globals__['scalar_exit'] is study.scalar_exit_cents


def test_rule_is_frozen_single_setting_not_parameter_grid():
    assert study.RULE == dict(period=20,bb_std=2.,kc_atr=1.5,squeeze_bars=3,
        release_valid_bars=6,confirmation_bars=2,entry_valid_sessions=20)
    assert study.FEES == (8,25)
