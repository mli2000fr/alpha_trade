"""Issuer self-tender source census/pilot, no price or economic backtest.

Reuse complete official quarterly indexes; capture all current-universe index
routes plus four hash-selected outside-route initial accessions per year.
SC TO-I is not assumed to mean listed fixed-price common-stock tender.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import hashlib
import re

import pandas as pd
from scripts.research.us_activist_13d_confirmation import Client
from scripts.research.us_activist_13d_extension import parse_quarter
from scripts.research.us_activist_13d_pilot import READ,UNIVERSE,MAPPING,Stopped
from scripts.research.us_cash_merger_feasibility import visible
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

INDEX_ROOTS=[Path('artifacts/research/us_activist_13d/extension-2024-20261020-v1'),
             Path('artifacts/research/us_activist_13d/confirmation-2025-2026-20261020-v1')]


def distinct_initials(rows,mapping):
    unique={}
    for row in rows:
        if row['form']!='SC TO-I':
            continue
        accession=row['accession']
        item=unique.setdefault(accession,dict(accession=accession,filed=row['filed'],year=int(row['filed'][:4]),
            indexed_ciks=[],index_names=[],paths=[],mapped_symbols=[]))
        if item['filed']!=row['filed']:
            raise ValueError('Conflicting accession dates')
        for key,values in [('indexed_ciks',[row['cik']]),('index_names',[row['name']]),('paths',[row['path']]),('mapped_symbols',mapping.get(row['cik'],[]))]:
            item[key]=sorted(set(item[key])|set(values))
    return sorted(unique.values(),key=lambda r:(r['filed'],r['accession']))


def choose(rows,n=4):
    chosen=[dict(r,cohort='CURRENT_UNIVERSE_INDEX_ROUTE') for r in rows if r['mapped_symbols']]
    for year in [2024,2025,2026]:
        other=sorted([r for r in rows if r['year']==year and not r['mapped_symbols']],key=lambda r:hashlib.sha256(r['accession'].encode()).hexdigest())
        chosen.extend(dict(r,cohort='OUTSIDE_ROUTE_HASH_PROBE') for r in other[:n])
    return sorted(chosen,key=lambda r:(r['filed'],r['accession']))


def parse_original(body):
    text=body.decode('utf-8',errors='replace')
    if '</SEC-DOCUMENT>' not in text.upper():
        raise ValueError('Incomplete SEC original')
    head=text.split('<DOCUMENT>',1)[0]
    sub=re.search(r'SUBJECT COMPANY:(.*?)(?=FILED BY:|</SEC-HEADER>)',head,re.S)
    if not sub:
        raise ValueError('No unambiguous SUBJECT COMPANY')
    cik=re.search(r'CENTRAL INDEX KEY:\s*(\d+)',sub.group(1));name=re.search(r'COMPANY CONFORMED NAME:\s*([^\r\n]+)',sub.group(1))
    stamp=re.search(r'<ACCEPTANCE-DATETIME>(\d{14})',head)
    if not cik or not name or not stamp:
        raise ValueError('Missing subject or acceptance')
    accepted=pd.to_datetime(stamp.group(1),format='%Y%m%d%H%M%S').tz_localize('America/New_York').tz_convert('UTC').isoformat()
    parts=[]
    for raw in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',text,re.S|re.I):
        typ=re.search(r'<TYPE>([^\r\n<]+)',raw);filename=re.search(r'<FILENAME>([^\r\n<]+)',raw)
        if not typ:
            continue
        typ=typ.group(1).strip()
        if typ!='SC TO-I' and (not typ.startswith('EX-') or typ.startswith(('EX-101','EX-107'))):
            continue
        parts.append(dict(type=typ,filename=filename.group(1).strip() if filename else None,
            text=visible(raw.split('<TEXT>',1)[-1].split('</TEXT>',1)[0])))
    if sum(r['type']=='SC TO-I' for r in parts)!=1:
        raise ValueError('Initial issuer tender primary not unique')
    return dict(subject_cik=cik.group(1).zfill(10),subject_name=name.group(1).strip(),accepted_utc=accepted,
        parts=parts,header=head,not_local_historical_receipt=True)


def discovery(obj):
    patterns={'offer_terms':r'(?:offer to (?:purchase|exchange)|purchase price|not greater than|not less than|cash price)',
              'security':r'(?:common (?:stock|shares)|ordinary shares|American Depositary|stock options|restricted stock|preferred (?:stock|shares)|convertible (?:notes|bonds))',
              'execution':r'(?:odd lot|prorat|withdrawal rights|expiration (?:date|time)|tender all|record date)',
              'fund':r'(?:net asset value|investment company act|closed.end fund|interval fund)'}
    result={}
    for key,pattern in patterns.items():
        found=[]
        for p in obj['parts']:
            for match in list(re.finditer(pattern,p['text'],re.I))[:4]:
                found.append(dict(filename=p['filename'],text=p['text'][max(0,match.start()-140):match.end()+280]))
        result[key]=found[:12]
    return result


def census(root):
    if root.exists():
        raise ValueError('Fresh immutable study directory required')
    universe=set(filter(None,re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig'))));mapping={}
    for row in READ(MAPPING).values():
        if row['ticker'] in universe:
            mapping.setdefault(str(row['cik_str']).zfill(10),set()).add(row['ticker'])
    sources=[Path(__file__),Path('tests/test_us_self_tender_feasibility.py'),UNIVERSE,MAPPING,
        Path('scripts/research/us_activist_13d_confirmation.py'),Path('scripts/research/us_activist_13d_extension.py'),
        Path('scripts/research/us_cash_merger_feasibility.py')]
    indexes=[];seen=set();rows=[];forms=Counter()
    for prior in INDEX_ROOTS:
        file=prior/'selection.json';sources.append(file)
        for item in READ(file)['indexes']:
            key=(item['year'],item['quarter'])
            if key in seen:
                continue
            if item.get('status','OK')!='OK':
                raise ValueError('Incomplete quarter index')
            receipt=item['receipt'];body=prior/receipt['file']
            if digest(body)!=receipt['sha256']:
                raise ValueError('Original index changed')
            sources.append(body);parsed=parse_quarter(body.read_bytes(),*key)
            subset=[r for r in parsed if r['form'] in ['SC TO-I','SC TO-I/A']]
            rows.extend(subset);forms.update((str(key[0]),r['form']) for r in subset)
            indexes.append(dict(year=key[0],quarter=key[1],source=str(body),sha256=digest(body),index_rows=len(parsed),
                initial_rows=sum(r['form']=='SC TO-I' for r in subset),amendment_rows=sum(r['form']=='SC TO-I/A' for r in subset)))
            seen.add(key)
    if seen!={(y,q) for y in [2024,2025] for q in [1,2,3,4]}|{(2026,q) for q in [1,2,3]}:
        raise ValueError('Prescribed historical quarters incomplete')
    initial=distinct_initials(rows,mapping);chosen=choose(initial)
    root.mkdir(parents=True);(root/'http').mkdir()
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in sources},
        period='2024-01-01 through 2026-09-30',universe_count=len(universe),selection='All indexedCIKs in CURRENT tradable mapping plus four outside-route smallest accessionSHA256 per year; dedup cofilers before selection; no price/outcome filter.',
        scope='Metadata census of SC TO-I initial accessions, NOT count of listed common-stock fixed-price offers; amendments retained as metadata, not new offers.',
        survivor_bias='Current1790 not historical universe; outside probe not exhaustive delisted census. Subject CIK must confirm issuer, never index filer assumed target.',
        broker='Alpaca current published voluntary election fee100USD is a feasibility stress, not proven historical fee/account eligibility. No election or broker API requested. Paper stock fill does not simulate tender acceptance/proration/cashcredit.',
        semantic_gate='Manual exact clauses in original. Common/ordinary listed equity only; fixed cash price excluding Dutch auction/NAV/option/debt/shareexchange. Historical ticker/ADS eligibility, expiration/deadline, proration, oddlot conditions, participation channel and fees must qualify before any PnL.',
        no_future_completion_assumed=True,no_prices=True,no_training=True,no_llm=True,no_sql=True,no_orders=True,no_batch_changes=True,
        limits=dict(requests=65,total_bytes=180*1024*1024,document_bytes=20*1024*1024,interval_seconds=.6,max_seconds=1200))
    atomic_json(root/'protocol.json',protocol)
    summaries=[dict(year=y,initial_index_rows=forms[(str(y),'SC TO-I')],amendment_index_rows=forms[(str(y),'SC TO-I/A')],
        distinct_initials=sum(r['year']==y for r in initial),current_route=sum(r['year']==y and bool(r['mapped_symbols']) for r in initial),
        selected=sum(r['year']==y for r in chosen)) for y in [2024,2025,2026]]
    atomic_json(root/'census.json',dict(indexes=indexes,summaries=summaries,initials=initial,amendments=[r for r in rows if r['form']=='SC TO-I/A'],selected=chosen,prices_read=False))
    print(summaries,flush=True)


def acquire(root):
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources']);table=READ(root/'census.json')
    if (root/'documents.json').exists():
        raise ValueError('Immutable capture; no implicit retries')
    client=Client(root,protocol['limits']);results=[];stop=None
    try:
        for i,row in enumerate(table['selected'],1):
            body,receipt=client.get('https://www.sec.gov/Archives/'+row['paths'][0])
            results.append(dict(selection=row,receipt=receipt))
            atomic_json(root/'progress.json',dict(status='CAPTURING',completed=i,total=len(table['selected'])))
            print(i,'/',len(table['selected']),row['filed'],row['mapped_symbols'],receipt['status'],flush=True)
    except Stopped as exc:
        stop=str(exc)
    finally:
        client.session.close()
    report=dict(status='COMPLETE_ATTEMPTS' if not stop and len(results)==len(table['selected']) else 'INCOMPLETE',
        stop=stop,documents=results,files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')})
    atomic_json(root/'documents.json',report);atomic_json(root/'progress.json',dict(status=report['status'],completed=len(results),total=len(table['selected']),stop=stop))


def extract(root):
    protocol=READ(root/'protocol.json');verify_hashes(Path('.'),protocol['sources']);docs=READ(root/'documents.json');verify_hashes(root,docs['files'])
    if (root/'extraction.json').exists():
        raise ValueError('Immutable extraction')
    folder=root/'review';folder.mkdir();rows=[]
    for item in docs['documents']:
        row=dict(**item['selection'],receipt=item['receipt'],status=item['receipt']['status'])
        if row['status']=='OK':
            try:
                obj=parse_original((root/row['receipt']['file']).read_bytes());path=folder/f"{row['accession']}.json";atomic_json(path,obj)
                row.update(status='READY_MANUAL_REVIEW',review_file=str(path.relative_to(root)),subject_cik=obj['subject_cik'],subject_name=obj['subject_name'],
                    accepted_utc=obj['accepted_utc'],subject_in_indexed_ciks=obj['subject_cik'] in row['indexed_ciks'],discovery=discovery(obj))
            except ValueError as exc:
                row.update(status='UNRESOLVED_SOURCE',reason=str(exc))
        rows.append(row)
    result=dict(status='EXTRACTED_NOT_ECONOMICALLY_TESTED',rows=rows,counts=dict(Counter(r['status'] for r in rows)),
        no_prices_read=True,not_all_fixed_cash_offers=True,files={str(f.relative_to(root)):digest(f) for f in folder.glob('*')})
    atomic_json(root/'extraction.json',result);print(result['counts'],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--phase',choices=['census','acquire','extract'],required=True)
    args=p.parse_args();globals()[args.phase](args.output)
