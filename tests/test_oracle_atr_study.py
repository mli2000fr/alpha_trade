from datetime import date
import json
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from service.market.oracle_atr_study import CALCULATION_VERSION, MACRO_FIELDS, MOVEMENT_FIELDS, run, summarize_day


def frames():
    scores = pd.DataFrame({'symbol': [str(i) for i in range(10)], 'proba_extreme': range(10)})
    labels = pd.DataFrame({'symbol': ['7','8','9'], 'oracle_decile': [1,10,5],
        'target_quality_valid': [1,1,1], 'future_return': [-.1,.2,.01],
        'oracle_available_date': ['2025-03-01']*3})
    labels = pd.concat([labels, pd.DataFrame({'symbol': [str(i) for i in range(7)],
        'oracle_decile': 5, 'target_quality_valid': 1, 'future_return': .005,
        'oracle_available_date': '2025-03-01'})], ignore_index=True)
    atr = {str(i): i+1 for i in range(10)}
    macro = {k: 1. for k in MACRO_FIELDS}
    macro['mode'] = 'normal'
    return scores, atr, labels, macro


def test_percentages_among_known_labels_and_original_deciles():
    out = summarize_day(*frames(), as_of=date(2026,1,1))
    assert out['intersection_count']==3
    assert out['d1_pct']==pytest.approx(100/3)
    assert out['d10_pct']==pytest.approx(100/3)
    assert out['d10_d1_ratio']==1
    assert out['d1_d10_total_pct']==pytest.approx(200/3)
    assert out['status']=='COMPLETE'


def test_future_labels_never_counted_as_available():
    out = summarize_day(*frames(), as_of=date(2025,2,1))
    assert out['evaluated_count']==0
    assert out['unknown_count']==3
    assert out['d1_pct'] is None and out['d10_pct'] is None
    assert out['d10_d1_ratio'] is None
    assert out['d1_d10_total_pct'] is None
    assert 'INCOMPLETE_LABELS' in out['quality_details']


@pytest.mark.parametrize('missing', [None, pd.NaT, 'invalid-date'])
def test_all_missing_availability_dates_remain_incomplete_without_crashing(missing):
    scores, atr, labels, macro = frames()
    labels['oracle_available_date'] = missing
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,10,6))
    assert out['evaluated_count'] == 0
    assert out['unknown_count'] == out['intersection_count'] == 3
    assert out['status'] == 'INCOMPLETE'
    assert 'INCOMPLETE_LABELS' in out['quality_details']
    assert all(out[field] is None for field in MOVEMENT_FIELDS)


def test_empty_labels_with_existing_scores_do_not_crash():
    scores, atr, labels, macro = frames()
    out = summarize_day(scores, atr, labels.iloc[:0], macro, as_of=date(2026,10,6))
    assert out['evaluated_count'] == 0 and out['unknown_count'] == 3
    assert 'INCOMPLETE_LABELS' in out['quality_details']


def test_availability_cutoff_is_inclusive_calendar_day():
    scores, atr, labels, macro = frames()
    labels['oracle_available_date'] = '2026-10-06 23:59:59'
    labels.loc[labels.symbol.eq('9'), 'oracle_available_date'] = '2026-10-07 00:00:00'
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,10,6))
    assert out['evaluated_count'] == 2 and out['unknown_count'] == 1


def test_invalid_labels_and_partial_denominator():
    scores, atr, labels, macro = frames()
    labels.loc[1,'target_quality_valid']=0
    labels.loc[2,'oracle_decile']=None
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    assert out['d1_pct']==100
    assert out['evaluated_count']==1 and out['unknown_count']==2
    assert out['evaluation_coverage_pct']==pytest.approx(100/3)
    assert out['status']=='INCOMPLETE'
    assert out['d1_d10_total_pct']==100


def test_absent_inputs_and_duplicate_guard():
    scores, atr, labels, macro = frames()
    out = summarize_day(scores.iloc[:0], {}, labels.iloc[:0], None, as_of=date(2026,1,1))
    assert out['regime_mode'] is None and out['vix'] is None
    assert out['d1_pct'] is None and 'MISSING_ORACLE' in out['quality_details']
    out = summarize_day(scores, {}, labels, macro, as_of=date(2026,1,1))
    assert 'MISSING_ATR' in out['quality_details']
    with pytest.raises(ValueError, match='Doublons'):
        summarize_day(pd.concat([scores,scores]), atr, labels, macro, as_of=date(2026,1,1))


