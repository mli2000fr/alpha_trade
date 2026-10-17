from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
import yaml

from scripts.research import us_news_financing_feasibility as audit


def stamp(value):
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def sessions():
    return [SimpleNamespace(is_open=True,open_at_utc=stamp(day+'T14:30:00Z'),
        close_at_utc=stamp(day+'T21:00:00Z')) for day in ('2024-12-31','2025-01-02','2025-01-03')]


def planned():
    return audit.windows('2025-01-02T15:01:00Z',sessions())


def bars(plan=None):
    plan=plan or planned()
    return [dict(market_code='US_EQ',interval_code='5m',session_tag='regular',
        data_adjustment='raw',is_filled=0,volume=100,open=100,high=101,low=99,close=100,
        provider='alpaca',data_source='alpaca_sip',bar_timestamp=start+i*audit.FIVE,
        bar_end_timestamp=start+(i+1)*audit.FIVE)
        for start in (plan['before_start'],plan['after_start']) for i in range(6)]


def test_rth_excludes_containing_bar_and_observes_completed_window():
    plan=planned()
    assert plan['before_end']==stamp('2025-01-02T15:00:00Z')
    assert plan['after_start']==stamp('2025-01-02T15:05:00Z')
    assert plan['reaction_available_no_earlier_than']==stamp('2025-01-02T15:35:00Z')


def test_exact_boundary_and_subsecond_never_round_backward():
    exact=audit.windows('2025-01-02T15:00:00Z',sessions())
    fraction=audit.windows('2025-01-02T15:00:00.000001Z',sessions())
    assert exact['after_start']==stamp('2025-01-02T15:00:00Z')
    assert fraction['after_start']==stamp('2025-01-02T15:05:00Z')


def test_premarket_uses_previous_real_session_not_holiday():
    plan=audit.windows('2025-01-02T11:00:00Z',sessions())
    assert plan['before_end']==stamp('2024-12-31T21:00:00Z')
    assert plan['after_start']==stamp('2025-01-02T14:30:00Z')


def test_postclose_uses_next_open_and_last_completed_session():
    plan=audit.windows('2025-01-02T21:00:00Z',sessions())
    assert plan['before_end']==stamp('2025-01-02T21:00:00Z')
    assert plan['after_start']==stamp('2025-01-03T14:30:00Z')


@pytest.mark.parametrize('value', ['2025-01-02T14:45:00Z','2025-01-02T20:45:00Z'])
def test_close_to_boundary_is_reserved_not_spliced_across_days(value):
    assert audit.windows(value,sessions())['status']=='INSUFFICIENT_ROOM_WITHIN_REGULAR_SESSION'


def test_missing_time_or_calendar_never_invents_time():
    assert audit.windows(None,sessions())['status']=='UNQUALIFIED_PUBLICATION_TIME'
    assert audit.windows('2025-01-02T15:00:00Z',[])['status']=='NEXT_SESSION_UNAVAILABLE'
    with pytest.raises(ValueError):
        audit.windows('2025-01-02',sessions())


def test_full_window_single_source_not_pit_or_issuer_proof():
    result=audit.assess(planned(),bars(),stamp('2025-01-03T00:00:00Z'))
    assert result['status']=='COMPLETE_SINGLE_SOURCE_WINDOW'
    assert not result['sources'][0]['historical_availability_certified']


def test_no_future_window_or_missing_bar_fill():
    assert audit.assess(planned(),bars(),stamp('2025-01-02T15:34:59Z'))['status']=='WINDOW_NOT_YET_COMPLETE'
    assert audit.assess(planned(),bars()[:-1],stamp('2025-01-03T00:00:00Z'))['status']=='MISSING_OR_INVALID_INTRADAY_WINDOW'


def test_iex_sip_and_providers_never_join_to_complete_one_window():
    rows=bars()
    for row in rows[6:]:
        row['data_source']='alpaca_iex'
    assert not any(r['complete'] for r in audit.assess(planned(),rows,stamp('2025-01-03T00:00:00Z'))['sources'])
    for row in rows[6:]:
        row['data_source']='alpaca_sip'
        row['provider']='other'
    assert not any(r['complete'] for r in audit.assess(planned(),rows,stamp('2025-01-03T00:00:00Z'))['sources'])


@pytest.mark.parametrize('change',[
    {'volume':0},{'is_filled':1},{'data_adjustment':'split'}, {'open':float('nan')},
    {'market_code':'FR_EQ'},{'high':99},{'bar_end_timestamp':stamp('2025-01-02T23:00:00Z')},
    {'session_tag':'pre_market'},{'interval_code':'1m'}])
