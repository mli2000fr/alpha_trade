"""Independent scalar/control recomputation, not independent human semantics."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_activist_13d_extension import prepare,parse_quarter,distinct,choose,MAPPING,UNIVERSE
from scripts.research.us_activist_13d_extension_review import reviewed_objects,freeze,NOTES
from scripts.research.us_activist_13d_pilot import READ,parse
from scripts.research.us_activist_13d_review import check_clause,identity
from scripts.research.us_activist_13d_replay import price_path,PRICE
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def close(actual,expected):
    if not np.isfinite([actual,expected]).all() or not np.isclose(actual,expected,rtol=1e-11,atol=1e-12):
        raise ValueError(f'Scalar audit mismatch {actual} / {expected}')


def scalar(path,commission=1.,notional=1000.,bps=10.):
    entry=float(path.open.iloc[0]);exit=float(path.close.iloc[-1]);ratio=exit/entry
    return ratio-1-2*commission/notional-bps/10000*(1+ratio)


def audit(root):
    p=prepare(root);reviewout,review=freeze(root);out=root/'replay-extension-v1'
    if (out/'audit.json').exists():
        raise ValueError('Immutable audit')
    docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    over=READ(root/'oversize-v1/report.json');verify_hashes(root/'oversize-v1',over['files'])
    if digest(Path('scripts/research/us_activist_13d_extension_review.py'))!=READ(root/'oversize-v1/protocol.json')['source_hash']:
        raise ValueError('Oversized capture implementation changed')
    ids=READ(reviewout/'identity-capture.json');verify_hashes(root,ids['files'])
    report=READ(out/'report.json');verify_hashes(out,report['files'])
    protocol=READ(out/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    selection=READ(root/'selection.json');verify_hashes(root,selection['selected_files'])
    # Reconstruct all market index candidates and the frozen hash-sample selection.
    import re
    universe={s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s}
    mapping={}
    for x in READ(MAPPING).values():
        if x['ticker'] in universe:
            mapping.setdefault(str(x['cik_str']).zfill(10),set()).add(x['ticker'])
    allrows=[];indexcounts=[]
    for x in selection['indexes']:
        receipt=x['receipt'];body=(root/receipt['file']).read_bytes()
        if digest(root/receipt['file'])!=receipt['sha256']:
            raise ValueError('Index changed')
        rows=parse_quarter(body,x['year'],x['quarter'])
        if len(rows)!=x['index_rows'] or len(distinct(rows,mapping))!=x['initial_accessions']:
            raise ValueError('Index counters incorrect')
        if x['year']==2024:
            allrows.extend(rows)
        indexcounts.append(dict(year=x['year'],quarter=x['quarter'],initial_accessions=x['initial_accessions']))
    if choose(distinct(allrows,mapping),p['noncurrent_probe_per_quarter'])!=selection['selected']:
        raise ValueError('Accession sample differs from pre-outcome selection')
    objects={r['accession']:(r,obj,text,method) for r,obj,text,method in reviewed_objects(root)}
    notes={r['accession']:r for r in READ(NOTES)['cases']}
    if set(objects)!=set(notes) or len(docs['documents'])!=len(selection['selected']):
        raise ValueError('Source denominator silently changed')
    parsed=0
    for doc in docs['documents']:
        if doc['receipt']['status']=='OK':
            obj=parse((root/doc['receipt']['file']).read_bytes());stored=objects[doc['selection']['accession']][1]
            if obj!=stored:
                raise ValueError('Extraction no longer agrees with raw original')
            parsed+=1
    for item in over['rows']:
        if item['receipt']['status']=='OK':
            obj=parse((root/'oversize-v1'/item['receipt']['file']).read_bytes())
            if obj!=item['review']:
                raise ValueError('Oversized original extraction mismatch')
            parsed+=1
    for accession,note in notes.items():
        obj=objects[accession][1]
        if obj:
            if obj['subject_cik']!=note['subject_cik']:
                raise ValueError('Subject/filer confusion')
            for c in note.get('clauses',[]):
                check_clause(obj,c['filename'],c['contains'])
    calendar=mcal.get_calendar('NYSE').schedule(start_date='2024-01-01',end_date='2025-06-30')
    admitted=[];until={}
    for row in sorted(review['rows'],key=lambda r:(r['filed'],r['accession'])):
        expected=calendar[calendar.index>pd.Timestamp(row['filed'])].index[0]
        if row['entry']!=str(expected.date()):
            raise ValueError('Premature or wrong session entry')
        if row['decision'] in ['PRIMARY_EXPLICIT_INTERVENTION','SECONDARY_GOVERNANCE_ONLY']:
            if pd.Timestamp(row['accepted_utc'])>=calendar.loc[expected].market_open:
                raise ValueError('Acceptance not before entry')
            j=calendar.index.get_loc(expected);should=j>=until.get(row['cik'],-1)
            if row['admitted']!=should:
                raise ValueError('Issuer block violated')
            if should:
                until[row['cik']]=j+60;admitted.append(row)
    supported={}
    for item in ids['rows']:
        r=next(r for r in admitted if r['accession']==item['accession'])
        if r.get('identity_clause'):
            c=r['identity_clause'];check_clause(objects[r['accession']][1],c['filename'],c['contains']);supported[r['accession']]=True
        elif item.get('receipt',{}).get('status')=='OK':
            if identity((root/item['receipt']['file']).read_bytes(),r['cik'],r['symbol'])!=item['identity']:
                raise ValueError('Historical ticker/class mismatch')
            if not r['annual_metadata']['filed']<r['filed']:
                raise ValueError('Future annual cover used for identity')
            supported[r['accession']]=bool(item['identity'])
        else:
            supported[r['accession']]=False
    frame=pd.read_csv(out/'event-results.csv',dtype={'cik':str})
    expectedkeys={(r['accession'],h) for r in admitted for h in [20,60]}
    if set(zip(frame.accession,frame.horizon))!=expectedkeys or len(frame)!=len(expectedkeys):
        raise ValueError('Admitted event/horizon missing, duplicated or replaced')
    prices=pd.read_parquet(out/'source-price-snapshot.parquet');scores=pd.read_parquet(out/'oracle-context.parquet')
    bars=pd.read_parquet(out/'audited-mark-inputs.parquet')
    groups={s:g for s,g in prices.groupby('symbol')};reserves=READ(PRICE.parent/'quality-reserves.json')['price_reserves']
    checked=0
    for row in frame.to_dict('records'):
        if row['status']!='EXPLORATORY_ADJUSTED_MARK':
            continue
        if not supported.get(row['accession']):
            raise ValueError('PnL despite unresolved historical identity')
        entry=pd.Timestamp(row['entry']);h=row['horizon'];paths={}
        for s in [row['symbol'],'SPY']:
            path,why=price_path(groups[s],calendar.index,entry,h,reserves.get(s))
            if path is None or len(path)!=h:
                raise ValueError('Unqualified marks in economic result '+why)
            archived=bars[(bars.accession==row['accession'])&bars.horizon.eq(h)&bars.symbol.eq(s)].sort_values('date')
            if list(archived.date)!=list(path.index):
                raise ValueError('Mark window mismatch')
            for col in ['open','high','low','close']:
                np.testing.assert_allclose(archived[col].to_numpy(float),path[col].to_numpy(float),rtol=1e-12)
            paths[s]=path
        stock=scalar(paths[row['symbol']]);spy=scalar(paths['SPY'])
        close(row['net_return'],stock);close(row['benchmark_net_return'],spy);close(row['excess_vs_spy'],stock-spy)
        close(row['stress_net_return'],scalar(paths[row['symbol']],bps=25.))
        close(row['hypothetical_net_usd'],1000*stock)
        decision=calendar.index[calendar.index.get_loc(entry)-1]
        current=scores[(scores.date==decision)&scores.symbol.eq(row['symbol'])]
        n=int(scores.date.eq(decision).sum())
        if len(current)!=1 or int(current.iloc[0]['rank'])!=row['oracle_rank'] or n!=row['oracle_count']:
            raise ValueError('Non-contemporaneous Oracle context')
        if row['in_top10']!=(row['oracle_rank']<=10) or row['in_top20pct']!=(row['oracle_rank']<=int(np.ceil(.2*n))):
            raise ValueError('Wrong Oracle pool assignment')
        checked+=1
    for summary in report['summaries']:
        part=frame[(frame.scope==summary['scope'])&frame.horizon.eq(summary['horizon'])]
        if summary['period']!='ALL_2024':
            part=part[part.quarter.eq(1) if summary['period']=='Q1_PILOT' else part.quarter.gt(1)]
        good=part[part.status=='EXPLORATORY_ADJUSTED_MARK']
        if len(part)!=summary['admitted'] or len(good)!=summary['qualified'] or len(part)-len(good)!=summary['unknown']:
            raise ValueError('Summary denominator mismatch')
        if len(good):
            for key,col in [('mean_net','net_return'),('mean_spy','benchmark_net_return'),('mean_excess','excess_vs_spy'),('mean_stress','stress_net_return')]:
                close(summary[key],float(good[col].mean()))
            if summary['positive_net']!=int(good.net_return.gt(0).sum()) or summary['negative_net']!=int(good.net_return.lt(0).sum()):
                raise ValueError('Wrong winner/loser count')
    # Reproduce the old Q1 results, not relabel them as unseen confirmation.
    old=pd.read_csv(Path('artifacts/research/us_activist_13d/20261020-v1/replay-v1/event-results.csv'))
    for x in frame[frame.quarter.eq(1)].to_dict('records'):
        prior=old[old.accession.eq(x['accession'])&old.horizon.eq(x['horizon'])].iloc[0]
        close(x['net_return'],float(prior.net_return))
    receipts=[READ(f) for f in (root/'http').glob('*.json')]+[READ(f) for f in (root/'oversize-v1/http').glob('*.json')]
    new=[x for x in receipts if not x.get('reused_from')]
    result=dict(status='PASS_EXPLORATORY_2024_ONLY_WITH_DOCUMENTARY_RESERVES',finished_at_utc=datetime.now(timezone.utc).isoformat(),
                index_quarters_verified=indexcounts,selected_accessions=len(selection['selected']),originals_reparsed=parsed,
                primary_issuers=report['issuer_count'],event_horizon_scalars_checked=checked,
                all_admitted_retained=True,no_future_outcome_candidate_replacement=True,old_Q1_reproduced=True,
                documentary_reserves=[dict(accession=r['accession'],issuer=r['subject_name'],decision=r['decision']) for r in review['rows'] if r['decision'].startswith('RESERVED_')],
                new_sec_requests=len(new),new_streamed_bytes=sum(r.get('streamed_bytes',0) for r in new),
                http_status_counts=dict(Counter(str(r.get('http_status')) for r in new)),
                same_assistant_not_independent_human=True,no_model_sql_llm_order_or_batch_change=True,
                sources={str(Path(__file__)):digest(Path(__file__)),str(out/'report.json'):digest(out/'report.json')})
    atomic_json(out/'audit.json',result)
    print(result,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    audit(p.parse_args().output)