def test_run_upserts_only_aggregate_and_repeat_has_same_keys():
    scores, atr, labels, macro = frames()
    scores['prediction_date']='2025-01-02'
    labels['prediction_date']='2025-01-02'
    macro['trade_date']='2025-01-02'
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value='alpha_trade'
    calendar = MagicMock()
    calendar.schedule.return_value=pd.DataFrame(index=pd.to_datetime(['2025-01-02']))
    writes = []
    with patch('service.market.oracle_atr_study.resolve_oracle_artifact_horizon',return_value=20), \
         patch('service.market.oracle_atr_study.load_universe_file_symbols',return_value=list(scores.symbol)), \
         patch('service.market.oracle_atr_study._get_nyse_calendar',return_value=calendar), \
         patch('service.market.oracle_atr_study.load_oracle_atr_by_date',return_value={'2025-01-02':atr}), \
         patch('service.market.oracle_atr_study.pd.read_sql',side_effect=[pd.DataFrame([macro]),scores,labels]*2):
        for _ in range(2):
            result=run(batch_id='batch',symbol_source='universe-file:test.txt',
                       start_date='2025-01-02',end_date='2025-01-02',engine=engine)
            writes.append(result['rows'])
    assert writes[0]==writes[1]
    sql=str(engine.begin.return_value.__enter__.return_value.execute.call_args.args[0])
    assert 'INSERT INTO oracle_atr_market_regime_daily' in sql
    assert 'ON DUPLICATE KEY UPDATE' in sql
    assert result['persisted_rows']==1 and result['complete_rows']==1


def test_wrong_database_is_blocked():
    engine=MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.scalar.return_value='alpha_trade_cn'
    with patch('service.market.oracle_atr_study.resolve_oracle_artifact_horizon',return_value=20), \
         patch('service.market.oracle_atr_study.load_universe_file_symbols',return_value=['A']):
        with pytest.raises(ValueError,match='alpha_trade'):
            run(batch_id='batch',symbol_source='universe-file:test.txt',
                start_date='2025-01-02',end_date='2025-01-02',engine=engine)
    engine.begin.assert_not_called()


def test_ui_command_has_identity_and_dates():
    from ihm.pages.market_regime import _oracle_study_command
    command=_oracle_study_command(date(2020,1,1),date(2026,9,30),'universe-file:a.txt','batch','artifacts/models')
    assert '--batch-id batch' in command
    assert '--symbol-source universe-file:a.txt' in command
    assert '--end-date 2026-09-30' in command
    assert '--date-batch-size 20' in command
    assert '--no-resume' not in command
    assert '--no-resume' in _oracle_study_command(date(2020,1,1),date(2026,9,30),
        'universe-file:a.txt','batch','artifacts/models',5,False)


@pytest.fixture
def tranche_environment():
    engine=MagicMock()
    conn=engine.connect.return_value.__enter__.return_value
    conn.execute.return_value.scalar.return_value='alpha_trade'
    conn.execute.return_value.scalars.return_value.all.return_value=[]
    calendar=MagicMock()
    calendar.schedule.return_value=pd.DataFrame(index=pd.to_datetime(['2025-01-02','2025-01-03']))
    with patch('service.market.oracle_atr_study.resolve_oracle_artifact_horizon',return_value=20), \
         patch('service.market.oracle_atr_study.load_universe_file_symbols',return_value=['A']), \
         patch('service.market.oracle_atr_study._get_nyse_calendar',return_value=calendar):
        yield engine, conn


def tranche_row(day):
    return {**summarize_day(*frames(),as_of=date(2026,1,1)), 'trade_date':day}