def test_invalid_bar_does_not_complete_window(change):
    rows=bars(); rows[0].update(change)
    assert audit.assess(planned(),rows,stamp('2025-01-03T00:00:00Z'))['status']=='MISSING_OR_INVALID_INTRADAY_WINDOW'


def test_duplicate_same_source_is_reserved():
    rows=bars(); rows.append(deepcopy(rows[0]))
    result=audit.assess(planned(),rows,stamp('2025-01-03T00:00:00Z'))
    assert result['sources'][0]['duplicate_timestamp'] and not result['sources'][0]['complete']


def test_config_and_plans_read_without_mutation_or_command_dump(tmp_path):
    path=tmp_path/'config.yaml'
    path.write_text(yaml.safe_dump({'us_pipeline':{'steps':[1,9],'steps_friday':[1,8,9]}}),encoding='utf-8')
    original=path.read_bytes()
    plan_dir=tmp_path/'plans'/'run'; plan_dir.mkdir(parents=True)
    (plan_dir/'plan.json').write_text(json.dumps({'selected_step_numbers':[1,8,9],
        'steps':[{'command':['private-value']}],'trade_date':'2025-01-03'}),encoding='utf-8')
    result=audit.collection_config(path,tmp_path/'plans')
    assert not result['news_selected_mon_thu'] and result['news_selected_friday']
    assert result['frozen_plans'][0]['news_selected']
    assert 'private-value' not in json.dumps(result)
    assert path.read_bytes()==original


def test_separate_daily_ingestion_is_not_mistaken_for_weekly_scoring(tmp_path):
    config=tmp_path/'config.yaml'
    config.write_text(yaml.safe_dump({'us_pipeline':{'steps':[1,9],'steps_friday':[1,8,9]}}),encoding='utf-8')
    batch=tmp_path/'batch.yaml'
    section=dict(enabled=True,status='ACTIVE_RESEARCH_ONLY',market_code='US_EQ',provider='eodhd',
        run_days='0,1,2,3,4,5,6',api_token='NEVER_COPY')
    batch.write_text(yaml.safe_dump({'eodhd_news_ingestion_sync':section}),encoding='utf-8')
    result=audit.collection_config(config,tmp_path/'no_plans')
    assert result['separate_daily_ingestion_configured'] and not result['news_selected_mon_thu']
    assert not result['daily_sentiment_scoring_demonstrated'] and 'NEVER_COPY' not in str(result)
    section['enabled']=False
    batch.write_text(yaml.safe_dump({'eodhd_news_ingestion_sync':section}),encoding='utf-8')
    assert not audit.collection_config(config,tmp_path/'no_plans')['separate_daily_ingestion_configured']


def test_changed_or_unbound_evidence_is_refused(tmp_path):
    audit.evidence.save(tmp_path/'protocol.json',{'cutoff_utc':'2025-01-03T00:00:00Z'})
    audit.evidence.save(tmp_path/'evidence.json',[{'evidence_key':'known'}])
    audit.evidence.save(tmp_path/'technical_review_filled.json',[])
    audit.evidence.save(tmp_path/'report.json',{'files':{
        name:audit.evidence.sha(tmp_path/name) for name in ('protocol.json','evidence.json')}})
    result=dict(report_sha256=audit.evidence.sha(tmp_path/'report.json'),
        review_sha256=audit.evidence.sha(tmp_path/'technical_review_filled.json'),results=[])
    audit.evidence.save(tmp_path/'technical_review_result.json',result)
    assert audit.read_pack(tmp_path)[2]==[{'evidence_key':'known'}]
    (tmp_path/'technical_review_filled.json').write_text('[{}]',encoding='utf-8')
    with pytest.raises(ValueError,match='Review does not bind'):
        audit.read_pack(tmp_path)
    (tmp_path/'evidence.json').write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError,match='Changed evidence'):
        audit.read_pack(tmp_path)


def test_half_day_window_stops_at_actual_calendar_close():
    half=[SimpleNamespace(is_open=True,open_at_utc=stamp('2025-11-28T14:30:00Z'),
        close_at_utc=stamp('2025-11-28T18:00:00Z'))]
    assert audit.windows('2025-11-28T17:45:00Z',half)['status']=='INSUFFICIENT_ROOM_WITHIN_REGULAR_SESSION'
