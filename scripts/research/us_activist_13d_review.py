"""Freeze reviewed13D actions and historical identity before any outcome reading."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_activist_13d_pilot import READ,prepare,Client,Stopped,normalized
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

NOTES=Path('doc/ml/sources/activist_13d_review_20261020.json')


def check_clause(obj,filename,contains):
    parts=[x for x in obj['parts'] if x['filename']==filename]
    if len(parts)!=1 or normalized(contains) not in normalized(parts[0]['text']):raise ValueError('Missing exact review clause '+filename)
    return True


def annual_before(payload,filed):
    candidates=set()
    for ns in payload.get('facts',{}).values():
        for tag in ns.values():
            for values in tag.get('units',{}).values():
                for r in values:
                    if r.get('form')=='10-K' and r.get('filed','')<filed and r.get('accn'):
                        candidates.add((r['filed'],r['accn']))
    if not candidates:return None
    day=max(x[0] for x in candidates);same=[x for x in candidates if x[0]==day]
    if len(same)!=1:raise ValueError('Ambiguous last prefiling10K')
    return dict(filed=same[0][0],accession=same[0][1],form='10-K')


def primary_name(body):
    soup=BeautifulSoup(body,'html.parser');files=[]
    for tr in soup.find_all('tr'):
        cols=tr.find_all('td')
        if len(cols)>=4 and cols[3].get_text(strip=True)=='10-K':
            a=cols[2].find('a')
            if a and re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',a.get_text(strip=True)):files.append(a.get_text(strip=True))
    if len(set(files))!=1:raise ValueError('Original10K primary absent or ambiguous')
    return files[0]


def identity(body,cik,symbol):
    soup=BeautifulSoup(body,'html.parser')
    ids={x.get_text(strip=True).zfill(10) for x in soup.find_all(lambda n:n.name.lower().split(':')[-1]=='identifier')}
    nodes=soup.find_all(lambda n:n.name.lower()=='ix:nonnumeric' and n.get('name','').split(':')[-1]=='TradingSymbol' and n.get_text(strip=True)==symbol)
    if cik not in ids or not nodes:return None
    return dict(cik=cik,symbol=symbol,cover_rows=sorted(set(normalized(n.find_parent('tr').get_text(' ',strip=True)) for n in nodes if n.find_parent('tr'))))


def freeze(root):
    p=prepare(root);ext=READ(root/'extraction.json');verify_hashes(root,ext['files']);notes=READ(NOTES)
    out=root/'review-v1'
    if (out/'protocol.json').exists():
        review=READ(out/'protocol.json');verify_hashes(Path('.'),review['sources']);return out,review
    if out.exists():raise ValueError('Fresh reviewed cohort required')
    ready={r['accession']:r for r in ext['rows'] if r['status']=='READY_REVIEW'}
    if set(ready)!={r['accession'] for r in notes['cases']}:raise ValueError('Must review every issuer-confirmed initial')
    rows=[];sources=[Path(__file__),Path('tests/test_us_activist_13d_review.py'),NOTES,root/'protocol.json',root/'extraction.json',root/'documents.json']
    calendar=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2024-09-30')
    for note in notes['cases']:
        r=ready[note['accession']];obj=READ(root/r['review_file'])
        if note['symbol'] not in r['index_symbols']:raise ValueError('Current identity mismatch')
        check_clause(obj,note['filename'],note['contains'])
        if note.get('action_contains'):check_clause(obj,note['filename'],note['action_contains'])
        if note.get('identity_contains'):check_clause(obj,note['identity_filename'],note['identity_contains'])
        entry=calendar[calendar.index>pd.Timestamp(r['filed'])].index[0]
        # Verify acceptance too; end-of-filing-date convention is still later.
        if r['accepted_utc'] and pd.Timestamp(r['accepted_utc'])>=calendar.loc[entry].market_open:raise ValueError('Acceptance later than conservative entry')
        row=dict(**note,filed=r['filed'],cik=r['cik'],entry=str(entry.date()),review_file=r['review_file'],
            identity_status='ORIGINAL_13D_TICKER_SUPPORT' if note.get('identity_contains') else 'UNKNOWN',
            active=note['decision']=='PRIMARY_EXPLICIT_INTERVENTION',secondary=note['decision']=='SECONDARY_GOVERNANCE_ONLY',
            admitted=False,admission_reason='NOT_PRIMARY_OR_GOVERNANCE' if not (note['decision']=='PRIMARY_EXPLICIT_INTERVENTION' or note['decision']=='SECONDARY_GOVERNANCE_ONLY') else 'PENDING')
        if note.get('identity_requires_prefiling_10k'):
            facts=Path(f'artifacts/sec_cache/companyfacts/CIK{r["cik"]}.json')
            if facts.exists():
                sources.append(facts);row['annual_metadata']=annual_before(READ(facts),r['filed'])
        rows.append(row)
    # Shared issuer block; cannot skip a first event due to later price data.
    next_entry={}
    sessions=calendar.index
    for row in sorted(rows,key=lambda r:(r['filed'],r['accession'])):
        if not(row['active'] or row['secondary']):continue
        j=sessions.get_loc(pd.Timestamp(row['entry']))
        if j<next_entry.get(row['symbol'],-1):row['admission_reason']='ISSUER_60SESSION_BLOCK';continue
        row['admitted']=True;row['admission_reason']='EARLIEST_ELIGIBLE_ISSUER';next_entry[row['symbol']]=j+60
    out.mkdir()
    report=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in sources},rows=rows,
        parent=str(root),all_originals_reviewed=len(ready),filer_not_subject_reserved=sum(r['status']=='RESERVED' for r in ext['rows']),
        freeze_before_price_outcomes=True,same_assistant_not_human_independent=True,
        primary_nonoverlap=sum(r['active'] and r['admitted'] for r in rows),secondary_nonoverlap=sum(r['secondary'] and r['admitted'] for r in rows))
    atomic_json(out/'protocol.json',report);print('Frozen primary',report['primary_nonoverlap'],'secondary',report['secondary_nonoverlap'],flush=True)
    return out,report


def capture_identity(root):
    out,review=freeze(root);p=prepare(root)
    if (out/'identity-capture.json').exists():raise ValueError('Immutable historical identity capture')
    client=Client(root,p['limits']);rows=[];stop=None
    try:
        for row in review['rows']:
            if not row['admitted'] or not row.get('identity_requires_prefiling_10k'):continue
            annual=row.get('annual_metadata');item=dict(symbol=row['symbol'],accession=row['accession'],identity=None)
            if annual:
                base=f'https://www.sec.gov/Archives/edgar/data/{int(row["cik"])}/{annual["accession"].replace("-","")}/'
                body,meta=client.get(base+annual['accession']+'-index.html');item['index_receipt']=meta
                if body:
                    name=primary_name(body);body,receipt=client.get(base+name);item['receipt']=receipt
                    if body:item['identity']=identity(body,row['cik'],row['symbol'])
            rows.append(item);print('Historical identity',row['symbol'],bool(item['identity']),flush=True)
    except (Stopped,ValueError) as exc:stop=str(exc)
    finally:client.client.close()
    atomic_json(out/'identity-capture.json',dict(rows=rows,stop=stop,requests=client.calls,streamed_bytes=client.bytes,
        files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--phase',choices=['freeze','capture_identity'],required=True);args=a.parse_args()
    globals()[args.phase](args.output)