def test_failure_preserves_prior_tranche_and_resume_skips_it(tranche_environment):
    engine, conn=tranche_environment
    options=dict(batch_id='batch',symbol_source='universe-file:a.txt',start_date='2025-01-02',
                 end_date='2025-01-03',engine=engine,date_batch_size=1)
    with patch('service.market.oracle_atr_study._calculate_tranche',
               side_effect=[[tranche_row('2025-01-02')],RuntimeError('interruption')]):
        with pytest.raises(RuntimeError,match='interruption'):
            run(**options)
    assert engine.begin.call_count==1
    assert engine.begin.return_value.__exit__.call_args.args==(None,None,None)
    saved=engine.begin.return_value.__enter__.return_value.execute.call_args.args[1]
    assert saved[0]['trade_date']=='2025-01-02'
    conn.execute.return_value.scalars.return_value.all.return_value=[date(2025,1,2)]
    with patch('service.market.oracle_atr_study._calculate_tranche',
               return_value=[tranche_row('2025-01-03')]) as calculate:
        result=run(**options)
    assert calculate.call_args.args[2]==['2025-01-03']
    assert result['skipped_rows']==1 and result['persisted_rows']==1


def test_force_recalculates_complete_dates_and_commits_each_tranche(tranche_environment):
    engine, conn=tranche_environment
    conn.execute.return_value.scalars.return_value.all.return_value=[date(2025,1,2),date(2025,1,3)]
    with patch('service.market.oracle_atr_study._calculate_tranche',
               side_effect=[[tranche_row('2025-01-02')],[tranche_row('2025-01-03')]]) as calculate:
        result=run(batch_id='batch',symbol_source='universe-file:a.txt',start_date='2025-01-02',
                   end_date='2025-01-03',engine=engine,date_batch_size=1,resume=False)
    assert calculate.call_count==2 and engine.begin.call_count==2
    assert result['skipped_rows']==0 and result['persisted_rows']==2


def test_all_complete_no_price_read_or_write(tranche_environment):
    engine, conn=tranche_environment
    conn.execute.return_value.scalars.return_value.all.return_value=[date(2025,1,2),date(2025,1,3)]
    with patch('service.market.oracle_atr_study._calculate_tranche') as calculate:
        result=run(batch_id='batch',symbol_source='universe-file:a.txt',start_date='2025-01-02',
                   end_date='2025-01-03',engine=engine)
    calculate.assert_not_called()
    engine.begin.assert_not_called()
    assert result['skipped_rows']==2 and result['persisted_rows']==0


def test_targeted_repair_recalculates_only_requested_exchange_dates(tranche_environment):
    engine, _ = tranche_environment
    with patch('service.market.oracle_atr_study._calculate_tranche',
               return_value=[tranche_row('2025-01-03')]) as calculate:
        result = run(batch_id='batch', symbol_source='universe-file:a.txt',
                     start_date='2025-01-02', end_date='2025-01-03', engine=engine,
                     resume=False, trade_dates=['2025-01-03'])
    assert calculate.call_args.args[2] == ['2025-01-03']
    assert result['persisted_rows'] == 1


def test_targeted_repair_refuses_dates_outside_calendar(tranche_environment):
    engine, _ = tranche_environment
    with pytest.raises(ValueError, match='hors fenêtre'):
        run(batch_id='batch', symbol_source='universe-file:a.txt',
            start_date='2025-01-02', end_date='2025-01-03', engine=engine,
            resume=False, trade_dates=['2025-01-04'])
    engine.begin.assert_not_called()


@pytest.mark.parametrize('size',[0,-1,True,1.5])
def test_invalid_tranche_size_rejected_before_io(size):
    with pytest.raises(ValueError,match='date_batch_size'):
        run(batch_id='batch',symbol_source='universe-file:a.txt',start_date='2025-01-02',
            end_date='2025-01-03',date_batch_size=size)


def test_d10_d1_ratio_125_and_zero_denominator():
    scores=pd.DataFrame({'symbol':[str(i) for i in range(40)], 'proba_extreme':range(40)})
    atr={str(i):i+1 for i in range(40)}
    labels=pd.DataFrame({'symbol':[str(i) for i in range(31,40)], 'oracle_decile':[10]*5+[1]*4,
        'target_quality_valid':1, 'future_return':.1, 'oracle_available_date':'2025-01-01'})
    macro=frames()[3]
    out=summarize_day(scores,atr,labels,macro,as_of=date(2026,1,1))
    assert out['d10_d1_ratio']==1.25
    assert out['d10_d1_ratio']==pytest.approx(out['d10_pct']/out['d1_pct'])
    labels['oracle_decile']=10
    assert summarize_day(scores,atr,labels,macro,as_of=date(2026,1,1))['d10_d1_ratio'] is None
    labels['oracle_decile']=1
    assert summarize_day(scores,atr,labels,macro,as_of=date(2026,1,1))['d10_d1_ratio']==0


