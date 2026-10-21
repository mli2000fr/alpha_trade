"""Frozen semantic/identity review and adjusted-mark replay for 2025/2026.

LONG only, original 20/60 session horizons/costs. Mature and immature outcomes
are distinct. No SQL, training, LLM, broker, production or fresh price calls.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import re

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_activist_13d_confirmation import prepare,Client
from scripts.research.us_activist_13d_extension import parse_quarter
from scripts.research.us_activist_13d_extension_review import block_issuers
from scripts.research.us_activist_13d_pilot import READ,Stopped
from scripts.research.us_activist_13d_review import check_clause,identity
from scripts.research.us_activist_13d_replay import PRICE,SCORES,price_path,marks
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

NOTES=Path('doc/ml/sources/activist_13d_confirmation_review_20261020.json')
ANNUALS={'10-K','20-F','40-F'}


def annual_before(payload,filed):
    candidates=set()
    for namespace in payload.get('facts',{}).values():
        for tag in namespace.values():
            for values in tag.get('units',{}).values():
                for row in values:
                    if row.get('form') in ANNUALS and row.get('filed','')<filed and row.get('accn'):
                        candidates.add((row['filed'],row['accn'],row['form']))
    if not candidates:
        return None
    day=max(x[0] for x in candidates);latest=[x for x in candidates if x[0]==day]
    if len(latest)!=1:
        raise ValueError('Ambiguous earlier annual metadata')
    day,accession,form=latest[0]
    return dict(filed=day,accession=accession,form=form)


def primary_name(body,form):
    soup=BeautifulSoup(body,'html.parser');names=[]
    for tr in soup.find_all('tr'):
        cols=tr.find_all('td')
        if len(cols)>=4 and cols[3].get_text(strip=True)==form:
            link=cols[2].find('a')
            if link and re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',link.get_text(strip=True)):
                names.append(link.get_text(strip=True))
    if len(set(names))!=1:
        raise ValueError('Original annual primary HTML ambiguous/absent')
    return names[0]


def indexed_annual_before(rows,cik,filed):
    candidates={(r['filed'],r['accession'],r['form']) for r in rows
                if r['cik']==cik and r['form'] in ANNUALS and r['filed']<filed}
    if not candidates:
        return None
    day=max(x[0] for x in candidates);latest=[x for x in candidates if x[0]==day]
    if len(latest)!=1:
        raise ValueError('Ambiguous prefiling annual index metadata')
    day,accession,form=latest[0]
    return dict(filed=day,accession=accession,form=form)


def full_calendar():
    return mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2026-12-31')


def maturity(entry,horizon,sessions,cutoff):
    entry=pd.Timestamp(entry);cutoff=pd.Timestamp(cutoff)
    if entry not in sessions:
        return False,None,'ENTRY_NOT_IN_CALENDAR'
    i=sessions.get_loc(entry)
    if i+horizon>len(sessions):
        return False,None,'CALENDAR_TOO_SHORT'
    last=sessions[i+horizon-1]
    return last<=cutoff,str(last.date()),'MATURE' if last<=cutoff else 'IMMATURE_HORIZON'


def freeze(root):
    p=prepare(root);out=root/'review-frozen-v1'
    if (out/'protocol.json').exists():
        result=READ(out/'protocol.json');verify_hashes(Path('.'),result['sources']);return out,result
    if out.exists():
        raise ValueError('Fresh semantic freeze required')
    ext=READ(root/'extraction.json');verify_hashes(root,ext['files'])
    docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    if docs['status']!='COMPLETE_ATTEMPTS':
        raise ValueError('Source denominator incomplete; cannot claim complete tests')
    notes=READ(NOTES);byid={r['accession']:r for r in notes['cases']}
    if len(byid)!=len(notes['cases']) or set(byid)!={r['accession'] for r in ext['rows']}:
        raise ValueError('One reviewed/reserved decision required for EVERY selected accession')
    calendar=full_calendar();rows=[]
    annual_index=[]
    for index in READ(root/'selection.json')['indexes']:
        if index['status']=='OK':
            receipt=index['receipt'];path=root/receipt['file']
            if digest(path)!=receipt['sha256']:
                raise ValueError('Annual metadata index changed')
            annual_index.extend(r for r in parse_quarter(path.read_bytes(),index['year'],index['quarter']) if r['form'] in ANNUALS)
    files=[Path(__file__),Path('tests/test_us_activist_13d_confirmation_replay.py'),NOTES,
           root/'protocol.json',root/'selection.json',root/'extraction.json',root/'documents.json']
    for r in ext['rows']:
        note=byid[r['accession']];eligible=note['decision'] in ['PRIMARY_EXPLICIT_INTERVENTION','SECONDARY_GOVERNANCE_ONLY']
        obj=READ(root/r['review_file']) if r['status']=='READY_REVIEW' else None
        if obj:
            if note.get('subject_cik')!=obj['subject_cik']:
                raise ValueError('Wrong SUBJECT issuer')
            for clause in note.get('clauses',[]):
                check_clause(obj,clause['filename'],clause['contains'])
            if note['decision']=='EXCLUDE_TARGET_OUTSIDE_MAIN_COHORT':
                if r['cohort']!='CURRENT_UNIVERSE_INDEX_ROUTE' or r['current_tradable_symbols']:
                    raise ValueError('Cannot hide main/probe issuer')
            elif not note.get('clauses'):
                raise ValueError('Source-supported exact clause required')
        elif not note['decision'].startswith('RESERVED_'):
            raise ValueError('Unavailable source must remain RESERVED')
        entry=calendar[calendar.index>pd.Timestamp(r['filed'])].index[0]
        if eligible and (not obj or not obj.get('accepted_utc') or pd.Timestamp(obj['accepted_utc'])>=calendar.loc[entry].market_open):
            raise ValueError('No full session after SEC acceptance')
        row=dict(**note,event_year=r['event_year'],quarter=r['quarter'],cohort=r['cohort'],filed=r['filed'],
                 cik=obj['subject_cik'] if obj else None,subject_name=obj['subject_name'] if obj else None,
                 entry=str(entry.date()),accepted_utc=obj.get('accepted_utc') if obj else None,
                 active=note['decision']=='PRIMARY_EXPLICIT_INTERVENTION')
        if eligible:
            if not note.get('symbol') or not note.get('clauses'):
                raise ValueError('Historical symbol candidate/action proof required')
            if note.get('identity_clause'):
                c=note['identity_clause'];check_clause(obj,c['filename'],c['contains'])
                row['identity_status']='ORIGINAL_13D_TICKER_SUPPORT'
            else:
                row['identity_status']='UNKNOWN'
                fact=Path(f'artifacts/sec_cache/companyfacts/CIK{row["cik"]}.json')
                if fact.exists():
                    files.append(fact);row['annual_metadata']=annual_before(READ(fact),row['filed'])
                indexed=indexed_annual_before(annual_index,row['cik'],row['filed'])
                if indexed and (not row.get('annual_metadata') or indexed['filed']>row['annual_metadata']['filed']):
                    row['annual_metadata']=indexed;row['annual_metadata_source']='ARCHIVED_OFFICIAL_QUARTER_INDEX'
        rows.append(row)
    rows=block_issuers(rows,calendar.index)
    out.mkdir()
    result=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in set(files)},
                rows=rows,decisions=dict(Counter(r['decision'] for r in rows)),economic=p['economic'],price_end=p['price_end'],
                freeze_before_2025_2026_returns=True,same_assistant_not_independent_human_review=True,
                admitted_primary_by_year={str(y):sum(r['active'] and r['admitted'] and r['event_year']==y for r in rows) for y in [2025,2026]})
    atomic_json(out/'protocol.json',result)
    print('Frozen',len(rows),'decisions; primary',result['admitted_primary_by_year'],flush=True)
    return out,result


def capture_identity(root):
    out,review=freeze(root)
    if (out/'identity-capture.json').exists():
        raise ValueError('Immutable identity capture')
    client=Client(root,prepare(root)['limits']);rows=[];stop=None
    try:
        for r in review['rows']:
            if not r['admitted']:
                continue
            item=dict(accession=r['accession'],symbol=r['symbol'],identity=None)
            if r['identity_status']=='ORIGINAL_13D_TICKER_SUPPORT':
                item['identity']=r['identity_clause'];item['status']='ORIGINAL_13D'
            elif r.get('annual_metadata'):
                a=r['annual_metadata'];base=f'https://www.sec.gov/Archives/edgar/data/{int(r["cik"])}/{a["accession"].replace("-","")}/'
                body,receipt=client.get(base+a['accession']+'-index.html');item['index_receipt']=receipt
                if body:
                    try:
                        name=primary_name(body,a['form']);body,receipt=client.get(base+name);item['receipt']=receipt
                        if body:
                            item['identity']=identity(body,r['cik'],r['symbol'])
                    except ValueError as exc:
                        item['reason']=str(exc)
                item['status']='PREFILING_ANNUAL_CONFIRMED' if item['identity'] else 'UNKNOWN'
            else:
                item['status']='UNKNOWN_NO_EARLIER_ANNUAL_METADATA'
            rows.append(item);print('identity',r['event_year'],r['symbol'],item['status'],flush=True)
    except Stopped as exc:
        stop=str(exc)
    finally:
        client.session.close()
    atomic_json(out/'identity-capture.json',dict(rows=rows,stop=stop,requests=client.calls,streamed_bytes=client.bytes,
                files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


def replay(root):
    reviewout,review=freeze(root);out=root/'replay-confirmation-v1'
    if out.exists():
        raise ValueError('Fresh immutable replay directory required')
    ids=READ(reviewout/'identity-capture.json');verify_hashes(root,ids['files'])
    known={r['accession']:r for r in ids['rows']};events=[r for r in review['rows'] if r['admitted']]
    files=[Path(__file__),Path('tests/test_us_activist_13d_confirmation_replay.py'),reviewout/'protocol.json',reviewout/'identity-capture.json',
           PRICE,PRICE.parent/'quality-reserves.json',SCORES/'protocol.json',SCORES/'final-audit.json']
    expected=next(v for k,v in READ(SCORES/'protocol.json')['sources'].items() if Path(k).name==PRICE.name)
    if digest(PRICE)!=expected:
        raise ValueError('Frozen research price tape changed')
    for y in [2025,2026]:
        done=SCORES/f'{y}-done.json';score=SCORES/f'{y}-H20-scores.parquet'
        if digest(score)!=READ(done)['files'][score.name]:
            raise ValueError('Frozen scores changed')
        files.extend([done,score])
    out.mkdir()
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},events=events,
                  economic=review['economic'],price_end=review['price_end'],admissions_before_price_quality=True,
                  missing_or_immature_retained=True,not_portfolio_or_live_parity=True)
    atomic_json(out/'protocol.json',protocol)
    calendar=full_calendar();symbols=sorted({r['symbol'] for r in events}|{'SPY'})
    prices=pd.read_parquet(PRICE,filters=[('symbol','in',symbols),('date','>=',pd.Timestamp('2025-01-01')),('date','<=',pd.Timestamp(review['price_end']))])
    groups={s:g for s,g in prices.groupby('symbol')};reserves=READ(PRICE.parent/'quality-reserves.json')['price_reserves']
    decisions=[calendar.index[calendar.index.get_loc(pd.Timestamp(e['entry']))-1] for e in events]
    scores=pd.concat([pd.read_parquet(SCORES/f'{y}-H20-scores.parquet',columns=['date','symbol','rank','score'],
                     filters=[('date','in',[d for d in decisions if d.year==y])]) for y in [2025,2026]],ignore_index=True)
    if scores.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate Oracle context')
    rows=[];bars=[]
    for event,decision in zip(events,decisions):
        context=scores[(scores.date==decision)&scores.symbol.eq(event['symbol'])];n=int(scores.date.eq(decision).sum())
        rank=int(context.iloc[0]['rank']) if len(context)==1 else None
        for h in protocol['economic']['horizons']:
            mature,last,why=maturity(event['entry'],h,calendar.index,protocol['price_end'])
            row=dict(accession=event['accession'],symbol=event['symbol'],cik=event['cik'],event_year=event['event_year'],
                     quarter=event['quarter'],cohort=event['cohort'],filed=event['filed'],entry=event['entry'],
                     scope='PRIMARY' if event['active'] else 'SECONDARY_GOVERNANCE',horizon=h,mature=mature,required_exit_session=last,
                     case_kind=event.get('case_kind','UNSPECIFIED'),instrument_kind=event.get('instrument_kind','COMMON_EQUITY'),
                     earlier_public_action_date=event.get('earlier_public_action_date'),new_announcement_certified=False,
                     oracle_date=str(decision.date()),oracle_rank=rank,oracle_count=n,oracle_context_status='KNOWN' if rank is not None else 'UNKNOWN',
                     in_top10=rank<=10 if rank is not None else None,in_top20pct=rank<=int(np.ceil(.2*n)) if rank is not None else None)
            if not mature:
                row.update(status='IMMATURE',reason=why);rows.append(row);continue
            if not known.get(event['accession'],{}).get('identity'):
                row.update(status='UNKNOWN',reason='HISTORICAL_TICKER_NOT_SUPPORTED');rows.append(row);continue
            paths={};problems=[]
            for s in [event['symbol'],'SPY']:
                path,reason=price_path(groups.get(s,pd.DataFrame(columns=prices.columns)),calendar.index,pd.Timestamp(event['entry']),h,reserves.get(s))
                if path is None:
                    problems.append(s+':'+reason)
                else:
                    paths[s]=path
            if problems:
                row.update(status='UNKNOWN',reason=';'.join(problems));rows.append(row);continue
            c=protocol['economic'];bps=c['spread_bps_per_leg']+c['slippage_bps_per_leg']
            stock=marks(paths[event['symbol']],c['notional_usd'],c['commission_per_order_usd'],bps)
            spy=marks(paths['SPY'],c['notional_usd'],c['commission_per_order_usd'],bps)
            stress=marks(paths[event['symbol']],c['notional_usd'],c['commission_per_order_usd'],c['stress_total_bps_per_leg'])
            row.update(status='EXPLORATORY_ADJUSTED_MARK',reason=None,**stock,benchmark_net_return=spy['net_return'],
                       excess_vs_spy=stock['net_return']-spy['net_return'],stress_net_return=stress['net_return'])
            rows.append(row)
            for s,path in paths.items():
                frame=path.reset_index(names='date');frame['symbol']=s;frame['accession']=event['accession'];frame['horizon']=h;bars.append(frame)
    frame=pd.DataFrame(rows);frame.to_csv(out/'event-results.csv',index=False)
    prices.to_parquet(out/'source-price-snapshot.parquet',index=False);scores.to_parquet(out/'oracle-context.parquet',index=False)
    if bars:
        pd.concat(bars,ignore_index=True).to_parquet(out/'audited-mark-inputs.parquet',index=False)
    summaries=[]
    for y in [2025,2026]:
        for scope in ['PRIMARY','SECONDARY_GOVERNANCE']:
            for h in [20,60]:
                selected=frame[(frame.event_year==y)&frame.scope.eq(scope)&frame.horizon.eq(h)]
                good=selected[selected.status=='EXPLORATORY_ADJUSTED_MARK']
                summaries.append(dict(year=y,scope=scope,horizon=h,admitted=len(selected),unique_issuers=selected.cik.nunique(),
                     mature=int(selected.mature.sum()),qualified=len(good),immature=int(selected.status.eq('IMMATURE').sum()),unknown=int(selected.status.eq('UNKNOWN').sum()),
                     positive_net=int(good.net_return.gt(0).sum()) if len(good) else 0,negative_net=int(good.net_return.lt(0).sum()) if len(good) else 0,
                     mean_net=float(good.net_return.mean()) if len(good) else None,median_net=float(good.net_return.median()) if len(good) else None,
                     mean_spy=float(good.benchmark_net_return.mean()) if len(good) else None,mean_excess=float(good.excess_vs_spy.mean()) if len(good) else None,
                     mean_stress=float(good.stress_net_return.mean()) if len(good) else None,
                     oracle_known=int(good.oracle_context_status.eq('KNOWN').sum()) if len(good) else 0,
                     top10=int(good.in_top10.fillna(False).sum()) if len(good) else 0,top20pct=int(good.in_top20pct.fillna(False).sum()) if len(good) else 0))
    verify_hashes(Path('.'),protocol['sources'])
    result=dict(status='EXPLORATORY_2025_2026_NOT_VALIDATED_SIGNAL',finished_at_utc=datetime.now(timezone.utc).isoformat(),
                price_end=protocol['price_end'],summaries=summaries,unknown_or_immature_cases=frame[frame.status.ne('EXPLORATORY_ADJUSTED_MARK')].to_dict('records'),
                portfolio_pnl=False,files={f.name:digest(f) for f in out.iterdir() if f.is_file()})
    atomic_json(out/'report.json',result);print(result['status'],summaries,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['freeze','capture_identity','replay'],required=True)
    args=parser.parse_args();globals()[args.phase](args.output)
