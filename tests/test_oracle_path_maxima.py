from datetime import date
import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from service.market.oracle_atr_study import PEAK_FIELD, attach_price_peaks
from service.market.oracle_path_maxima import price_peak, load_price_peaks
from service.market.oracle_atr_peak_backfill import persist_peaks
from modelFactory.oracle.security_continuity import SecurityDiscontinuity


@pytest.fixture
def path():
    sessions = pd.bdate_range('2025-01-02', periods=23)
    bars = pd.DataFrame({'date': sessions[:21], 'symbol': 'A', 'open': 20.,
        'high': 21., 'low': 14., 'close': 20., 'adj_close': 20., 'volume': 100,
        'is_filled': 0, 'instrument_id': 1, 'data_source': 'eodhd',
        'data_adjustment': 'raw'})
    bars.loc[0, 'high'] = 100.  # J excluded, not a future peak.
    bars.loc[9, 'high'] = 32.
    bars.loc[20, ['open', 'close', 'adj_close']] = 15.
    return bars, sessions


def evaluate(path, **overrides):
    bars, sessions = path
    options = dict(symbol='A', trade_date=sessions[0], sessions=sessions,
                   horizon=20, as_of=date(2026, 1, 1), future_return=-.25, registry={})
    options.update(overrides)
    return price_peak(bars, **options)


def test_peak_32_even_when_terminal_is_15_and_j_high_is_100(path):
    result = evaluate(path)
    assert result['max_price'] == 32
    assert result['max_date'] == str(path[1][9].date())
    assert result['anchor_close'] == 20
    assert result['observed_sessions'] == 20 and result['reason'] is None


def test_split_prices_are_expressed_in_signal_day_units(path):
    bars, sessions = path
    # 2:1 split after J: the actually quoted peak is 16, comparable to 32 at J.
    bars.loc[1:, ['open', 'high', 'low', 'close', 'adj_close']] /= 2
    bars.loc[0, 'adj_close'] = 10
    assert evaluate((bars, sessions))['max_price'] == 32


def test_newer_prices_and_later_peak_do_not_extend_horizon(path):
    bars, sessions = path
    later = bars.iloc[-1:].copy()
    later['date'] = sessions[21]
    later['high'] = 1000.
    assert evaluate((pd.concat([bars, later]), sessions))['max_price'] == 32


def test_missing_session_never_shifted_or_replaced(path):
    bars, sessions = path
    result = evaluate((bars.drop(index=5), sessions))
    assert result['max_price'] is None
    assert result['observed_sessions'] == 19
    assert result['reason'] == 'MISSING_FILLED_OR_INVALID_BAR'


@pytest.mark.parametrize('column,value', [('is_filled', 1), ('volume', 0),
    ('high', float('inf')), ('low', 0), ('high', 10), ('adj_close', -1)])
def test_invalid_path_bar_reserved(path, column, value):
    bars, sessions = path
    bars.loc[4, column] = value
    assert evaluate((bars, sessions))['reason'] == 'MISSING_FILLED_OR_INVALID_BAR'


@pytest.mark.parametrize('column,value,reason', [
    ('instrument_id', 2, 'IDENTITY_CHANGE_OR_UNKNOWN'),
    ('data_source', 'alpaca', 'SOURCE_CHANGE_OR_UNKNOWN'),
    ('data_adjustment', 'UNKNOWN', 'ADJUSTMENT_CHANGE_OR_UNKNOWN')])
def test_lineage_changes_reserved(path, column, value, reason):
    bars, sessions = path
    bars.loc[4, column] = value
    assert evaluate((bars, sessions))['reason'] == reason


def test_known_identity_break_reserved(path):
    sessions = path[1]
    registry = {'A': (SecurityDiscontinuity('A', sessions[4], sessions[5], 'renamed'),)}
    assert evaluate(path, registry=registry)['reason'] == 'KNOWN_IDENTITY_BREAK'


def test_immature_path_remains_unavailable_even_if_future_bars_exist(path):
    assert evaluate(path, as_of=path[1][20].date())['reason'] == 'NOT_YET_AVAILABLE'
    assert evaluate(path, as_of=path[1][21].date())['max_price'] == 32


@pytest.mark.parametrize('value', [0., None, 'invalid', float('inf')])
def test_peak_requires_terminal_consistency_with_archived_label(path, value):
    assert evaluate(path, future_return=value)['reason'] == 'ARCHIVED_RETURN_VS_CURRENT_BARS_MISMATCH'


def test_duplicate_symbol_bars_rejected(path):
    bars, sessions = path
    with pytest.raises(ValueError, match='Doublons'):
        evaluate((pd.concat([bars, bars.iloc[:1]]), sessions))


def summary_row():
    return {'evaluated_count': 3, 'quality_details': None, 'status': 'COMPLETE',
        'movement_quality': json.dumps({'lists': {'predicted_oracle_score_order_returns_pct': {
            'selection_symbols': ['A', 'B', 'C'], 'value_symbols': ['A', 'B', 'C']}}})}


def test_peaks_keep_oracle_order_not_peak_order_and_preserve_decimals():
    maxima = {'A': {'max_price': 32.1234567}, 'B': {'max_price': 120.}, 'C': {'max_price': 8.}}
    row = attach_price_peaks(summary_row(), maxima, horizon=20, policy='partial')
    assert json.loads(row[PEAK_FIELD]) == [32.123457, 120., 8.]
    info = json.loads(row['movement_quality'])['lists'][PEAK_FIELD]
    assert info['value_symbols'] == ['A', 'B', 'C']
    assert info['status'] == 'COMPLETE' and info['unit'] == 'USD_SIGNAL_DAY_PRICE_SCALE'
    assert info['research_only_future_information'] is True