def test_total_is_sum_of_percentages_including_valid_zero():
    scores, atr, labels, macro=frames()
    out=summarize_day(scores,atr,labels,macro,as_of=date(2026,1,1))
    assert out['d1_d10_total_pct']==pytest.approx(out['d1_pct']+out['d10_pct'])
    labels['oracle_decile']=5
    out=summarize_day(scores,atr,labels,macro,as_of=date(2026,1,1))
    assert out['evaluated_count']==3
    assert out['d1_d10_total_pct']==0


def test_four_lists_use_selection_then_signed_absolute_order_and_percent_units():
    scores, atr, labels, macro = frames()
    # Biggest realized loser has a low predicted score and low ATR.
    labels.loc[labels.symbol.eq('0'), 'future_return'] = -.3
    atr['6'] = 100
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    assert out['evaluated_count'] == 2
    expected = {
        'real_oracle_top_returns_pct': [-30, 20],
        'intersection_returns_pct': [20, 1],
        'predicted_oracle_top_returns_pct': [20, 1],
        'predicted_oracle_score_order_returns_pct': [1, 20],
        'atr_top_returns_pct': [1, 1],
    }
    for field, values in expected.items():
        assert json.loads(out[field]) == pytest.approx(values)
    assert out['status'] == 'COMPLETE'


def test_missing_top_result_not_replaced_and_real_benchmark_requires_full_coverage():
    scores, atr, labels, macro = frames()
    labels.loc[labels.symbol.eq('9'), 'target_quality_valid'] = 0
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    assert out['evaluated_count'] == 2
    assert json.loads(out['intersection_returns_pct']) == [20, -10]
    assert out['predicted_oracle_top_returns_pct'] is None
    assert out['predicted_oracle_score_order_returns_pct'] is None
    assert out['atr_top_returns_pct'] is None
    assert out['real_oracle_top_returns_pct'] is None
    assert 'INCOMPLETE_PREDICTED_TOP_RETURNS' in out['quality_details']
    assert 'INCOMPLETE_ATR_TOP_RETURNS' in out['quality_details']
    assert 'INCOMPLETE_REAL_TOP_RETURNS' in out['quality_details']


@pytest.mark.parametrize('invalid', [float('inf'), float('-inf'), float('nan'), 'bad'])
def test_nonfinite_realized_return_never_serialized(invalid):
    scores, atr, labels, macro = frames()
    labels['future_return'] = labels.future_return.astype(object)
    labels.loc[labels.symbol.eq('8'), 'future_return'] = invalid
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    assert out['evaluated_count'] == 2
    assert out['real_oracle_top_returns_pct'] is None
    assert json.loads(out['intersection_returns_pct']) == [-10, 1]


@pytest.mark.parametrize('value,expected', [
    (.082, 8), (-.075, -8), (.069, 7), (.005, 1), (-.005, -1),
    (.0049, 0), (-.0049, 0), (1.235, 124), (-1.235, -124),
])
def test_all_five_lists_store_json_integers(value, expected):
    scores, atr, labels, macro = frames()
    # Keep a genuine TOP20 pool: only the three selected titles have this amplitude.
    labels['future_return'] = 0.
    labels.loc[labels.symbol.isin(['7', '8', '9']), 'future_return'] = value
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    for field in MOVEMENT_FIELDS:
        values = json.loads(out[field])
        assert values == [expected] * out['evaluated_count']
        assert all(type(v) is int for v in values)
    assert out['d1_pct'] == pytest.approx(100/3)
    assert out['d10_d1_ratio'] == 1


def test_no_evaluable_candidates_means_null_not_empty_lists():
    out = summarize_day(*frames(), as_of=date(2025,2,1))
    assert all(out[field] is None for field in MOVEMENT_FIELDS)


