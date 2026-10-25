"""Offline synthetic tests, never production data/API/positions."""
from copy import deepcopy
from types import SimpleNamespace
import json

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine

from scripts.research import us_gpt_august_2026_path_audit as study
from service.llm_directional.config import FilterConfig
from service.llm_directional.news_cache import META,atomic_json,NewsCache,sha
from service.llm_directional.prompts import TREND_EVIDENCE_VERSION


def fixture():
    start=pd.Timestamp('2026-08-04T13:30Z')
    window=[SimpleNamespace(open_at_utc=start,close_at_utc=start+pd.Timedelta(minutes=20),session_date=start.date())]
    stamps=pd.date_range(start,periods=4,freq='5min')
    frame=pd.DataFrame(dict(symbol='ABC',bar_timestamp=stamps,bar_end_timestamp=stamps+pd.Timedelta(minutes=5),
        open=[100.,105.,110.,95.],high=[110.,118.,112.,100.],low=[98.,102.,85.,90.],close=[105.,110.,95.,96.],
        volume=100,is_filled=0,data_adjustment='raw'))
    actions=pd.DataFrame(columns=['symbol','action_type','effective_date','value_num'])
    return frame,window,actions


def test_both_excursions_from_same_open_not_h20_close():
    frame,window,actions=fixture()
    result=study.measure_path(frame,window,{},'ABC',actions)
    assert result['path_status']=='QUALIFIED_COMPLETE_5M'
    assert result['high_max_pct']==pytest.approx(18)
    assert result['low_min_pct']==pytest.approx(-15)
    assert result['h20_close_return_pct']==pytest.approx(-4)
    assert result['dominant_direction']=='LONG'
    assert result['first_extremum']=='HIGH_FIRST'


@pytest.mark.parametrize('fault',['missing','invalid','duplicate','filled','split','entry_missing'])
def test_quality_failures_never_become_qualified_paths(fault):
    frame,window,actions=fixture()
    if fault=='missing':frame=frame.drop(index=1)
    elif fault=='invalid':frame.loc[1,'high']=90
    elif fault=='duplicate':frame=pd.concat([frame,frame.iloc[[1]]])
    elif fault=='filled':frame.loc[1,'is_filled']=1
    elif fault=='split':actions=pd.DataFrame([dict(symbol='ABC',action_type='split',effective_date=window[0].session_date,value_num=2)])
    else:frame=frame.drop(index=0)
    result=study.measure_path(frame,window,{},'ABC',actions)
    assert result['path_status']!='QUALIFIED_COMPLETE_5M'


def test_same_bar_order_is_not_invented_and_global_extrema_not_first_direction():
    frame,window,actions=fixture();frame.loc[1,'low']=80
    result=study.measure_path(frame,window,{},'ABC',actions)
    assert result['first_extremum']=='SAME_5M_BAR_UNRESOLVED'
    assert result['dominant_direction']=='SHORT'
    frame.loc[1,'low']=90;frame.loc[0,'low']=80
    result=study.measure_path(frame,window,{},'ABC',actions)
    assert result['first_extremum']=='LOW_FIRST'


def context():
    return dict(symbol='ABC',oracle_rank=1,oracle_score=.9,issuer_reference={'company_name':'ABC','exchange':'NASDAQ'},
        trade_date='2026-08-03',horizon_sessions=20,analysis_mode='local_data_only',analysis_protocol=TREND_EVIDENCE_VERSION,
        local_evidence=[dict(source_id='news:1',kind='news',text='Company raised revenue guidance.',eligible_for_direction=False)],
        local_evidence_sha256='a',local_data_status={},freshness_policy={},evidence_exclusions={},
        evidence_cutoff_utc='2026-08-03T20:00:00+00:00')


def answer(request):
    value=dict(symbol='ABC',issuer='ABC',identity_verified=True,confidence=.8,
        bull_case='Revenue guidance raised',bear_case='Uncertainty',catalysts=[],sources=[],
        local_evidence=[dict(source_id='news:1',quote='raised revenue guidance')],
        consensus_analysis='No archived consensus',context_analysis='Historical reconstructed data only',
        direction_score=7,trend_status='ASSESSED',evidence_quality='PARTIAL',evidence_explanation='Historical receipts not PIT')
    return dict(status='completed',model='gpt-6-luna',usage=dict(input_tokens=1000,output_tokens=200,input_tokens_details={}),
        output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(value))])])


