from datetime import date, timedelta
import math

import pytest

from modelFactory.fr_feature_panel import compute_symbol_features
from modelFactory.fr_oracle_h5_pilot import feature_matrix
from service.fr.feature_parity_16g import manual_features, parity


@pytest.fixture
def window():
    sessions = [date(2026, 8, 1) + timedelta(days=i) for i in range(21)]
    rows = [{'source_session_date': day, 'open': 100 + i * .7,
             'close': 100.2 + i * .71, 'high': 101 + i * .75,
             'low': 99 + i * .7, 'volume': 1000 + i * 53} for i, day in enumerate(sessions)]
    return rows, sessions


def test_separate_arithmetic_matches_shared_formula_and_transform(window):
    result = parity(*window)
    assert result['raw_mismatches'] == [] and result['transformed_mismatches'] == []
    assert result['training_transformed']['traded_value_mean20_eur'] == pytest.approx(
        math.log1p(result['manual_raw']['traded_value_mean20_eur']))


def test_wrong_atr_detected(window):
    def wrong_compute(*args):
        frame = compute_symbol_features(*args)
        frame['atr20_pct'] *= 2
        return frame
    result = parity(*window, compute=wrong_compute)
    assert result['raw_mismatches'] == ['atr20_pct']


def test_double_log_detected(window):
    def double_log(frame):
        result = feature_matrix(frame)
        result['traded_value_mean20_eur'] = result['traded_value_mean20_eur'].map(math.log1p)
        return result
    result = parity(*window, transform=double_log)
    assert result['transformed_mismatches'] == ['traded_value_mean20_eur']


@pytest.mark.parametrize('mutation', ['short', 'duplicate', 'unordered', 'zero', 'nan', 'bool', 'ohlc'])
def test_invalid_arithmetic_window_rejected(window, mutation):
    rows, _ = window
    if mutation == 'short': rows.pop()
    if mutation == 'duplicate': rows[-1]['source_session_date'] = rows[0]['source_session_date']
    if mutation == 'unordered': rows.reverse()
    if mutation == 'zero': rows[0]['volume'] = 0
    if mutation == 'nan': rows[0]['close'] = float('nan')
    if mutation == 'bool': rows[0]['volume'] = True
    if mutation == 'ohlc': rows[0]['high'] = 50
    with pytest.raises(ValueError):
        manual_features(rows)


def test_wrong_session_window_rejected(window):
    rows, sessions = window
    with pytest.raises(ValueError, match='XPAR sessions'):
        parity(rows, sessions[1:] + [sessions[-1] + timedelta(days=1)])


def test_transform_column_order_checked(window):
    with pytest.raises(ValueError, match='order'):
        parity(*window, transform=lambda frame: feature_matrix(frame).iloc[:, ::-1])


def test_first_bar_required_for_twenty_returns_and_true_ranges(window):
    rows, sessions = window
    original = parity(rows, sessions)['manual_raw']
    rows[0].update(open=90., high=91., low=89., close=90.)
    changed = parity(rows, sessions)['manual_raw']
    assert changed['return_20'] != original['return_20']
    assert changed['atr20_pct'] != original['atr20_pct']
    assert changed['realized_vol20'] != original['realized_vol20']
    assert changed['traded_value_mean20_eur'] == original['traded_value_mean20_eur']