def test_duplicate_dataframe_indices_and_input_order_do_not_change_lists():
    scores, atr, labels, macro = frames()
    expected = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    labels = labels.sample(frac=1, random_state=1)
    labels.index = [0]*len(labels)
    out = summarize_day(scores.sample(frac=1, random_state=2), atr, labels, macro, as_of=date(2026,1,1))
    assert out == expected


def test_tied_selection_uses_symbol_not_future_return():
    scores, atr, labels, macro = frames()
    scores.loc[scores.symbol.isin(['6','7','8','9']), 'proba_extreme'] = 100
    # Average percentile .85 makes all four tied scores TOP20.
    # ATR intersects three; selection of Oracle first three is 6,7,8, not 7,8,9.
    labels.loc[labels.symbol.eq('9'), 'future_return'] = .9
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    assert out['evaluated_count'] == 3
    assert json.loads(out['predicted_oracle_top_returns_pct']) == [20, -10, 1]
    assert json.loads(out['predicted_oracle_score_order_returns_pct']) == [1, -10, 20]
    assert json.loads(out['intersection_returns_pct']) == [90, 20, -10]


def test_new_version_preflight_and_resume_query(tranche_environment):
    engine, conn = tranche_environment
    with patch('service.market.oracle_atr_study._calculate_tranche',
               return_value=[tranche_row('2025-01-02')]):
        result = run(batch_id='batch', symbol_source='universe-file:a.txt',
                     start_date='2025-01-02', end_date='2025-01-03', engine=engine)
    assert result['rows'][0]['calculation_version'] == CALCULATION_VERSION
    calls = conn.execute.call_args_list
    assert all(field in str(calls[1].args[0]) for field in MOVEMENT_FIELDS)
    assert calls[2].args[1]['version'] == CALCULATION_VERSION
    write = engine.begin.return_value.__enter__.return_value.execute.call_args
    assert all(field in str(write.args[0]) for field in MOVEMENT_FIELDS)
    assert isinstance(write.args[1][0]['intersection_returns_pct'], str)


def _movement_migration(filename='0092_oracle_atr_movements.py'):
    path = Path(__file__).parents[1]/'alembic/versions'/filename
    spec = importlib.util.spec_from_file_location('movement_migration', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_migration_adds_missing_columns_and_is_idempotent():
    migration = _movement_migration()
    with patch.object(migration, 'context') as context, patch.object(migration, 'op') as op, \
         patch.object(migration, 'inspect') as inspect:
        context.is_offline_mode.return_value = False
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade'
        inspect.return_value.get_columns.return_value = [{'name': MOVEMENT_FIELDS[0]}]
        migration.upgrade()
        assert op.execute.call_count == 3
        assert all('JSON NULL' in call.args[0] for call in op.execute.call_args_list)
        op.execute.reset_mock()
        inspect.return_value.get_columns.return_value = [{'name': field} for field in MOVEMENT_FIELDS]
        migration.upgrade()
        op.execute.assert_not_called()


def test_score_order_migration_idempotent_and_us_only():
    migration = _movement_migration('0094_oracle_atr_score_order.py')
    with patch.object(migration, 'context') as context, patch.object(migration, 'op') as op, \
         patch.object(migration, 'inspect') as inspect:
        context.is_offline_mode.return_value = False
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade'
        inspect.return_value.get_columns.return_value = []
        migration.upgrade()
        assert op.execute.call_count == 1
        assert migration.COLUMN in op.execute.call_args.args[0]
        op.execute.reset_mock()
        inspect.return_value.get_columns.return_value = [{'name': migration.COLUMN}]
        migration.upgrade()
        op.execute.assert_not_called()
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade_cn'
        with pytest.raises(RuntimeError, match='alpha_trade'):
            migration.upgrade()
        op.execute.assert_not_called()


@pytest.mark.parametrize('operation', ['upgrade', 'downgrade'])
def test_movement_migration_blocks_other_markets(operation):
    migration = _movement_migration()
    with patch.object(migration, 'context') as context, patch.object(migration, 'op') as op:
        context.is_offline_mode.return_value = False
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade_fr'
        with pytest.raises(RuntimeError, match='alpha_trade'):
            getattr(migration, operation)()
        op.execute.assert_not_called()


def test_partial_lists_keep_original_selection_without_replacements():
    scores, atr, labels, macro = frames()
    labels.loc[labels.symbol.eq('9'), 'target_quality_valid'] = 0
    labels.loc[labels.symbol.eq('9'), 'target_quality_reason'] = 'EXIT_PRICE_MISSING'
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1), missing_returns_policy='partial')
    assert out['status'] == 'PARTIAL' and out['evaluated_count'] == 2
    assert json.loads(out['predicted_oracle_score_order_returns_pct']) == [20]
    assert json.loads(out['predicted_oracle_top_returns_pct']) == [20]
    info = json.loads(out['movement_quality'])['lists']['predicted_oracle_score_order_returns_pct']
    assert info['selection_symbols'] == ['9', '8']  # Not replaced by 7.
    assert info['value_symbols'] == ['8']
    assert info['original_selection_positions'] == [2]
    assert info['missing_symbols'] == ['9']
    assert info['missing_reasons'] == {'9': 'EXIT_PRICE_MISSING'}
    assert info['known_count'] == 1 and info['coverage_pct'] == 50


