from datetime import date
import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from service.market.oracle_atr_study import PEAK_FIELD, PEAK_PCT_FIELD, attach_price_peaks, attach_peak_returns
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
    assert result['min_price'] == 14
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


def test_peaks_keep_oracle_order_integer_list_and_precise_metadata():
    maxima = {'A': {'max_price': 32.1234567, 'min_price':14., 'anchor_close': 20.},
              'B': {'max_price': 120., 'min_price':14., 'anchor_close': 20.},
              'C': {'max_price': 8., 'min_price':4., 'anchor_close': 20.}}
    row = attach_price_peaks(summary_row(), maxima, horizon=20, policy='partial')
    assert json.loads(row[PEAK_FIELD]) == [32, 120, 8]
    info = json.loads(row['movement_quality'])['lists'][PEAK_FIELD]
    assert info['value_symbols'] == ['A', 'B', 'C']
    assert info['status'] == 'COMPLETE' and info['unit'] == 'USD_SIGNAL_DAY_PRICE_SCALE'
    assert info['research_only_future_information'] is True
    assert info['value_details']['A']['max_price'] == 32.1234567
    assert info['rounding_decimals'] == 0
    assert all(isinstance(value, int) for value in json.loads(row[PEAK_FIELD]))


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
    fixed = attach_price_peaks(row, {s: {'max_price': 32., 'min_price':14., 'anchor_close': 20.} for s in ['A', 'B', 'C']},
                               horizon=20, policy='partial')
    assert fixed['quality_details'] is None and fixed['status'] == 'COMPLETE'
    row = summary_row()
    row['quality_details'] = 'MISSING_MACRO,INCOMPLETE_PREDICTED_MAX_PRICES'
    fixed = attach_price_peaks(row, {s: {'max_price': 32., 'min_price':14., 'anchor_close': 20.} for s in ['A', 'B', 'C']},
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


def test_peak_integer_rounding_half_up_and_sub_dollar_precision():
    row = attach_price_peaks(summary_row(), {'A': {'max_price': 6.93},
        'B': {'max_price': 32.5}, 'C': {'max_price': .42}}, horizon=20, policy='partial')
    assert json.loads(row[PEAK_FIELD]) == [7, 33, 0]
    assert json.loads(row['movement_quality'])['lists'][PEAK_FIELD]['value_details']['C']['max_price'] == .42


def test_dominant_returns_use_precise_baseline_not_integer_price_and_keep_oracle_order():
    row = summary_row()
    row['predicted_oracle_score_order_returns_pct'] = '[-26,6,-36]'
    row = attach_price_peaks(row, {'A': {'max_price': 6.93, 'min_price':3.935, 'anchor_close': 5.67},
        'B': {'max_price': 120., 'min_price':14., 'anchor_close': 20.},
        'C': {'max_price': 17., 'min_price':14., 'anchor_close': 20.}},
        horizon=20, policy='partial')
    assert json.loads(row[PEAK_FIELD]) == [7,120,17]
    assert json.loads(row[PEAK_PCT_FIELD]) == [-31,500,-30]  # No rerank by future returns.
    assert row['predicted_oracle_score_order_returns_pct'] == '[-26,6,-36]'
    info = json.loads(row['movement_quality'])['lists'][PEAK_PCT_FIELD]
    assert info['unit'] == 'PERCENT' and info['value_symbols'] == ['A','B','C']
    assert info['value_details']['A']['up_return_pct'] == pytest.approx(22.2222222222)
    assert info['value_details']['A']['max_return_pct'] == pytest.approx(-30.5996472663)
    assert info['value_details']['A']['dominant_side'] == 'DOWN'
    assert info['research_only_future_information']


@pytest.mark.parametrize('anchor', [None, 0, -1, 'Infinity', 'invalid', True])
def test_peak_returns_missing_anchor_omitted_without_replacement(anchor):
    maxima = {'A': {'max_price': 22., 'min_price':18., 'anchor_close': 20.},
        'B': {'max_price': 300., 'min_price':14., 'anchor_close': anchor},
        'C': {'max_price': 20.5, 'min_price':20., 'anchor_close': 20.},
        'D': {'max_price': 600., 'min_price':14., 'anchor_close': 20.}}
    row = attach_price_peaks(summary_row(), maxima, horizon=20, policy='partial')
    assert json.loads(row[PEAK_PCT_FIELD]) == [10,3]
    info = json.loads(row['movement_quality'])['lists'][PEAK_PCT_FIELD]
    assert info['value_symbols'] == ['A','C'] and info['original_selection_positions'] == [1,3]
    assert info['missing_reasons'] == {'B':'ANCHOR_CLOSE_MISSING_OR_INVALID'}
    assert row['status'] == 'PARTIAL' and 'INCOMPLETE_PREDICTED_MAX_RETURNS' in row['quality_details']
    strict = attach_price_peaks(summary_row(), maxima, horizon=20, policy='strict')
    assert strict[PEAK_PCT_FIELD] is None and strict['status'] == 'INCOMPLETE'


def test_no_qualified_path_remains_null_not_zero_and_missing_issue_can_be_repaired():
    row = attach_price_peaks(summary_row(), {}, horizon=20, policy='partial')
    assert row[PEAK_PCT_FIELD] is None
    assert json.loads(row['movement_quality'])['lists'][PEAK_PCT_FIELD]['status'] == 'UNAVAILABLE'
    row = attach_price_peaks(row, {s:{'max_price':32.,'min_price':14.,'anchor_close':20.} for s in ['A','B','C']},
                             horizon=20, policy='partial')
    assert json.loads(row[PEAK_PCT_FIELD]) == [60,60,60]
    assert row['status'] == 'COMPLETE' and row['quality_details'] is None
    first = dict(row)
    assert attach_peak_returns(row) == first  # Idempotent with same policy.


def test_peak_returns_preserve_split_adjusted_signal_day_basis(path):
    bars, sessions = path
    bars.loc[1:, ['open','high','low','close','adj_close']] /= 2
    bars.loc[0,'adj_close'] = 10.
    maxima = {s: evaluate((bars,sessions)) for s in ['A','B','C']}
    row = attach_price_peaks(summary_row(), maxima, horizon=20, policy='partial')
    assert json.loads(row[PEAK_PCT_FIELD]) == [60,60,60]


def test_dominant_selection_precedes_rounding_and_exact_tie_is_positive():
    row = attach_price_peaks(summary_row(), {
        'A': {'max_price':122.49,'min_price':77.50,'anchor_close':100.},
        'B': {'max_price':122.5,'min_price':77.5,'anchor_close':100.},
        'C': {'max_price':101.,'min_price':80.,'anchor_close':100.}}, horizon=20,policy='partial')
    assert json.loads(row[PEAK_PCT_FIELD]) == [-23,23,-20]
    info = json.loads(row['movement_quality'])['lists'][PEAK_PCT_FIELD]
    assert info['value_details']['A']['dominant_side'] == 'DOWN'
    assert info['value_details']['B']['dominant_side'] == 'UP'


@pytest.mark.parametrize('invalid', ['missing_low','invalid_low','changed_peak','changed_anchor','reserved_path'])
def test_dominant_backfill_never_pairs_unqualified_lows_or_changes_archived_high(invalid):
    maxima = {s:{'max_price':32.,'min_price':14.,'anchor_close':20.} for s in ['A','B','C']}
    row = attach_price_peaks(summary_row(), maxima,horizon=20,policy='partial')
    old_prices, old_details = row[PEAK_FIELD], json.loads(row['movement_quality'])['lists'][PEAK_FIELD]
    fresh = {s:dict(value) for s,value in maxima.items()}
    if invalid == 'missing_low':
        del fresh['A']['min_price']
    elif invalid == 'invalid_low':
        fresh['A']['min_price'] = 33.
    elif invalid == 'changed_peak':
        fresh['A']['max_price'] = 33.
    elif invalid == 'changed_anchor':
        fresh['A']['anchor_close'] = 21.
    else:
        fresh['A']['reason'] = 'MISSING_FILLED_OR_INVALID_BAR'
    row = attach_peak_returns(row,policy='partial',maxima=fresh)
    assert json.loads(row[PEAK_PCT_FIELD]) == [60,60]
    meta = json.loads(row['movement_quality'])['lists']
    assert meta[PEAK_PCT_FIELD]['value_symbols'] == ['B','C']
    assert meta[PEAK_PCT_FIELD]['missing_symbols'] == ['A']
    assert row[PEAK_FIELD] == old_prices and meta[PEAK_FIELD] == old_details


def test_peak_returns_migration_idempotent_and_us_only():
    path = Path(__file__).parents[1]/'alembic/versions/0103_oracle_atr_max_returns.py'
    spec = importlib.util.spec_from_file_location('peak_return_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with patch.object(migration, 'context') as context, patch.object(migration, 'op') as op, \
         patch.object(migration, 'inspect') as inspector:
        context.is_offline_mode.return_value = False
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade'
        inspector.return_value.get_columns.return_value = []
        migration.upgrade()
        assert op.execute.call_count == 1 and PEAK_PCT_FIELD in op.execute.call_args.args[0]
        op.execute.reset_mock()
        inspector.return_value.get_columns.return_value = [{'name': PEAK_PCT_FIELD}]
        migration.upgrade()
        op.execute.assert_not_called()
        for database in ['alpha_trade_fr', 'alpha_trade_cn']:
            op.get_bind.return_value.execute.return_value.scalar.return_value = database
            with pytest.raises(RuntimeError, match='alpha_trade'):
                migration.upgrade()
            with pytest.raises(RuntimeError, match='alpha_trade'):
                migration.downgrade()


def test_peak_returns_backfill_backup_scoping_concurrency_and_idempotence(tmp_path):
    from service.market.oracle_atr_peak_returns_backfill import run
    maxima = {s: {'max_price':6.93,'min_price':3.935,'anchor_close':5.67} for s in ['A','B','C']}
    row = attach_price_peaks(summary_row(), maxima,
                             horizon=20, policy='partial')
    expected = dict(row)
    meta = json.loads(row['movement_quality'])
    del meta['lists'][PEAK_PCT_FIELD]
    row['movement_quality'] = json.dumps(meta)
    del row[PEAK_PCT_FIELD]
    row.update(trade_date=date(2025,1,2),universe_hash='hash',oracle_batch_id='batch',oracle_horizon=20,
               missing_returns_policy='partial')
    engine = MagicMock()
    conn = engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.scalar.return_value = 'alpha_trade'
    conn.execute.return_value.fetchone.return_value = ('table','CREATE TABLE ...')
    write = engine.begin.return_value.__enter__.return_value
    write.execute.return_value.rowcount = 1
    with patch('service.market.oracle_atr_peak_returns_backfill.inspect') as inspector, \
         patch('service.market.oracle_atr_peak_returns_backfill._load_current_paths', return_value={'2025-01-02':maxima}), \
         patch('service.market.oracle_atr_peak_returns_backfill.pd.read_sql', return_value=pd.DataFrame([row])) as read:
        inspector.return_value.get_columns.return_value = [{'name':PEAK_FIELD}]
        report = run(output_dir=tmp_path/'apply', engine=engine, apply=True)
        assert report['changed_rows'] == 1 and report['nonnull_rows'] == 1
        assert (tmp_path/'apply'/'study_before.parquet').exists()
        sql = str(write.execute.call_args.args[0])
        assert 'UPDATE alpha_trade.oracle_atr_market_regime_daily SET ' in sql
        assert PEAK_PCT_FIELD in sql and 'SHA2(CAST(' in sql
        assert 'predicted_oracle_score_order_returns_pct' not in sql and 'stock_bars_daily' not in sql
        assert json.loads(write.execute.call_args.args[1][PEAK_PCT_FIELD]) == [-31,-31,-31]
        written_meta = json.loads(write.execute.call_args.args[1]['movement_quality'])
        assert written_meta['lists'][PEAK_FIELD] == json.loads(row['movement_quality'])['lists'][PEAK_FIELD]
        write.execute.return_value.rowcount = 0
        with pytest.raises(RuntimeError, match='simultanément'):
            run(output_dir=tmp_path/'concurrent', engine=engine, apply=True)
        # Subsequent run has nothing to rewrite and never repeats DDL.
        read.return_value = pd.DataFrame([{**row, **expected}])
        inspector.return_value.get_columns.return_value = [{'name':PEAK_FIELD},{'name':PEAK_PCT_FIELD}]
        write.execute.reset_mock()
        assert run(output_dir=tmp_path/'again', engine=engine, apply=True)['changed_rows'] == 0
        write.execute.assert_not_called()
        conn.execute.return_value.scalar.return_value = 'alpha_trade_cn'
        with pytest.raises(ValueError, match='Base US'):
            run(output_dir=tmp_path/'wrong-market', engine=engine, apply=True)


def test_dominant_backfill_counts_unchanged_across_all_tranches(tmp_path):
    from service.market.oracle_atr_peak_returns_backfill import run
    maxima={s:{'max_price':32.,'min_price':14.,'anchor_close':20.} for s in ['A','B','C']}
    first=attach_price_peaks(summary_row(),maxima,horizon=20,policy='partial')
    first.update(trade_date=date(2025,1,2),universe_hash='hash',oracle_batch_id='batch',oracle_horizon=20,
                 missing_returns_policy='partial')
    second=dict(first,trade_date=date(2025,1,3))
    # Only first date needs enrichment; the final tranche is unchanged.
    meta=json.loads(first['movement_quality'])
    del meta['lists'][PEAK_PCT_FIELD]
    first['movement_quality']=json.dumps(meta)
    first[PEAK_PCT_FIELD]=None
    engine=MagicMock()
    conn=engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.scalar.return_value='alpha_trade'
    conn.execute.return_value.fetchone.return_value=('table','CREATE TABLE ...')
    with patch('service.market.oracle_atr_peak_returns_backfill.inspect') as inspector, \
         patch('service.market.oracle_atr_peak_returns_backfill._load_current_paths',
               return_value={'2025-01-02':maxima,'2025-01-03':maxima}), \
         patch('service.market.oracle_atr_peak_returns_backfill.pd.read_sql',return_value=pd.DataFrame([first,second])):
        inspector.return_value.get_columns.return_value=[{'name':PEAK_FIELD},{'name':PEAK_PCT_FIELD}]
        report=run(output_dir=tmp_path/'counts',engine=engine,date_batch_size=1)
    assert report['examined_rows']==2 and report['changed_rows']==1 and report['unchanged_rows']==1


def test_existing_rounding_preserves_units_order_and_full_precision():
    from service.market.oracle_atr_peak_rounding import round_record
    row = attach_price_peaks(summary_row(), {'A': {'max_price': 6.93, 'anchor_close': 5.67},
        'B': {'max_price': 32.4999996}, 'C': {'max_price': 8.}}, horizon=20, policy='partial')
    # Old six-decimal rendering; use precise metadata, avoid double-rounding B.
    row[PEAK_FIELD] = '[6.93,32.500000,8.0]'
    result = round_record(row)
    assert json.loads(result[PEAK_FIELD]) == [7, 32, 8]
    info = json.loads(result['movement_quality'])['lists'][PEAK_FIELD]
    assert info['value_symbols'] == ['A', 'B', 'C']
    assert info['value_details']['A']['max_price'] == 6.93
    assert info['value_details']['A']['anchor_close'] == 5.67
    assert info['unit'] == 'USD_SIGNAL_DAY_PRICE_SCALE'
    assert round_record(result) == result


@pytest.mark.parametrize('invalid', ['alignment', 'unit', 'precision', 'nonfinite'])
def test_existing_rounding_refuses_invalid_metadata(invalid):
    from service.market.oracle_atr_peak_rounding import round_record
    row = attach_price_peaks(summary_row(), {s: {'max_price': 6.93} for s in ['A', 'B', 'C']},
                             horizon=20, policy='partial')
    meta = json.loads(row['movement_quality'])
    info = meta['lists'][PEAK_FIELD]
    if invalid == 'alignment':
        info['value_symbols'] = ['A']
    elif invalid == 'unit':
        info['unit'] = 'PERCENT'
    elif invalid == 'precision':
        del info['value_details']['A']['max_price']
    else:
        info['value_details']['A']['max_price'] = float('inf')
    row['movement_quality'] = json.dumps(meta)
    with pytest.raises(ValueError):
        round_record(row)


def test_existing_rounding_update_is_backed_up_scoped_and_concurrency_guarded(tmp_path):
    from service.market.oracle_atr_peak_rounding import run
    row = attach_price_peaks(summary_row(), {s: {'max_price': 6.93} for s in ['A', 'B', 'C']},
                             horizon=20, policy='partial')
    meta = json.loads(row['movement_quality'])
    meta['lists'][PEAK_FIELD]['rounding_decimals'] = 6
    row['movement_quality'] = json.dumps(meta)
    row[PEAK_FIELD] = '[6.93,6.93,6.93]'
    row.update(trade_date=date(2025, 1, 2), universe_hash='hash', oracle_batch_id='batch', oracle_horizon=20)
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = 'alpha_trade'
    write = engine.begin.return_value.__enter__.return_value

    def guarded_update(statement, parameters):
        assert (tmp_path/'apply'/'before.parquet').exists()
        assert (tmp_path/'apply'/'protocol.json').exists()
        sql = str(statement)
        assert 'SET predicted_oracle_score_order_max_prices=' in sql
        assert 'SHA2(CAST(' in sql and 'oracle_horizon=:oracle_horizon' in sql
        assert 'stock_bars_daily' not in sql and 'predicted_oracle_score_order_returns_pct' not in sql
        assert len(parameters['old_value_hash']) == 64
        return MagicMock(rowcount=1)

    write.execute.side_effect = guarded_update
    with patch('service.market.oracle_atr_peak_rounding.pd.read_sql', return_value=pd.DataFrame([row])):
        assert run(output_dir=tmp_path/'apply', engine=engine, apply=True)['changed_rows'] == 1
        write.execute.side_effect = None
        write.execute.return_value.rowcount = 0
        with pytest.raises(RuntimeError, match='simultanément'):
            run(output_dir=tmp_path/'concurrent', engine=engine, apply=True)
        assert json.loads((tmp_path/'concurrent'/'progress.json').read_text())['status'] == 'FAILED'
        engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value = 'alpha_trade_fr'
        write.execute.reset_mock()
        with pytest.raises(ValueError, match='Base US'):
            run(output_dir=tmp_path/'wrong-market', engine=engine, apply=True)
        write.execute.assert_not_called()
