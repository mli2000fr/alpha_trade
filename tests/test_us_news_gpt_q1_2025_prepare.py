"""Pure fixtures; never MySQL, APIs, paid calls, real models or financial PnL."""
import pandas as pd
import pytest

from scripts.research import us_news_gpt_q1_2025_prepare as study


def scores():
    return pd.DataFrame({'date':pd.to_datetime(['2025-01-02']*12),'symbol':[f'T{i:02d}' for i in range(12)],
        'score':[.9-i*.05 for i in range(12)]})


def test_top10_is_count_not_fraction_and_not_future_rank():
    data=scores();data['future_return']=list(range(12))
    actual=study.fixed_top(data,10)
    assert actual.symbol.tolist()==[f'T{i:02d}' for i in range(10)]
    assert actual.oracle_rank.tolist()==list(range(1,11))


def test_ties_by_symbol_not_input_order():
    data=scores();data['score']=.5
    expected=study.fixed_top(data,10)
    actual=study.fixed_top(data.sample(frac=1,random_state=7),10)
    assert actual.symbol.tolist()==expected.symbol.tolist()


@pytest.mark.parametrize('bad',['duplicate','nan','outside','too_small'])
def test_invalid_score_pool_fails_closed(bad):
    data=scores()
    if bad=='duplicate':data=pd.concat([data,data.iloc[:1]],ignore_index=True)
    if bad=='nan':data.loc[0,'score']=float('nan')
    if bad=='outside':data.loc[0,'score']=2
    if bad=='too_small':data=data.iloc[:9]
    with pytest.raises(ValueError):study.fixed_top(data,10)


def test_original_top5_is_reproduced():
    top=study.fixed_top(scores(),10)
    result=study.compare_original_top5(top,top.iloc[:5])
    assert result['rows_compared']==5 and result['score_max_absolute_error']==0


def test_original_top5_membership_mismatch_rejected():
    top=study.fixed_top(scores(),10);old=top.iloc[:5].copy();old.loc[0,'symbol']='WRONG'
    with pytest.raises(AssertionError):study.compare_original_top5(top,old)


def test_original_top5_score_drift_rejected():
    top=study.fixed_top(scores(),10);old=top.iloc[:5].copy();old.loc[0,'score']+=.01
    with pytest.raises(ValueError):study.compare_original_top5(top,old)


def test_packet_contains_only_accepted_article_and_marks_truncation():
    item=dict(decision_date='2025-01-02',symbol='T00',oracle_rank=1,cutoff_utc='2025-01-02T21:00:00Z',
        accepted_article_ids=['a'])
    metadata=pd.DataFrame({'article_id':['a'],'published_at_utc':pd.to_datetime(['2025-01-02T12:00:00Z']),
        'content_chars':[5000]}).set_index('article_id')
    bodies={'a':{'headline':'<p>Headline</p>','summary':'Text','body':'A'*4000,'body_sha256':'h'}}
    packet=study.packet_for(item,metadata,bodies,{'company_name':'Test'})
    assert packet['articles'][0]['body_truncated']
    assert len(packet['articles'][0]['body'])==2400
    assert 'score' not in packet and 'future_return' not in packet


def test_missing_body_does_not_invent_content():
    item=dict(decision_date='2025-01-02',symbol='T00',oracle_rank=1,cutoff_utc='2025-01-02T21:00:00Z',accepted_article_ids=['a'])
    metadata=pd.DataFrame({'article_id':['a'],'published_at_utc':pd.to_datetime(['2025-01-02T12:00:00Z']),
        'content_chars':[None]}).set_index('article_id')
    packet=study.packet_for(item,metadata,{'a':{'headline':'News','summary':None,'body':None,'body_sha256':None}},None)
    assert packet['articles'][0]['body']=='' and packet['issuer_reference']=={}


def test_news_cutoff_excludes_exact_close_and_does_not_require_historical_import():
    candidates=pd.DataFrame({'date':pd.to_datetime(['2025-01-02']),'symbol':['T00'],'oracle_rank':[1],'selected':[True]})
    news=pd.DataFrame({'article_id':['a','b'],'symbol':['T00','T00'],'ingestion_source':['eodhd','eodhd'],
        'published_at_utc':pd.to_datetime(['2025-01-02T12:00:00Z','2025-01-02T21:00:00Z']),
        'provider_publication':['2025-01-02T12:00:00Z','2025-01-02T21:00:00Z'],'content_chars':[300,300]})
    for field in ['created_at','updated_at','map_created_at','map_updated_at']:
        news[field]=pd.to_datetime(['2026-01-01T00:00:00Z']*2)
    result=study.panel_rows(candidates,news,{pd.Timestamp('2025-01-02'):pd.Timestamp('2025-01-02T21:00:00Z')})[0]
    assert result['article_ids']==['a'] and result['accepted_article_ids']==['a']
    assert result['conservative_guarded_pairs']==0
    assert result['guard_reasons']['CREATED_AT_NOT_BEFORE_DECISION']==1


def test_admission_uses_oracle_rank_from_candidates_not_raw_price_features():
    from types import SimpleNamespace
    group=pd.DataFrame({'date':pd.to_datetime(['2025-01-02','2025-01-03']),
        'symbol':['T00','T00'],'oracle_rank':[6,10]})
    features=pd.DataFrame({'price_feature':[1.,float('nan')]},index=group.date)
    quality=pd.Series(True,index=group.date)
    dataset=SimpleNamespace(STOCK=['price_feature'],MARKET=[],FEATURES=['price_feature','oracle_rank'])
    actual=study.j_history_admission(group,features,quality,dataset)
    assert [row['selected'] for row in actual]==[True,False]
