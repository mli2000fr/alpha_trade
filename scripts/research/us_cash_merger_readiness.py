"""Cash-merger lifecycle evidence and price QUALITY ONLY. Never calculates return."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import re

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_cash_merger_completion import READ,prepare,freeze_cohort,normalized
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

REVIEW=Path('doc/ml/sources/cash_merger_lifecycle_review_20261020.json')


def no_future_completion(clause):
    if re.search(r'\b(expect\w*|anticipat\w*|will|plan\w*)\b',clause,re.I):
        raise ValueError('Expected future closing is not observed completion')


def validate_events(root):
    prepare(root);cohort=freeze_cohort(root);life=READ(root/'lifecycle.json');parsed=READ(root/'lifecycle-extract.json')
    verify_hashes(root,life['files']);verify_hashes(root,parsed['files']);review=READ(REVIEW)
    if life['status']!='COMPLETE_CAPTURE' or not all(c['bound_pass'] for c in life['cases']):raise ValueError('Incomplete lifecycle population')
    docs={r['index']['accession']:r for r in parsed['documents']}
    if set(docs)!=set(review['document_review']):raise ValueError('Every selected lifecycle document must be reviewed')
    eligible={r['symbol']:r for r in cohort['rows'] if r['eligible']}
    if {r['symbol'] for r in review['outcomes']}!=set(eligible):raise ValueError('No eligible case may be omitted for outcome')
    for case in life['cases']:
        numbers=[]
        for r in case['candidates']:
            d=docs[r['accession']]
            if d.get('status')!='READY_MANUAL_REVIEW':raise ValueError('Unreadable lifecycle filing')
            obj=READ(root/d['review_file']);head=obj['header']
            if r['form']=='SC TO-T/A':
                head=re.search(r'SUBJECT COMPANY:(.*?)(?=FILED BY:|</SEC-HEADER>)',head,re.S).group(1)
            cik=re.search(r'CENTRAL INDEX KEY:\s*(\d+)',head).group(1).zfill(10)
            if cik!=case['case']['target_cik']:raise ValueError('Wrong target in lifecycle')
            if r['form']=='SC TO-T/A':
                primary=next(p for p in obj['parts'] if p['type']=='SC TO-T/A')
                m=re.search(r'Amendment No\.?\s+(\d+)',primary['text'],re.I)
                if not m:raise ValueError('Missing amendment sequence')
                numbers.append(int(m.group(1)))
        if sorted(numbers)!=list(range(1,max(numbers)+1)):raise ValueError('Missing numbered amendment')
    result=[]
    for r in review['outcomes']:
        e=eligible[r['symbol']];proofs=[]
        no_future_completion(r['evidence']['contains'])
        for field in ['evidence','cash_evidence']:
            proof=r[field];item=docs[proof['accession']];obj=READ(root/item['review_file'])
            part=next((p for p in obj['parts'] if p['filename']==proof['filename']),None)
            if not part or normalized(proof['contains']) not in normalized(part['text']):raise ValueError(f'Unsupported event clause {r["symbol"]}')
            proofs.append(dict(**proof,original_url=item['receipt']['url'],original_sha256=item['receipt']['sha256'],
                observed_at_utc=item['receipt']['retrieved_at_utc']))
        if r['final_cash_usd']!=e['offer_cash_usd']:raise ValueError('Final price change requires explicit lifecycle contract')
        result.append(dict(symbol=r['symbol'],target_cik=e['target_cik'],initial_filed=e['initial_filed'],
            state='COMPLETED_LEGAL_CASH_RIGHT_NOT_BROKER_CREDIT',completed_on=r['completed_on'],cash_per_share_usd=r['final_cash_usd'],
            broker_cash_credit_date=None,broker_cash_credit_qualified=False,proofs=proofs,reserve=r.get('reserve'),
            original_local_historical_receipt_proven=False))
    return result


def prepare_readiness(root):
    out=root/'readiness-v1';events=validate_events(root)
    if (out/'protocol.json').exists():
        p=READ(out/'protocol.json');verify_hashes(Path('.'),p['sources']);return out,p
    if out.exists():raise ValueError('Fresh immutable readiness output required')
    out.mkdir()
    sources=[Path(__file__),Path('tests/test_us_cash_merger_readiness.py'),REVIEW,root/'cohort.json',root/'lifecycle.json',root/'lifecycle-extract.json']
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in sources},events=events,
        source_scope='All5term-admissible cases retained. Three AlpacaGET: SIP raw/split daily and all corporateactions; fixed2024Jan1-May31bars,Jan1-Jun30actions. No price-based admission or return evaluation.',
        quality='Calendar/OHLCV/rawsplit agreement/identity corroboration only. No gain, trade performance, spread-to-offer selection, training, SQL or orders.',
        limits=dict(requests=3,response_bytes=12*1024*1024),
        cash='Legal right at closing known; broker spendable date UNKNOWN, never expiry/asof/process_date/T+2 imputed.',
        no_performance=True,no_sql_writes=True,no_orders=True)
    atomic_json(out/'protocol.json',p);return out,p


def fetch(root):
    from common.public_data_http import verified_session
    from service.alpaca.clientAlpaca import _build_headers
    out,p=prepare_readiness(root)
    if (out/'download.json').exists():raise ValueError('Immutable data capture')
    symbols=','.join(e['symbol'] for e in p['events']);calls=[]
    queries=[('raw','/v2/stocks/bars',dict(symbols=symbols,start='2024-01-01T00:00:00Z',end='2024-05-31T23:59:59Z',
        timeframe='1Day',feed='sip',adjustment='raw',asof='-',sort='asc',limit=10000)),
        ('split','/v2/stocks/bars',dict(symbols=symbols,start='2024-01-01T00:00:00Z',end='2024-05-31T23:59:59Z',
        timeframe='1Day',feed='sip',adjustment='split',asof='-',sort='asc',limit=10000)),
        ('actions','/v1/corporate-actions',dict(symbols=symbols,start='2024-01-01',end='2024-06-30',data_quality='all',limit=1000,sort='asc'))]
    with verified_session() as session:
        for name,endpoint,params in queries:
            file=out/f'{name}.json'
            if file.exists():continue
            response=session.get('https://data.alpaca.markets'+endpoint,params=params,headers=_build_headers('default'),timeout=(10,35))
            if len(response.content)>p['limits']['response_bytes']:raise ValueError('Response size limit')
            value=dict(endpoint=endpoint,params=params,status_code=response.status_code,
                observed_at_utc=datetime.now(timezone.utc).isoformat(),payload=response.json() if response.status_code==200 else None)
            atomic_json(file,value);calls.append(name);print('Price readiness',name,'HTTP',response.status_code,flush=True)
            if response.status_code in [403,429]:break
    atomic_json(out/'download.json',dict(new_requests=len(calls),files={f.name:digest(f) for f in out.glob('*.json') if f.name!='protocol.json'}))


def validate_bar_values(rows):
    if not rows:return ['NO_BARS']
    frame=pd.DataFrame(rows);values=frame[['o','h','l','c','v']].to_numpy(dtype=float)
    issues=[]
    if not np.isfinite(values).all() or (values<=0).any():issues.append('NONPOSITIVE_OR_NONFINITE_OHLCV')
    if ((frame.l>frame[['o','c','h']].min(axis=1)+1e-8)|(frame.h<frame[['o','c','l']].max(axis=1)-1e-8)).any():issues.append('INCONSISTENT_OHLC')
    dates=[str(pd.Timestamp(r['t']).tz_convert('America/New_York').date()) for r in rows]
    if len(dates)!=len(set(dates)):issues.append('DUPLICATE_DATES')
    return issues


def build(root):
    out,p=prepare_readiness(root)
    if (out/'report.json').exists():raise ValueError('Immutable readiness report')
    verify_hashes(out,READ(out/'download.json')['files']);series={}
    for name in ['raw','split','actions']:
        f=out/f'{name}.json'
        if not f.exists():raise ValueError('Missing data response')
        receipt=READ(f)
        if receipt['status_code']!=200 or receipt['payload'].get('next_page_token'):raise ValueError('Incomplete data response')
        series[name]=receipt['payload']
    results=[];calendar=mcal.get_calendar('NYSE')
    for e in p['events']:
        s=e['symbol'];raw=series['raw'].get('bars',{}).get(s,[]);split=series['split'].get('bars',{}).get(s,[])
        problems=validate_bar_values(raw);day=lambda r:str(pd.Timestamp(r['t']).tz_convert('America/New_York').date())
        dates={day(r) for r in raw}
        first=calendar.valid_days(start_date=(pd.Timestamp(e['initial_filed'])+pd.Timedelta(days=1)).date(),end_date='2024-05-31')[0].date()
        end=(pd.Timestamp(e['completed_on'])-pd.Timedelta(days=1)).date()
        expected={str(d.date()) for d in calendar.valid_days(start_date=first,end_date=end)}
        missing=sorted(expected-dates);after=sorted(d for d in dates if d>=e['completed_on'])
        a={r['t']:[r[c] for c in ['o','h','l','c']] for r in raw};b={r['t']:[r[c] for c in ['o','h','l','c']] for r in split}
        same=(set(a)==set(b) and all(np.allclose(a[t],b[t],rtol=0,atol=1e-8) for t in a))
        if not same:problems.append('RAW_SPLIT_DIFFER_OR_KEYS_MISSING')
        if missing:problems.append('MISSING_REQUIRED_PRE_CLOSING_SESSIONS')
        if after:problems.append('BARS_AT_OR_AFTER_LEGAL_CLOSING_REQUIRE_QUALIFICATION')
        results.append(dict(**e,first_conservative_session=str(first),last_required_session=str(end),
            required_sessions=len(expected),present_required=len(expected&dates),missing_dates=missing,
            raw_rows=len(raw),raw_split_identical=same,after_closing_dates=after,price_quality_issues=problems,
            complete_pre_closing_calendar=not missing,production_identity_certified=False))
    report=dict(status='COHORT_AND_LEGAL_LIFECYCLE_DOCUMENTED_NOT_PORTFOLIO_PNL_READY',initials=13,
        terms_eligible=5,excluded=8,outcome_counts=dict(COMPLETED=5,TERMINATED=0,UNRESOLVED=0),
        note='Five closed deals in frozen eligible subset, NOT five winning trades or evidence that merger failure risk is absent.',
        rows=results,corporate_action_payload=series['actions'].get('corporate_actions',{}),
        exact_broker_cash_dates_qualified=0,no_price_return_or_pnl_calculated=True,no_sql_writes=True,no_orders=True,
        files={f.name:digest(f) for f in out.glob('*') if f.is_file()})
    atomic_json(out/'report.json',report);print(report['status'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--phase',choices=['prepare','fetch','build'],required=True);a=p.parse_args()
    if a.phase=='prepare':prepare_readiness(a.root)
    else:globals()[a.phase](a.root)
