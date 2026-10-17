"""No real SQL, API key or paid transport."""
from decimal import Decimal
from threading import Event
import copy

import pandas as pd
import pytest
from sqlalchemy import create_engine

from scripts.research import us_news_gpt_top20_history as campaign
from service.llm_directional.news_cache import META,NewsCache,request_identity


def packet():
    return dict(decision_date='2025-01-02',cutoff_utc='2025-01-02T21:00:00+00:00',
        symbol='TEST',oracle_rank=1,batch_id=campaign.MODELS[2025],
        issuer_reference={'company_name':'Test Corp'},articles=[dict(article_id='one',
        headline='The company raises new capital.',summary='',body='The company raises new capital.',
        publication_utc='2025-01-02T18:00:00+00:00',body_truncated=False,body_sha256='a'*64)])


def response(invalid=False):
    import json
    value=dict(decision='BEARISH',confidence=.85,issuer_match='MATCH',basis='MATERIAL_FACT',
        reason='Capital raising',evidence=[dict(article_id='one',kind='FINANCING',
            quote='an invented adverse quote' if invalid else 'company raises new capital')])
    return dict(status='completed',model='gpt-6-luna',service_tier='default',
        usage=dict(input_tokens=100,output_tokens=50,input_tokens_details={'cache_write_tokens':100}),
        output=[dict(type='message',content=[dict(type='output_text',text=json.dumps(value))])])


@pytest.fixture
def cache(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'cache.db'));META.create_all(engine)
    yield NewsCache(engine)
    engine.dispose()


def test_budget_reserves_before_call_and_survives_restart(tmp_path):
    path=tmp_path/'budget.json';b=campaign.Budget(path,cap='.002')
    req=campaign.paid_payload(packet(),campaign.MODEL)
    b.reserve('one',req)
    assert campaign.Budget(path,cap='.002').summary()['unresolved']==1
    with pytest.raises(campaign.BudgetStop):b.reserve('two',req)
    assert 'two' not in campaign.read(path)['entries']
    with pytest.raises(ValueError):campaign.Budget(path,cap='8.01')


def test_paid_answer_saved_then_exact_db_reuse(cache,tmp_path):
    b=campaign.Budget(tmp_path/'budget.json');calls=[];stop=Event()
    def call(req):calls.append(req);return response()
    def run():return campaign.assess(packet(),cache,b,'test',tmp_path/'spool',stop,call)
    one=run();two=run()
    assert len(calls)==1 and one['veto_long'] and two['cache_hit']
    assert b.summary()['paid_calls']==1 and b.summary()['unresolved']==0
    assert Decimal(str(b.summary()['cost_usd']))==Decimal('.0000375')
    assert one['raw_response_sha256']==two['raw_response_sha256']


def test_no_input_does_not_spend_or_claim(cache,tmp_path):
    b=campaign.Budget(tmp_path/'budget.json');p=packet();p['articles']=[]
    out=campaign.assess(p,cache,b,'test',tmp_path/'spool',Event(),lambda _:pytest.fail('API'))
    assert out['decision']=='UNKNOWN_NO_QUALIFIED_TEXT' and not b.state['entries']


def test_invalid_evidence_is_retained_not_repaid(cache,tmp_path):
    b=campaign.Budget(tmp_path/'budget.json');calls=[]
    def call(req):calls.append(req);return response(True)
    out=campaign.assess(packet(),cache,b,'test',tmp_path/'spool',Event(),call)
    again=campaign.assess(packet(),cache,b,'test2',tmp_path/'spool',Event(),lambda _:pytest.fail('repay'))
    assert out['decision']==again['decision']=='UNKNOWN_INVALID_RESPONSE'
    assert len(calls)==1 and not again['veto_long']


def test_unknown_paid_attempt_stops_without_retry(cache,tmp_path):
    b=campaign.Budget(tmp_path/'budget.json');stop=Event();calls=[]
    def fail(req):calls.append(req);raise TimeoutError('possibly charged')
    with pytest.raises(campaign.UnresolvedAttempt):campaign.assess(packet(),cache,b,'test',tmp_path/'spool',stop,fail)
    assert stop.is_set() and b.summary()['unresolved']==1
    with pytest.raises(campaign.UnresolvedAttempt):campaign.reconcile(cache,b,tmp_path/'spool','test')
    with pytest.raises(campaign.UnresolvedAttempt):campaign.assess(packet(),cache,b,'test',tmp_path/'spool',Event(),fail)
    assert len(calls)==1


