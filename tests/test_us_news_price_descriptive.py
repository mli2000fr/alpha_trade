from copy import deepcopy
from datetime import datetime,timedelta,timezone
from types import SimpleNamespace
import pytest

from scripts.research import us_news_price_descriptive_20261016 as pilot
from scripts.research import us_news_price_descriptive_readout_20261016 as readout


def ts(s):
    return datetime.fromisoformat(s.replace('Z','+00:00'))


def plan():
    sessions=[SimpleNamespace(is_open=True,open_at_utc=ts(day+'T13:30:00Z'),
        close_at_utc=ts(day+'T20:00:00Z')) for day in ('2026-10-13','2026-10-14','2026-10-15')]
    return pilot.windows('2026-10-14T15:01:00Z',sessions)


def bars():
    p=plan()
    rows=[dict(symbol='XYZ',market_code='US_EQ',interval_code='5m',session_tag='regular',
        data_adjustment='raw',is_filled=0,volume=100,open=100 if phase==0 else 104,
        high=106,low=99,close=100 if phase==0 else 104,
        provider='alpaca',data_source='alpaca_sip',bar_timestamp=start+i*pilot.FIVE,
        bar_end_timestamp=start+(i+1)*pilot.FIVE,observed_at=ts('2026-10-16T12:00:00Z'))
        for phase,start in enumerate((p['before_start'],p['after_start'])) for i in range(6)]
    rows[5]['close']=102
    rows[-1]['close']=106
    return rows


def test_returns_keep_pre_post_and_gap_distinct():
    result=pilot.reaction(plan(),bars(),ts('2026-10-16T13:00:00Z'))
    m=result['metrics']
    assert m['before_30m_pct']==pytest.approx(2)
    assert m['after_30m_pct']==pytest.approx(100*(106/104-1))
    assert m['gap_pct']==pytest.approx(100*(104/102-1))
    assert m['bridge_pct']==pytest.approx(100*(106/102-1))
    assert (1+m['gap_pct']/100)*(1+m['after_30m_pct']/100)==pytest.approx(1+m['bridge_pct']/100)
    assert m['calculation_not_profit'] and not m['historical_bar_availability_certified']


@pytest.mark.parametrize('mutation',[
    {'data_source':'alpaca_iex'}, {'provider':'other'}, {'volume':0}, {'is_filled':1},
    {'observed_at':None}, {'observed_at':ts('2026-10-17T00:00:00Z')}, {'data_adjustment':'split'},
])
def test_missing_invalid_future_or_other_feed_bar_never_completes_window(mutation):
    rows=bars(); rows[0].update(mutation)
    assert pilot.reaction(plan(),rows,ts('2026-10-16T13:00:00Z'))['metrics'] is None


def test_duplicate_or_unfinished_window_refused():
    rows=bars(); rows.append(deepcopy(rows[0]))
    assert pilot.reaction(plan(),rows,ts('2026-10-16T13:00:00Z'))['metrics'] is None
    assert pilot.reaction(plan(),bars(),plan()['after_end']-timedelta(seconds=1))['metrics'] is None


def test_cohort_uses_identity_and_fixed_quotes_not_returns_or_control_label():
    now=ts('2026-10-16T13:00:00Z')
    item=dict(evidence_key='a',article_id='one',symbol='XYZ',text_hash='hash',
        fields={'content':'A favourable opinion.'},screened=False,temporal_reservations=[])
    reviews=[dict(evidence_key='a',identity_verified=True)]
    labels={'one':['POSITIVE','content','favourable opinion','Explicit reading']}
    rows,excluded=pilot.select_cohort([item],reviews,labels,now)
    assert rows[0]['tone']=='POSITIVE' and rows[0]['legacy_keyword_control']
    assert rows[0]['tone_available_at']==now and not excluded
    assert pilot.select_cohort([item],[dict(evidence_key='a',identity_verified=False)],{},now)[0]==[]
    assert pilot.select_cohort([dict(item,symbol='MSCI')],reviews,{},now)[1][0]['reason']=='EXISTING_RIGHTS_RESERVATION'
    with pytest.raises(ValueError,match='Exact tone quotation'):
        pilot.select_cohort([item],reviews,{'one':['NEGATIVE','content','Invented news quote','wrong']},now)


def test_summary_keeps_controls_separate_from_tone_and_does_not_invent_empty_scores():
    m=pilot.reaction(plan(),bars(),ts('2026-10-16T13:00:00Z'))
    row=dict(anchor='publication',tone='POSITIVE',legacy_keyword_control=True,
        symbol='XYZ',publication_ny_date='2026-10-14',**m)
    s=pilot.summary([row],'publication')
    assert s['groups']['POSITIVE']['aligned_before']==1
    assert s['groups']['POSITIVE']['aligned_after']==1
    assert s['groups']['NEGATIVE']['means_pct']['after_30m_pct'] is None
    assert s['groups']['MIXED_OR_NEUTRAL']['aligned_after'] is None
    assert s['groups']['POSITIVE']['alignment_is_not_directional_accuracy']
    assert s['distinct_publication_ny_dates']==1


def test_clock_readout_is_explicitly_posthoc_and_bound_to_sealed_results(tmp_path):
    root=tmp_path/'results'; root.mkdir()
    checked=pilot.reaction(plan(),bars(),ts('2026-10-16T13:00:00Z'))
    row=dict(anchor='publication',tone='POSITIVE',legacy_keyword_control=True,
        symbol='XYZ',article_id='one',publication_ny_date='2026-10-14',plan=plan(),
        publication_window_ended_before_receipt=True,**checked)
    pilot.evidence.save(root/'cases.json',[row])
    pilot.evidence.save(root/'report.json',dict(files={'cases.json':pilot.evidence.sha(root/'cases.json')}))
    result=readout.run(tmp_path)
    assert result['clock_stratification_requested_after_initial_results'] is True
    assert result['not_validation_of_a_clock_filter'] is True
    assert result['complete_publication_windows_ended_before_receipt']==1
    assert result['groups']['publication']['regular_session']['complete_pairs']==1
    assert result['groups']['publication']['outside_regular_session']['complete_pairs']==0