def test_partial_real_top_explicitly_has_incomplete_reference_and_shortfall():
    scores, atr, labels, macro = frames()
    labels.loc[labels.symbol.eq('0'), 'target_quality_valid'] = 0
    out = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1), missing_returns_policy='partial')
    info = json.loads(out['movement_quality'])['lists']['real_oracle_top_returns_pct']
    assert info['selection_basis'] == 'REALIZED_TOP20_AMONG_EVALUABLE_SYMBOLS'
    assert info['reference_missing_symbols'] == ['0']
    assert info['reference_coverage_pct'] == 90
    assert info['status'] == 'PARTIAL'
    assert info['requested_count'] == 3 and info['known_count'] == 2
    assert info['selection_shortfall_count'] == 1
    assert info['coverage_pct'] == pytest.approx(200/3)
    assert json.loads(out['real_oracle_top_returns_pct']) == [20, -10]
    strict = summarize_day(scores, atr, labels, macro, as_of=date(2026,1,1))
    assert strict['real_oracle_top_returns_pct'] is None


def test_partial_immature_day_never_uses_even_misdated_labels():
    out = summarize_day(*frames(), as_of=date(2026,1,1), missing_returns_policy='partial',
                        expected_available_date=date(2026,1,2))
    assert all(out[field] is None for field in MOVEMENT_FIELDS)
    assert out['evaluated_count'] == 0 and out['status'] == 'INCOMPLETE'
    assert 'HORIZON_NOT_YET_AVAILABLE' in out['quality_details']


def test_partial_quality_alignment_and_integer_values():
    out = summarize_day(*frames(), as_of=date(2026,1,1), missing_returns_policy='partial')
    for field, info in json.loads(out['movement_quality'])['lists'].items():
        assert len(json.loads(out[field])) == info['known_count'] == len(info['value_symbols'])
        assert all(type(value) is int for value in json.loads(out[field]))
    with pytest.raises(ValueError, match='strict ou partial'):
        summarize_day(*frames(), as_of=date(2026,1,1), missing_returns_policy='unknown')


def test_partial_migration_is_idempotent_and_rejects_fr():
    migration = _movement_migration('0095_oracle_atr_partial_returns.py')
    with patch.object(migration, 'context') as context, patch.object(migration, 'op') as op, \
         patch.object(migration, 'inspect') as inspector:
        context.is_offline_mode.return_value = False
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade'
        inspector.return_value.get_columns.return_value = []
        migration.upgrade()
        assert op.execute.call_count == 2
        op.execute.reset_mock()
        inspector.return_value.get_columns.return_value = [{'name': name} for name in migration.COLUMNS]
        migration.upgrade()
        op.execute.assert_not_called()
        op.get_bind.return_value.execute.return_value.scalar.return_value = 'alpha_trade_fr'
        with pytest.raises(RuntimeError, match='alpha_trade'):
            migration.upgrade()
