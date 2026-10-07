import json

import numpy as np
import pandas as pd
import pytest

from scripts.research.us_concentrated_exit_variants import resolve_long_path


def fixture():
    days = pd.bdate_range('2025-01-02', periods=30)
    data = np.tile([100., 101., 99., 100., 10000., 0., 1.], (30, 1))
    signal = {'execution_date': days[1], 'side': 'buy', 'fill_price': 100.,
        'replay_initial_stop_price': 95., 'replay_take_profit_price': 106.,
        'replay_trailing_stop_pct': .05, 'replay_trailing_activation_price': 100.}
    return signal, days, data


def test_expiry_twenty_after_entry_not_twenty_after_signal():
    signal, days, data = fixture()
    result = resolve_long_path(signal, days, data, 'NO_TP_FIXED_SL_20_AFTER_ENTRY')
    assert result['exit_date'] == days[21]
    assert result['scheduled_exit_date'] == days[21]
    assert result['exit_reason'] == 'expiry_20_sessions_after_entry_close'


def test_stop_gap_filled_at_open_not_stop():
    signal, days, data = fixture()
    data[2, :4] = [80., 90., 75., 85.]
    result = resolve_long_path(signal, days, data, 'NO_TP_FIXED_SL_20_AFTER_ENTRY')
    assert result['exit_price'] == 80.
    assert result['exit_reason'] == 'initial_stop_gap_open'


def test_favourable_tp_gap_precedes_later_intraday_stop_conservative_limit():
    signal, days, data = fixture()
    data[2, :4] = [110., 112., 90., 100.]
    result = resolve_long_path(signal, days, data, 'REFERENCE_20_AFTER_ENTRY')
    assert result['exit_price'] == 106.
    assert result['exit_reason'] == 'take_profit_gap_limit'


def test_no_tp_does_not_stop_at_old_tp():
    signal, days, data = fixture()
    data[2, :4] = [100., 150., 99., 140.]
    data[3:, :4] = [140., 141., 139., 140.]
    result = resolve_long_path(signal, days, data, 'NO_TP_FIXED_SL_20_AFTER_ENTRY')
    assert result['exit_date'] == days[21]
    assert result['exit_price'] == 140.


def test_same_day_stop_does_not_create_posthumous_watcher():
    signal, days, data = fixture()
    data[1, :4] = [100., 110., 90., 105.]
    result = resolve_long_path(signal, days, data, 'REFERENCE_20_AFTER_ENTRY')
    assert result['exit_reason'] == 'initial_stop'
    assert pd.isna(result['watcher_effective_date'])
    assert not any('WATCHER' in e['type'] for e in json.loads(result['events_json'])[:-1])


def test_trailing_uses_previous_peak_not_same_day_high():
    signal, days, data = fixture()
    data[2, :4] = [100., 150., 99., 140.]
    data[3, :4] = [140., 145., 138., 140.]
    result = resolve_long_path(signal, days, data, 'NO_TP_TRAILING_20_AFTER_ENTRY')
    assert result['exit_date'] == days[3]
    assert result['exit_price'] == 140.  # previous peak stop 142.5 gapped through
    assert result['exit_reason'] == 'trailing_stop_gap_open'


def test_missing_bar_is_blocked_not_skipped():
    signal, days, data = fixture()
    data[2, 0] = np.nan
    result = resolve_long_path(signal, days, data, 'NO_TP_FIXED_SL_20_AFTER_ENTRY')
    assert result['status'] == 'BLOCKED_PRICE_PATH'
    assert result['exit_price'] is None


def test_terminal_is_explicit_and_censored():
    signal, days, data = fixture()
    result = resolve_long_path(signal, days[:8], data[:8], 'NO_TP_FIXED_SL_20_AFTER_ENTRY')
    assert result['exit_date'] == days[7]
    assert result['status'] == 'RESOLVED_TERMINAL_HYPOTHESIS'
    assert 'HOLDING_WINDOW_CENSORED' in result['path_flags']
    assert result['economic_comparison'] is False


def test_short_cannot_silently_enter_long_experiment():
    signal, days, data = fixture()
    signal['side'] = 'sell'
    with pytest.raises(ValueError, match='LONG only'):
        resolve_long_path(signal, days, data, 'REFERENCE_20_AFTER_ENTRY')
