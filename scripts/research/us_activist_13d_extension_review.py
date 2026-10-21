"""Review/freeze/replay companion for the immutable 2024 original13D capture."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re

from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_activist_13d_extension import Client, prepare, PILOT
from scripts.research.us_activist_13d_pilot import READ, INITIAL, Stopped, normalized, parse
from scripts.research.us_activist_13d_review import check_clause, annual_before, primary_name, identity
from scripts.research.us_activist_13d_replay import PRICE, SCORES, price_path, marks
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

NOTES=Path('doc/ml/sources/activist_13d_extension_review_20261020.json')


def section4(obj, raw_body=None):
    if obj.get('item4'):
        return normalized(obj['item4']), 'LEGACY_HEADING'
    if raw_body:
        soup=BeautifulSoup(raw_body,'html.parser')
        nodes=soup.find_all(lambda n:n.name.lower().split(':')[-1]=='transactionpurpose')
        if len(nodes)==1:
            return normalized(nodes[0].get_text(' ',strip=True)), 'STRUCTURED_TRANSACTIONPURPOSE'
    parts=[p for p in obj['parts'] if p['type'] in INITIAL]
    text=normalized(parts[0]['text']) if len(parts)==1 else ''
    starts=list(re.finditer(r'\bItem\s*4\s*[.:\-]?\s*Purpose\s+of\s+(?:the\s+)?Transaction',text,re.I))
    sections=[]
    for m in starts:
        end=re.search(r'\bItem\s*5\b',text[m.end():],re.I)
        if end:
            sections.append(text[m.start():m.end()+end.start()])
    return (max(sections,key=len),'LEGACY_ALTERNATE_ITEM5') if sections else ('','UNRESOLVED')


def oversized(root):
    """One fresh bounded larger read, not a refusal bypass, never modifies old receipt."""
    p=prepare(root)
    out=root/'oversize-v1'
    if out.exists():
        raise ValueError('Fresh oversized-source capture required')
    out.mkdir();(out/'http').mkdir()
    candidates=[r for r in READ(root/'extraction.json')['rows'] if r['status']=='DOCUMENT_TOO_LARGE']
    limits=dict(p['limits'],requests=len(candidates),document_bytes=40*1024*1024,total_bytes=40*1024*1024,max_seconds=180)
    atomic_json(out/'protocol.json',dict(reason='Technical per-document cap extension before semantic review and prices',
                 limits=limits,candidates=candidates,source_hash=digest(Path(__file__)),no_bypass=True))
    client=Client(out,limits)
    rows=[];stop=None
    try:
        for r in candidates:
            body, receipt=client.get(r['receipt']['url'])
            obj=parse(body) if body else None
            rows.append(dict(accession=r['accession'],receipt=receipt,review=obj))
            print(r['accession'],receipt['status'],receipt.get('bytes'),flush=True)
    except (Stopped,ValueError) as exc:
        stop=str(exc)
    finally:
        client.session.close()
    atomic_json(out/'report.json',dict(rows=rows,stop=stop,requests=client.calls,streamed_bytes=client.bytes,
                files={str(f.relative_to(out)):digest(f) for f in (out/'http').glob('*')}))


def reviewed_objects(root):
    ext=READ(root/'extraction.json');verify_hashes(root,ext['files'])
    extra=READ(root/'oversize-v1/report.json') if (root/'oversize-v1/report.json').exists() else {'rows':[]}
    if extra.get('files'):
        verify_hashes(root/'oversize-v1',extra['files'])
    oversized_map={r['accession']:r for r in extra['rows']}
    for row in ext['rows']:
        if row['status']=='READY_REVIEW':
            obj=READ(root/row['review_file']);raw=(root/row['receipt']['file']).read_bytes()
        elif row['accession'] in oversized_map and oversized_map[row['accession']].get('review'):
            over=oversized_map[row['accession']];obj=over['review']
            raw=(root/'oversize-v1'/over['receipt']['file']).read_bytes()
            row=dict(row,subject_cik=obj['subject_cik'],subject_name=obj['subject_name'],
                     current_mapping_symbols=row['mapped_symbols'],current_tradable_symbols=row['mapped_symbols'],
                     source_override='oversize-v1/report.json')
        else:
            yield row,None,'','UNAVAILABLE';continue
        section,method=section4(obj,raw)
        yield row,obj,section,method


def inspect(root):
    prepare(root)
    if (root/'review-sections.json').exists():
        raise ValueError('Immutable derived sections')
    rows=[]
    for row,obj,text,method in reviewed_objects(root):
        rows.append(dict(accession=row['accession'],subject_cik=obj['subject_cik'] if obj else None,
                         subject_name=obj['subject_name'] if obj else None,method=method,section4=text))
    atomic_json(root/'review-sections.json',dict(rows=rows,no_prices_read=True,counts=dict(Counter(r['method'] for r in rows))))
    print(Counter(r['method'] for r in rows),flush=True)


def block_issuers(rows, sessions):
    blocked_until={}
    result=[]
    for item in sorted(rows,key=lambda r:(r['filed'],r['accession'])):
        row=dict(item,admitted=False,admission_reason='NOT_ELIGIBLE')
        if row['decision'] in ['PRIMARY_EXPLICIT_INTERVENTION','SECONDARY_GOVERNANCE_ONLY']:
            j=sessions.get_loc(pd.Timestamp(row['entry']))
            key=row['cik']  # Same issuer even when multiple symbols/classes or renamed.
            if j<blocked_until.get(key,-1):
                row['admission_reason']='ISSUER_60SESSION_BLOCK'
            else:
                row.update(admitted=True,admission_reason='EARLIEST_ELIGIBLE_ISSUER')
                blocked_until[key]=j+60
        result.append(row)
    return result


def freeze(root):
    p=prepare(root);out=root/'review-frozen-v1'
    if (out/'protocol.json').exists():
        payload=READ(out/'protocol.json');verify_hashes(Path('.'),payload['sources']);return out,payload
    if out.exists():
        raise ValueError('Fresh semantic freeze required')
    notes=READ(NOTES);mapping={n['accession']:n for n in notes['cases']}
    objects=list(reviewed_objects(root))
    if len(mapping)!=len(notes['cases']) or set(mapping)!={r['accession'] for r,_,_,_ in objects}:
        raise ValueError('Exactly one decision required for EVERY selected accession')
    calendar=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2025-06-30')
    sources=[Path(__file__),Path('tests/test_us_activist_13d_extension_review.py'),NOTES,
             root/'protocol.json',root/'selection.json',root/'documents.json',root/'extraction.json',root/'review-sections.json']
    if (root/'oversize-v1/report.json').exists():
        sources.extend([root/'oversize-v1/protocol.json',root/'oversize-v1/report.json'])
    rows=[]
    for r,obj,section,method in objects:
        n=mapping[r['accession']]
        eligible=n['decision'] in ['PRIMARY_EXPLICIT_INTERVENTION','SECONDARY_GOVERNANCE_ONLY']
        if obj:
            if n.get('subject_cik') and n['subject_cik']!=obj['subject_cik']:
                raise ValueError('Wrong SUBJECT issuer')
            for clause in n.get('clauses',[]):
                check_clause(obj,clause['filename'],clause['contains'])
            if not n.get('clauses') and n['decision']!='EXCLUDE_TARGET_OUTSIDE_MAIN_COHORT':
                raise ValueError('Reviewed decision needs an exact original clause')
            if n['decision']=='EXCLUDE_TARGET_OUTSIDE_MAIN_COHORT' and (r['cohort']!='CURRENT_UNIVERSE_INDEX_ROUTE' or r.get('current_tradable_symbols')):
                raise ValueError('Cannot hide an issuer eligible for main/probe review')
        elif not n['decision'].startswith('RESERVED_'):
            raise ValueError('Unavailable original cannot receive a semantic decision')
        entry=calendar[calendar.index>pd.Timestamp(r['filed'])].index[0]
        if eligible:
            if not obj or not obj.get('accepted_utc') or pd.Timestamp(obj['accepted_utc'])>=calendar.loc[entry].market_open:
                raise ValueError('No safe post-acceptance full session')
            if not n.get('symbol') or not n.get('clauses'):
                raise ValueError('Admitted event needs named class/symbol candidate and action proof')
        row=dict(**n,filed=r['filed'],quarter=r['quarter'],cohort=r['cohort'],
                 cik=obj['subject_cik'] if obj else None,subject_name=obj['subject_name'] if obj else None,
                 entry=str(entry.date()),accepted_utc=obj.get('accepted_utc') if obj else None,section_method=method,
                 source_review_file=r.get('review_file'),active=n['decision']=='PRIMARY_EXPLICIT_INTERVENTION')
        if eligible and n.get('identity_clause'):
            check_clause(obj,n['identity_clause']['filename'],n['identity_clause']['contains'])
            row['identity_status']='ORIGINAL_13D_TICKER_SUPPORT'
        elif eligible:
            row['identity_status']='UNKNOWN'
            facts=Path(f'artifacts/sec_cache/companyfacts/CIK{row["cik"]}.json')
            if facts.exists():
                sources.append(facts);row['annual_metadata']=annual_before(READ(facts),row['filed'])
        rows.append(row)
    rows=block_issuers(rows,calendar.index)
    out.mkdir()
    payload=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),rows=rows,decisions=dict(Counter(r['decision'] for r in rows)),
                 sources={str(f):digest(f) for f in set(sources)},freeze_before_extension_returns=True,
                 original_Q1_pilot_outcomes_already_observed=True,same_assistant_not_independent_human_review=True,
                 economic=p['economic'],eligible_primary=sum(r['active'] and r['admitted'] for r in rows))
    atomic_json(out/'protocol.json',payload)
    print('Frozen',len(rows),'decisions; primary',payload['eligible_primary'],payload['decisions'],flush=True)
    return out,payload


def capture_identity(root):
    out,review=freeze(root)
    if (out/'identity-capture.json').exists():
        raise ValueError('Immutable historical identity capture')
    client=Client(root,prepare(root)['limits']);rows=[];stop=None
    try:
        for row in review['rows']:
            if not row['admitted']:
                continue
            item=dict(accession=row['accession'],symbol=row['symbol'],identity=None)
            if row['identity_status']=='ORIGINAL_13D_TICKER_SUPPORT':
                item['identity']=row['identity_clause'];item['status']='ORIGINAL_13D'
            elif row.get('annual_metadata'):
                a=row['annual_metadata'];base=f'https://www.sec.gov/Archives/edgar/data/{int(row["cik"])}/{a["accession"].replace("-","")}/'
                body,receipt=client.get(base+a['accession']+'-index.html');item['index_receipt']=receipt
                if body:
                    name=primary_name(body);body,receipt=client.get(base+name);item['receipt']=receipt
                    if body:
                        item['identity']=identity(body,row['cik'],row['symbol'])
                item['status']='PREFILING_ANNUAL_CONFIRMED' if item['identity'] else 'UNKNOWN'
            else:
                item['status']='UNKNOWN_NO_EARLIER_ANNUAL_METADATA'
            rows.append(item)
            print('identity',row['symbol'],item['status'],flush=True)
    except (Stopped,ValueError) as exc:
        stop=str(exc)
    finally:
        client.session.close()
    atomic_json(out/'identity-capture.json',dict(rows=rows,stop=stop,requests=client.calls,streamed_bytes=client.bytes,
                files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


def replay(root):
    reviewout,review=freeze(root);out=root/'replay-extension-v1'
    if out.exists():
        raise ValueError('Fresh immutable replay directory required')
    ids=READ(reviewout/'identity-capture.json');verify_hashes(root,ids['files'])
    known={r['accession']:r for r in ids['rows']}
    events=[r for r in review['rows'] if r['admitted']]
    inputs=[Path(__file__),Path('tests/test_us_activist_13d_extension_review.py'),reviewout/'protocol.json',reviewout/'identity-capture.json',
            PRICE,PRICE.parent/'quality-reserves.json',SCORES/'2024-H20-scores.parquet',SCORES/'2024-done.json',SCORES/'final-audit.json',SCORES/'protocol.json']
    expected=next(v for k,v in READ(SCORES/'protocol.json')['sources'].items() if Path(k).name==PRICE.name)
    if digest(PRICE)!=expected or digest(SCORES/'2024-H20-scores.parquet')!=READ(SCORES/'2024-done.json')['files']['2024-H20-scores.parquet']:
        raise ValueError('Frozen prices or scores changed')
    out.mkdir()
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in inputs},events=events,
                  prices_end='2025-06-30',economic=review['economic'],eligibility_fixed_before_outcome_quality=True,
                  missing_outcomes_retained=True,no_live_or_portfolio_parity=True,not_first_worldwide_announcement_alpha=True)
    atomic_json(out/'protocol.json',protocol)
    days=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date=protocol['prices_end']).index
    symbols=sorted({e['symbol'] for e in events}|{'SPY'})
    prices=pd.read_parquet(PRICE,filters=[('symbol','in',symbols),('date','>=',pd.Timestamp('2024-01-01')),('date','<=',pd.Timestamp(protocol['prices_end']))])
    groups={s:g for s,g in prices.groupby('symbol')};reserves=READ(PRICE.parent/'quality-reserves.json')['price_reserves']
    decisions=[days[days.get_loc(pd.Timestamp(e['entry']))-1] for e in events]
    scores=pd.read_parquet(SCORES/'2024-H20-scores.parquet',columns=['date','symbol','rank','score'],filters=[('date','in',decisions)])
    if scores.duplicated(['date','symbol']).any():
        raise ValueError('Duplicate Oracle context')
    rows=[];bars=[]
    for event,decision in zip(events,decisions):
        context=scores[(scores.date==decision)&scores.symbol.eq(event['symbol'])]
        n=int(scores.date.eq(decision).sum());rank=int(context.iloc[0]['rank']) if len(context)==1 else None
        for h in protocol['economic']['horizons']:
            row=dict(accession=event['accession'],symbol=event['symbol'],cik=event['cik'],filed=event['filed'],entry=event['entry'],
                     quarter=event['quarter'],cohort=event['cohort'],scope='PRIMARY' if event['active'] else 'SECONDARY_GOVERNANCE',
                     horizon=h,earlier_public_action_date=event.get('earlier_public_action_date'),new_announcement_certified=False,
                     oracle_date=str(decision.date()),oracle_rank=rank,oracle_count=n,in_top10=rank is not None and rank<=10,
                     in_top20pct=rank is not None and rank<=int(np.ceil(.2*n)))
            if not known.get(event['accession'],{}).get('identity'):
                row.update(status='UNKNOWN',reason='HISTORICAL_TICKER_NOT_SUPPORTED');rows.append(row);continue
            pair={};problems=[]
            for s in [event['symbol'],'SPY']:
                path,why=price_path(groups.get(s,pd.DataFrame(columns=prices.columns)),days,pd.Timestamp(event['entry']),h,reserves.get(s))
                if path is None:
                    problems.append(s+':'+why)
                else:
                    pair[s]=path
            if problems:
                row.update(status='UNKNOWN',reason=';'.join(problems));rows.append(row);continue
            c=protocol['economic'];cost=c['spread_bps_per_leg']+c['slippage_bps_per_leg']
            stock=marks(pair[event['symbol']],c['notional_usd'],c['commission_per_order_usd'],cost)
            benchmark=marks(pair['SPY'],c['notional_usd'],c['commission_per_order_usd'],cost)
            stress=marks(pair[event['symbol']],c['notional_usd'],c['commission_per_order_usd'],c['stress_total_bps_per_leg'])
            row.update(status='EXPLORATORY_ADJUSTED_MARK',reason=None,**stock,benchmark_net_return=benchmark['net_return'],
                       excess_vs_spy=stock['net_return']-benchmark['net_return'],stress_net_return=stress['net_return'])
            rows.append(row)
            for s,path in pair.items():
                frame=path.reset_index(names='date');frame['symbol']=s;frame['accession']=event['accession'];frame['horizon']=h;bars.append(frame)
    frame=pd.DataFrame(rows)
    frame.to_csv(out/'event-results.csv',index=False)
    prices.to_parquet(out/'source-price-snapshot.parquet',index=False)
    scores.to_parquet(out/'oracle-context.parquet',index=False)
    if bars:
        pd.concat(bars,ignore_index=True).to_parquet(out/'audited-mark-inputs.parquet',index=False)
    summaries=[]
    for scope in ['PRIMARY','SECONDARY_GOVERNANCE']:
        for period in ['ALL_2024','Q1_PILOT','Q2_Q4_EXTENSION']:
            for h in [20,60]:
                selected=frame[(frame.scope==scope)&frame.horizon.eq(h)]
                if period!='ALL_2024':
                    selected=selected[selected.quarter.eq(1) if period=='Q1_PILOT' else selected.quarter.gt(1)]
                good=selected[selected.status=='EXPLORATORY_ADJUSTED_MARK']
                summaries.append(dict(scope=scope,period=period,horizon=h,admitted=len(selected),qualified=len(good),unknown=len(selected)-len(good),
                    positive_net=int(good.net_return.gt(0).sum()) if len(good) else 0,negative_net=int(good.net_return.lt(0).sum()) if len(good) else 0,
                    mean_net=float(good.net_return.mean()) if len(good) else None,median_net=float(good.net_return.median()) if len(good) else None,
                    mean_spy=float(good.benchmark_net_return.mean()) if len(good) else None,mean_excess=float(good.excess_vs_spy.mean()) if len(good) else None,
                    mean_stress=float(good.stress_net_return.mean()) if len(good) else None,
                    top10=int(good.in_top10.sum()) if len(good) else 0,top20pct=int(good.in_top20pct.sum()) if len(good) else 0))
    verify_hashes(Path('.'),protocol['sources'])
    result=dict(status='EXPLORATORY_2024_EXTENSION_NOT_VALIDATED_SIGNAL',finished_at_utc=datetime.now(timezone.utc).isoformat(),
                issuer_count=len({r['cik'] for r in events if r['active']}),summaries=summaries,
                unknown_cases=frame[frame.status=='UNKNOWN'].to_dict('records'),portfolio_pnl=False,
                files={f.name:digest(f) for f in out.iterdir() if f.is_file()})
    atomic_json(out/'report.json',result)
    print(result['status'],result['issuer_count'],'primary issuers',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['oversized','inspect','freeze','capture_identity','replay'],required=True)
    args=parser.parse_args();globals()[args.phase](args.output)