def request():
    cfg=FilterConfig(model='gpt-6-luna',analysis_mode='local_data_only',scoring_mode='direction_1_10',separate_trend_evidence=True)
    return study.request_for(context(),cfg)


@pytest.mark.parametrize('fault',[None,'score','quote','tool','future_outcome','account','duplicate_keys','truncated'])
def test_request_and_response_validation(fault):
    req=request();raw=answer(req)
    if fault in ('score','quote'):
        val=json.loads(raw['output'][0]['content'][0]['text'])
        if fault=='score':val['direction_score']=11
        else:val['local_evidence'][0]['quote']='invented'
        raw['output'][0]['content'][0]['text']=json.dumps(val)
    elif fault=='tool':raw['output'].append(dict(type='web_search_call'))
    elif fault=='future_outcome':
        ctx=json.loads(req['input']);ctx['future_return']=.3;req['input']=json.dumps(ctx)
    elif fault=='account':
        ctx=json.loads(req['input']);ctx['account_equity']=4000;req['input']=json.dumps(ctx)
    elif fault=='duplicate_keys':raw['output'][0]['content'][0]['text']=raw['output'][0]['content'][0]['text'].replace('"direction_score": 7','"direction_score": 7,"direction_score": 8')
    elif fault=='truncated':raw['status']='incomplete'
    if fault:
        with pytest.raises(Exception):
            study.check_request(req);study.qualify(raw,req)
    else:
        study.check_request(req);parsed=study.qualify(raw,req)
        assert parsed['direction_score']==7 and parsed['research_only']


@pytest.mark.parametrize('fault',[None,'missing_usage','too_many_output','fast_tier','other_model'])
def test_cost_includes_cache_writes_and_bounds(fault):
    req=request();raw=answer(req)
    raw['usage']['input_tokens_details']={'cache_write_tokens':100,'cached_tokens':200}
    if fault=='missing_usage':raw.pop('usage')
    elif fault=='too_many_output':raw['usage']['output_tokens']=req['max_output_tokens']+1
    elif fault=='fast_tier':raw['service_tier']='fast'
    elif fault=='other_model':raw['model']='another'
    if fault:
        with pytest.raises(ValueError):study.usage_cost(raw,req)
    else:
        assert float(study.usage_cost(raw,req))==pytest.approx(.0002025)
        assert study.upper_cost(req)>study.usage_cost(raw,req)


def test_statistics_match_same_population_and_nonoverlap_control():
    frame,window,actions=fixture();path=study.measure_path(frame,window,{},'ABC',actions)
    data=pd.DataFrame([dict(date='2026-08-03',symbol='ABC',status='VALID',direction_score=7,**path),
        dict(date='2026-08-04',symbol='ABC',status='VALID',direction_score=8,**path)])
    result=study.score_summary(data)
    assert result['directional_accuracy_pct']==100
    assert result['always_long_accuracy_pct']==100
    assert result['nonoverlap_by_symbol']['n']==1


def test_exact_archived_research_call_is_not_paid_again(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=__import__('sqlalchemy').pool.StaticPool)
    META.create_all(engine);cache=NewsCache(engine);req=request();raw=answer(req)
    archived=dict(request=req,response=raw,response_sha256=sha(raw),status='VALID',assessment=study.qualify(raw,req),cost_usd='.001')
    cache.save_import(study.PREFIX+':response:'+sha(req),archived)
    atomic_json(tmp_path/'requests.json',[req]);atomic_json(tmp_path/'protocol.json',dict(files={},source_hashes={},configuration=FilterConfig(model='gpt-6-luna').snapshot()))
    monkeypatch.setattr(study,'ResponsesClient',lambda *a:pytest.fail('No paid duplicate allowed'))
    result=study.analyze(engine,tmp_path,workers=1)
    assert result['valid']==1 and result['committed_usd']==0
    engine.dispose()