def test_spooled_response_recovers_without_api(cache,tmp_path):
    b=campaign.Budget(tmp_path/'budget.json');req=campaign.paid_payload(packet(),campaign.MODEL)
    key,_,_=cache.claim(req,campaign.SCOPE);b.reserve(key,req);b.started(key)
    folder=tmp_path/'spool'/key;folder.mkdir(parents=True)
    campaign.atomic_json(folder/'request.json',req);campaign.atomic_json(folder/'response.json',response())
    campaign.reconcile(cache,b,tmp_path/'spool','recovery')
    assert b.summary()['paid_calls']==1 and cache.get(key)['status']=='VALID'


def test_model_years_and_lineage_fail_closed():
    assert set(campaign.MODELS)=={2024,2025,2026}
    model=dict(universe=['TEST'],fold='2024-12-05',model_sha256='a',profile_sha256='b',available_date='2024-12-04')
    row=dict(date=pd.Timestamp('2025-01-02'),symbol='TEST',fold_start='2024-12-05',lineage_fold='2024-12-05',
        model_sha256='a',feature_profile_sha256='b',model_available_date='2024-12-04',target_name='oracle_path_extreme20',
        target_horizon=20,future_return=None,oracle_extreme10=None)
    campaign.validate_scores(pd.DataFrame([row]),model)
    for field,value in [('model_sha256','wrong'),('model_available_date','2025-01-03'),('future_return',.5),('symbol','OTHER')]:
        altered=copy.deepcopy(row);altered[field]=value
        with pytest.raises(ValueError):campaign.validate_scores(pd.DataFrame([altered]),model)


def test_sorted_snapshot_restores_exact_legacy_request():
    import json
    from scripts.research.us_news_gpt_q1_2025_run import paid_payload as original
    value=packet();value['issuer_reference']=dict(symbol='TEST',company_name='Test Corp',exchange='NASDAQ')
    sorted_copy=json.loads(json.dumps(value,sort_keys=True))
    assert campaign.paid_payload(sorted_copy,campaign.MODEL)==original(value,campaign.MODEL)
    altered=copy.deepcopy(sorted_copy);altered['articles'][0]['body']+=' A new fact.'
    assert campaign.paid_payload(altered,campaign.MODEL)!=original(value,campaign.MODEL)


def test_parallel_reservations_cannot_exceed_ceiling(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    b=campaign.Budget(tmp_path/'budget.json',cap='.002')
    req=campaign.paid_payload(packet(),campaign.MODEL)
    def reserve(i):
        try:b.reserve(str(i),req);return True
        except campaign.BudgetStop:return False
    with ThreadPoolExecutor(max_workers=4) as pool:values=list(pool.map(reserve,range(8)))
    assert sum(values)==1 and b.committed()<=Decimal('.002')


def test_month_saved_in_sql_including_absent_news_and_replayed_without_api(cache,tmp_path):
    month='2025-01';folder=tmp_path/'months'/month;folder.mkdir(parents=True)
    value=packet();empty=copy.deepcopy(value);empty.update(symbol='NONE',oracle_rank=2,articles=[])
    campaign.atomic_json(folder/'packets.json',[value,empty])
    campaign.atomic_json(folder/'availability.json',[])
    campaign.atomic_json(folder/'prepared.json',{'status':'SCORES_VERIFIED'})
    req=campaign.paid_payload(value,campaign.MODEL)
    cache.import_response(req,response(),scope=campaign.SCOPE,consumer='prior',provenance={},qualifier=campaign.parse)
    budget=campaign.Budget(tmp_path/'budget.json')
    result=campaign.analyze_month(tmp_path,{'model':'frozen'},month,cache.engine,budget,2)
    saved=campaign.read(folder/'assessments'/'0001.json')
    assert saved['decision']=='UNKNOWN_NO_QUALIFIED_TEXT'
    assert result['candidate_days']==2 and budget.summary()['paid_calls']==0
    snapshot=cache.get_import(result['sql_completed_import_id'])
    import json
    assert len(json.loads(snapshot['snapshot_json'])['assessments'])==2
    assert campaign.analyze_month(tmp_path,{'model':'frozen'},month,cache.engine,budget,2)==result
