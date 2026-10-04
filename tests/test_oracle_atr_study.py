from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from service.market.oracle_atr_study import MACRO_FIELDS, run, summarize_day


def frames():
    scores = pd.DataFrame({'symbol': [str(i) for i in range(10)], 'proba_extreme': range(10)})
    labels = pd.DataFrame({'symbol': ['7','8','9'], 'oracle_decile': [1,10,5],
        'target_quality_valid': [1,1,1], 'future_return': [-.1,.2,.01],
        'oracle_available_date': ['2025-03-01']*3})
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