def test_partial_missing_peak_omitted_without_replacement_or_reordering():
    maxima = {'B': {'max_price': 120.}, 'C': {'max_price': 8.}, 'D': {'max_price': 1000.}}
    row = attach_price_peaks(summary_row(), maxima, horizon=20, policy='partial')
    assert json.loads(row[PEAK_FIELD]) == [120., 8.]
    info = json.loads(row['movement_quality'])['lists'][PEAK_FIELD]
    assert info['original_selection_positions'] == [2, 3]
    assert info['missing_symbols'] == ['A'] and row['status'] == 'PARTIAL'
    strict = attach_price_peaks(summary_row(), maxima, horizon=20, policy='strict')
    assert strict[PEAK_FIELD] is None and strict['status'] == 'INCOMPLETE'


def test_repaired_peak_removes_only_its_previous_quality_issue():
    row = summary_row()
    row['quality_details'] = 'INCOMPLETE_PREDICTED_MAX_PRICES'
    row['status'] = 'PARTIAL'
    fixed = attach_price_peaks(row, {s: {'max_price': 32.} for s in ['A', 'B', 'C']},
                               horizon=20, policy='partial')
    assert fixed['quality_details'] is None and fixed['status'] == 'COMPLETE'
    row = summary_row()
    row['quality_details'] = 'MISSING_MACRO,INCOMPLETE_PREDICTED_MAX_PRICES'
    fixed = attach_price_peaks(row, {s: {'max_price': 32.} for s in ['A', 'B', 'C']},
                               horizon=20, policy='partial')
    assert fixed['quality_details'] == 'MISSING_MACRO' and fixed['status'] == 'PARTIAL'


def test_unqualified_return_never_reintroduced_as_known_price():
    row = summary_row()
    meta = json.loads(row['movement_quality'])
    meta['lists']['predicted_oracle_score_order_returns_pct']['value_symbols'] = ['B', 'C']
    row['movement_quality'] = json.dumps(meta)
    row = attach_price_peaks(row, {s: {'max_price': 32.} for s in ['A', 'B', 'C']}, horizon=20, policy='partial')
    assert json.loads(row[PEAK_FIELD]) == [32., 32.]
    assert json.loads(row['movement_quality'])['lists'][PEAK_FIELD]['value_symbols'] == ['B', 'C']


def test_loader_bulk_read_is_bounded_to_selected_symbols_and_exit_date(path):
    bars, sessions = path
    labels = pd.DataFrame({'prediction_date': [sessions[0]], 'symbol': ['A'],
        'target_quality_valid': [1], 'future_return': [-.25], 'oracle_available_date': [sessions[21]]})
    with patch('service.market.oracle_path_maxima.nyse_sessions', return_value=sessions), \
         patch('service.market.oracle_path_maxima.load_security_discontinuities', return_value={}), \
         patch('service.market.oracle_path_maxima.pd.read_sql', return_value=bars) as read:
        result = load_price_peaks(MagicMock(), {str(sessions[0].date()): ['A']}, labels,
            horizon=20, as_of=date(2026, 1, 1))
    assert result[str(sessions[0].date())]['A']['max_price'] == 32
    assert read.call_args.kwargs['params']['symbols'] == ['A']
    assert read.call_args.kwargs['params']['end'] == sessions[20].date()


def test_peak_migration_is_idempotent_and_rejects_other_markets():
    path = Path(__file__).parents[1]/'alembic/versions/0102_oracle_atr_max_prices.py'
    spec = importlib.util.spec_from_file_location('peak_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with patch.object(migration, 'context') as context, patch.object(migration, 'op') as op, \
         patch.object(migration, 'inspect') as inspector:
        context.is_offline_mode.return_value = False
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade'
        inspector.return_value.get_columns.return_value = []
        migration.upgrade()
        assert op.execute.call_count == 1 and PEAK_FIELD in op.execute.call_args.args[0]
        op.execute.reset_mock()
        inspector.return_value.get_columns.return_value = [{'name': PEAK_FIELD}]
        migration.upgrade()
        op.execute.assert_not_called()
        for database in ['alpha_trade_fr', 'alpha_trade_cn']:
            op.get_bind.return_value.execute.return_value.scalar.return_value = database
            with pytest.raises(RuntimeError, match='alpha_trade'):
                migration.upgrade()
            with pytest.raises(RuntimeError, match='alpha_trade'):
                migration.downgrade()
        op.execute.assert_not_called()


def test_targeted_backfill_updates_only_new_list_and_quality_not_old_returns():
    engine = MagicMock()
    row = {**summary_row(), 'trade_date': date(2025, 1, 2), 'universe_hash': 'hash',
           'oracle_batch_id': 'batch', 'oracle_horizon': 20,
           'predicted_oracle_score_order_returns_pct': '[1,2,3]', 'd10_pct': 20}
    row = attach_price_peaks(row, {s: {'max_price': 32.} for s in ['A', 'B', 'C']},
                             horizon=20, policy='partial')
    persist_peaks(engine, [row])
    call = engine.begin.return_value.__enter__.return_value.execute.call_args
    sql = str(call.args[0])
    assert sql.startswith('UPDATE oracle_atr_market_regime_daily SET ')
    assert 'predicted_oracle_score_order_returns_pct' not in sql and 'd10_pct' not in sql
    assert 'INSERT' not in sql and 'stock_bars_daily' not in sql
    assert json.loads(call.args[1][0][PEAK_FIELD]) == [32., 32., 32.]
    assert {'trade_date', 'universe_hash', 'oracle_batch_id', 'oracle_horizon'} <= set(call.args[1][0])
