"""Separate simple-query control after EFTS treated AND/parentheses literally.

Preserves the first probe. No provider scraping, mirror, price or backtest.
"""
import argparse
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
import re

from bs4 import BeautifulSoup
from scripts.research.us_index_deletion_feasibility import Client, Stopped, READ, UNIVERSE, MAPPING, FORMS, nearby
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def echoed_terms(payload):
    tree=payload.get('query',{}).get('query',{}).get('bool',{})
    return [x['match_phrase']['doc_text'] for key in ['must','should','must_not'] for x in tree.get(key,[]) if 'match_phrase' in x]


def run(root,prior):
    if root.exists():
        raise ValueError('Fresh immutable source control directory required')
    old=READ(prior/'report.json');verify_hashes(prior,old['files'])
    root.mkdir(parents=True);(root/'http').mkdir()
    universe=set(filter(None,re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig'))));mapping={}
    for x in READ(MAPPING).values():
        if x['ticker'] in universe:
            mapping.setdefault(str(x['cik_str']).zfill(10),set()).add(x['ticker'])
    files=[Path(__file__),Path('tests/test_us_index_deletion_source_check.py'),Path('scripts/research/us_index_deletion_feasibility.py'),prior/'report.json',UNIVERSE,MAPPING]
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
        reason='Initial EFTS response echoed AND and parentheses as literal required phrases; initial zero is NOT evidence of no issuer events',
        discovery_query='"Russell" "removed"',positive_control='"Russell"',forms=FORMS,
        limits=dict(requests=9,max_originals=5),first100_only=True,no_population_or_completeness_claim=True,
        selected_before_any_price=True,lseg_requests_allowed=False,mirrors_not_allowed=True,no_prices=True,no_sql=True,no_llm=True,no_training=True)
    atomic_json(root/'protocol.json',protocol)
    searches=[];originals=[];candidates={};stop=None;client=None
    try:
        client=Client(root)
        for year,query in [(2025,'"Russell"'),(2024,'"Russell" "removed"'),(2025,'"Russell" "removed"'),(2026,'"Russell" "removed"')]:
            params=dict(q=query,dateRange='custom',startdt=f'{year}-01-01',enddt=f'{year}-12-31' if year<2026 else '2026-09-30',forms=FORMS,**{'from':'0','size':'100'})
            body,receipt=client.get('https://efts.sec.gov/LATEST/search-index?'+urlencode(params))
            item=dict(year=year,query=query,receipt=receipt,status='UNAVAILABLE')
            if body:
                try:
                    payload=__import__('json').loads(body);hits=payload['hits']['hits'];total=payload['hits']['total'];terms=echoed_terms(payload)
                    n=total['value'] if isinstance(total,dict) else total
                    expected=['Russell'] if query=='"Russell"' else ['Russell','removed']
                    valid=terms==expected
                    item.update(status='VALIDATED_SIMPLE_QUERY' if valid else 'QUERY_SEMANTICS_UNQUALIFIED',
                        total_hits=total,returned=len(hits),truncated=n>len(hits),echoed_terms=terms)
                    if valid and query!='"Russell"':
                        for h in hits:
                            s=h['_source'];ciks={str(c).zfill(10) for c in s.get('ciks',[])}
                            if len(ciks)!=1 or not(ciks&mapping.keys()):
                                continue
                            acc=s.get('adsh','');name=h['_id'].split(':')[-1]
                            if not re.fullmatch(r'\d{10}-\d{2}-\d{6}',acc) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.html?',name):
                                continue
                            cik=next(iter(ciks));url=f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-","")}/{name}'
                            candidates[url]=dict(cik=cik,symbols=sorted(mapping[cik]),filed=s.get('file_date'),accession=acc,url=url)
                except (ValueError,KeyError,TypeError) as exc:
                    item.update(status='SCHEMA_UNQUALIFIED',error_type=type(exc).__name__)
            searches.append(item)
        chosen=sorted(candidates.values(),key=lambda r:(r['filed'] or '',r['accession'],r['url']))[:5]
        atomic_json(root/'selected-disclosures.json',dict(rows=chosen,all_candidates_in_truncated_pages=len(candidates),selected_without_prices=True))
        for row in chosen:
            body,receipt=client.get(row['url']);item=dict(**row,receipt=receipt,status='UNAVAILABLE')
            if body:
                text=BeautifulSoup(body,'html.parser').get_text(' ',strip=True)
                item.update(status='DISCOVERY_ONLY_NOT_ADMITTED',nearby_mentions=nearby(text))
            originals.append(item)
    except Stopped as exc:
        stop=str(exc)
    finally:
        if client:
            client.session.close()
    verify_hashes(Path('.'),protocol['sources'])
    result=dict(status='SOURCE_FEASIBILITY_ONLY_NO_AUTHORIZED_COMPLETE_COHORT',finished_at_utc=datetime.now(timezone.utc).isoformat(),
        searches=searches,originals=originals,stop=stop,new_requests=client.calls if client else 0,streamed_bytes=client.bytes if client else 0,
        files={str(f.relative_to(root)):digest(f) for f in root.rglob('*') if f.is_file()},no_economic_results=True)
    atomic_json(root/'report.json',result)
    print({k:result[k] for k in ['status','stop','new_requests','streamed_bytes']},flush=True)
    print([{k:v for k,v in x.items() if k!='receipt'} for x in searches],flush=True)
    print([dict(symbols=x['symbols'],filed=x['filed'],mentions=x.get('nearby_mentions'),status=x['status']) for x in originals],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--prior',type=Path,required=True)
    args=p.parse_args();run(args.output,args.prior)