def test_unknown_prior_claim_blocks_paid_retry(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=__import__('sqlalchemy').pool.StaticPool)
    META.create_all(engine);req=request()
    NewsCache(engine).save_import(study.PREFIX+':claim:'+sha(req),dict(request_sha256=sha(req)))
    atomic_json(tmp_path/'requests.json',[req]);atomic_json(tmp_path/'protocol.json',dict(files={},source_hashes={},configuration=FilterConfig(model='gpt-6-luna').snapshot()))
    monkeypatch.setattr(study,'ResponsesClient',lambda *a:pytest.fail('No ambiguous paid retry'))
    result=study.analyze(engine,tmp_path,workers=1)
    assert result['status']=='PARTIAL_STOPPED' and result['completed']==0
    engine.dispose()


def test_budget_cap_stops_before_any_paid_call(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=__import__('sqlalchemy').pool.StaticPool)
    META.create_all(engine);req=request()
    atomic_json(tmp_path/'budget.json',dict(cap_usd='4',entries={'previous':dict(charge_usd='3.999',status='RESERVED')}))
    atomic_json(tmp_path/'requests.json',[req]);atomic_json(tmp_path/'protocol.json',dict(files={},source_hashes={},configuration=FilterConfig(model='gpt-6-luna').snapshot()))
    monkeypatch.setattr(study,'ResponsesClient',lambda *a:pytest.fail('Budget exceeded before transport'))
    result=study.analyze(engine,tmp_path,workers=1)
    assert result['status']=='PARTIAL_STOPPED' and result['committed_usd']==3.999
    engine.dispose()


def test_input_price_context_excludes_future_rows():
    dates=pd.to_datetime(['2026-07-31','2026-08-03','2026-08-04'])
    prices=pd.DataFrame(dict(date=dates,symbol='ABC',open=[99.,100.,999.],high=[102.,103.,1001.],
        low=[98.,99.,998.],close=[100.,101.,1000.],volume=100,is_filled=0,data_source='alpaca_sip',
        data_adjustment='split',ingested_at=pd.Timestamp('2026-10-01'),last_updated=pd.Timestamp('2026-10-01')))
    calendar=[SimpleNamespace(session_date=d.date()) for d in dates]
    closes,source,error=study.price_context(prices,pd.Timestamp('2026-08-03'),calendar)
    assert error is None and len(closes)==2 and closes[-1]['close']==101
    assert '999' not in source['text'] and source['eligible_for_direction'] is False


def test_future_news_and_possible_secret_are_never_sent():
    dates=pd.to_datetime(['2026-07-31','2026-08-03'])
    calendar=[SimpleNamespace(session_date=d.date(),close_at_utc=pd.Timestamp(str(d.date())+'T20:00Z')) for d in dates]
    prices=pd.DataFrame(dict(date=dates,symbol='ABC',open=100.,high=102.,low=98.,close=101.,volume=100,
        is_filled=0,data_source='alpaca_sip',data_adjustment='split',
        ingested_at=pd.Timestamp('2026-10-01'),last_updated=pd.Timestamp('2026-10-01')))
    common=dict(symbol='ABC',article_id='secret',headline='Issuer news',summary='',body='sk-proj-'+'x'*30,
        published_at_utc=pd.Timestamp('2026-08-03T16:00Z'),provider_publication='2026-08-03T16:00:00Z',
        content_sha256='hash1',content_chars=200,created_at=pd.Timestamp('2026-10-01'),updated_at=pd.Timestamp('2026-10-01'))
    future=dict(common,article_id='future',headline='FUTURE_OUTCOME',body='Future news',content_sha256='hash2',
        published_at_utc=pd.Timestamp('2026-08-04T16:00Z'),provider_publication='2026-08-04T16:00:00Z')
    cfg=FilterConfig(model='gpt-6-luna',analysis_mode='local_data_only',scoring_mode='direction_1_10',separate_trend_evidence=True)
    ctx=study.make_context(SimpleNamespace(symbol='ABC',date=dates[-1],oracle_rank=1,score=.9),pd.DataFrame([common,future]),
        prices,{'company_name':'ABC','exchange':'NASDAQ'},cfg,calendar)
    assert [s['kind'] for s in ctx['local_evidence']]==['price_volume']
    assert ctx['evidence_exclusions']['POSSIBLE_SECRET_PATTERN_IN_ARCHIVED_NEWS']==1
    req=study.request_for(ctx,cfg);study.check_request(req)
    assert 'FUTURE_OUTCOME' not in req['input'] and 'sk-proj-' not in req['input']
