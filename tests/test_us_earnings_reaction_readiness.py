import copy
import pandas as pd
import pytest

from scripts.research import us_earnings_reaction_readiness as s


def facts():
    out={}
    for tag,unit,vals in [('Revenues','USD',(120,100)),('OperatingIncomeLoss','USD',(18,10)),('EarningsPerShareDiluted','USD/shares',(2,1))]:
        entries=[]
        for year,value in zip((2024,2023),vals):
            entries.append(dict(start=f'{year}-04-01',end=f'{year}-06-30',val=value,
                accn='0000000001-24-000001',fy=2024,fp='Q2',form='10-Q',filed='2024-08-01'))
        out[tag]=dict(units={unit:entries})
    return dict(facts={'us-gaap':out})


def test_same_accession_comparative_dates_not_filing_fy_fp_keys():
    rows,_=s.facts_events(facts(),cutoff='2024-09-01')
    assert len(rows)==1
    r=rows[0];assert r['numeric_ready'] and r['accounting_pattern']=='LONG'
    assert r['revenue_growth']==pytest.approx(.2)
    assert r['operating_margin_change']==pytest.approx(.05)
    assert not r['first_publication_proven'] and not r['original_document_verified']


@pytest.mark.parametrize('mode',['annual','ytd','amendment','later','no_accession','nonfinite'])
def test_bad_quarter_facts_excluded(mode):
    e=facts()['facts']['us-gaap']['Revenues']['units']['USD'][0]
    if mode=='annual':e['start']='2023-07-01'
    if mode=='ytd':e['start']='2024-01-01'
    if mode=='amendment':e['form']='10-Q/A'
    if mode=='later':e['filed']='2024-06-01'
    if mode=='no_accession':e['accn']=''
    if mode=='nonfinite':e['val']=float('nan')
    assert not s.quarter_fact(e)


def test_no_future_filing_or_current_fact_projected_backwards():
    rows,_=s.facts_events(facts(),cutoff='2024-07-31');assert rows==[]


@pytest.mark.parametrize('field,value',[('accn','different'),('unit','EUR'),('tag','SalesRevenueNet'),('start','2023-01-01')])
def test_no_unverified_cross_basis_comparative(field,value):
    x=dict(facts()['facts']['us-gaap']['Revenues']['units']['USD'][0],unit='USD',tag='Revenues')
    y=dict(facts()['facts']['us-gaap']['Revenues']['units']['USD'][1],unit='USD',tag='Revenues')
    assert s.same_quarter_prior(x,y)
    y[field]=value;assert not s.same_quarter_prior(x,y)


def test_conflicting_tag_values_never_cherry_picked():
    f=facts();f['facts']['us-gaap']['SalesRevenueNet']=copy.deepcopy(f['facts']['us-gaap']['Revenues'])
    f['facts']['us-gaap']['SalesRevenueNet']['units']['USD'][0]['val']=200
    r=s.facts_events(f,cutoff='2024-09-01')[0][0]
    assert not r['numeric_ready'] and r['accounting_pattern']=='ABSTAIN'
    assert 'REVENUE_TAG_CONFLICT' in r['technical_reasons']


def test_different_currency_not_assumed_usd():
    f=facts();f['facts']['us-gaap']['Revenues']['units']['EUR']=f['facts']['us-gaap']['Revenues']['units'].pop('USD')
    r=s.facts_events(f,cutoff='2024-09-01')[0][0]
    assert not r['numeric_ready']


def test_missing_operating_income_not_zero_or_eps_fallback():
    f=facts();del f['facts']['us-gaap']['OperatingIncomeLoss']
    r=s.facts_events(f,cutoff='2024-09-01')[0][0]
    assert not r['numeric_ready'] and r['accounting_pattern']=='ABSTAIN'


def test_conflicting_comparative_values_reserved():
    f=facts();rows=f['facts']['us-gaap']['Revenues']['units']['USD'];rows.append(dict(rows[1],val=99))
    r=s.facts_events(f,cutoff='2024-09-01')[0][0]
    assert not r['numeric_ready']


def test_fiscal_52_week_comparative_allowed():
    x=dict(accn='A',unit='USD',tag='Revenues',start='2024-04-01',end='2024-06-30')
    y=dict(accn='A',unit='USD',tag='Revenues',start='2023-04-03',end='2023-07-02')
    assert s.same_quarter_prior(x,y)


def test_first_full_session_strictly_after_filing_date_then_next_open():
    days=pd.DatetimeIndex(['2024-08-01','2024-08-02','2024-08-05','2024-08-06'])
    r=s.reaction_session('2024-08-02',days)
    assert r==pd.Timestamp('2024-08-05')
    assert s.reaction_session(r,days)==pd.Timestamp('2024-08-06')
    assert s.reaction_session('2024-08-06',days) is None


@pytest.mark.parametrize('values,expected', [((120,100,18,10),'LONG'),((90,100,5,10),'SHORT'),
    ((120,100,6,10),'ABSTAIN'),((0,100,18,10),'ABSTAIN'),((120,None,18,10),'ABSTAIN')])
def test_accounting_agreement_not_any_good_metric(values,expected):
    assert s.accounting_direction(*values)[0]==expected


def test_market_relative_reaction_no_forward_prices():
    value,side=s.reaction(100,105,100,106)
    assert side=='SHORT' and value==pytest.approx(-.01)
    assert s.reaction(100,None,100,106)==(None,'UNKNOWN')


def test_later_repeat_and_amendment_not_new_event():
    f=facts()
    for obj in f['facts']['us-gaap'].values():
        unit=next(iter(obj['units']));rows=obj['units'][unit]
        rows += [dict(x,accn='0000000001-24-000002',filed='2024-08-09') for x in rows.copy()]
    rows,stats=s.facts_events(f,cutoff='2024-09-01')
    assert len(rows)==1 and rows[0]['filed']==pd.Timestamp('2024-08-01')
    assert stats['REPEATED_TARGET_PERIOD_RESERVED']==1
