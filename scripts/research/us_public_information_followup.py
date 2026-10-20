"""Bounded public SEC follow-up: consensus semantics and a fresh Q1 event population.

Existing files / official public documents only. No SQL, LLM, prices after a
decision, training, broker orders or modification of earlier sealed pilots.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_earnings_release_reconstruction import (
    Fetcher, AccessStopped, rows_from_metadata, acceptance, reaction_day,
)
from scripts.research.us_earnings_release_table_review import exhibits, LABELS, numbers, scale_in

TOP20=Path('artifacts/research/us_consensus_revenue_top20/20261019-v1')
READY=Path('artifacts/research/us_earnings_reaction_readiness/20261019-v1')
OLD=Path('artifacts/research/us_earnings_release_reconstruction/20261019-v1')
MAP=Path('artifacts/sec_cache/company_tickers.json')
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
DATES=r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(20\d{2})'


def document_url(cik,accession):
    if not re.fullmatch(r'\d{10}',cik) or not re.fullmatch(r'\d{10}-\d{2}-\d{6}',accession):
        raise ValueError('Invalid SEC identity')
    return f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace("-","")}/{accession}.txt'


def metadata_rows(obj):
    records=rows_from_metadata(obj)
    ids=[r['accessionNumber'] for r in records]
    if len(set(ids))!=len(ids):
        raise ValueError('Duplicate filing accession')
    return records


def candidate_event(row):
    return row.get('form')=='6-K' or (row.get('form')=='8-K' and '2.02' in str(row.get('items','')).split(','))


def quarter_dates(text,*,prospective=False):
    verb=r'(?:ending|ends?|ended)' if prospective else 'ended'
    pattern=rf'(?:quarter|three[ -]months|thirteen[ -]weeks).{{0,100}}?\b{verb}\b.{{0,30}}?{DATES}'
    found=[]
    for m in re.finditer(pattern,text,re.I|re.S):
        month,day,year=m.group(m.lastindex-2),m.group(m.lastindex-1),m.group(m.lastindex)
        try:end=pd.to_datetime(f'{month} {day} {year}').normalize()
        except ValueError:continue
        found.append(dict(end=end.strftime('%Y-%m-%d'),quote=text[max(0,m.start()-90):m.end()+180]))
    return found


def same_month_anchor(actual,anchor):
    """Never invent a numeric threshold for 'first days of next month'."""
    day=pd.Timestamp(actual);vendor=pd.Timestamp(anchor)
    return day.year==vendor.year and day.month==vendor.month and vendor.is_month_end


def primary_parts(body):
    result=[]
    for part in re.findall(r'<DOCUMENT>(.*?)</DOCUMENT>',body,re.I|re.S):
        m=re.search(r'<TYPE>([^\r\n<]+)',part)
        if m and m.group(1).strip() in ('10-Q','10-K','20-F','6-K'):
            result.append((m.group(1).strip(),part))
    return result


def visible(part):
    soup=BeautifulSoup(part,'html.parser')
    for node in soup(['script','style','ix:header','ix:hidden','xbrli:xbrl']):node.decompose()
    return ' '.join(soup.stripped_strings)


def inline_currencies(body):
    """Reporting currency from nondimensional monetary REVENUE facts, not listing currency."""
    proofs=[]
    for typ,part in primary_parts(body):
        soup=BeautifulSoup(part,'html.parser')
        units={str(u.get('id','')):u.get_text(' ',strip=True) for u in soup.find_all(re.compile(r'(?:^|:)unit$'))}
        contexts={str(c.get('id','')):c for c in soup.find_all(re.compile(r'(?:^|:)context$'))}
        for fact in soup.find_all('ix:nonfraction'):
            tag=str(fact.get('name','')).split(':')[-1]
            if tag not in ('Revenues','SalesRevenueNet','RevenueFromContractWithCustomerExcludingAssessedTax','Revenue','RevenueFromContractsWithCustomers'):
                continue
            context=contexts.get(str(fact.get('contextref','')))
            if context is None or context.find(re.compile(r'(?:explicitmember|typedmember)$')) is not None:
                continue
            measure=units.get(str(fact.get('unitref','')),'')
            currencies=re.findall(r'iso4217:([A-Z]{3})\b',measure)
            end=context.find(re.compile(r'(?:^|:)enddate$'))
            if len(currencies)==1 and end is not None:
                proofs.append(dict(form=typ,currency=currencies[0],tag=tag,
                    context_id=context.get('id'),end=end.get_text(strip=True),
                    unit_id=fact.get('unitref'),unit_measure=measure))
    currencies=sorted({x['currency'] for x in proofs})
    return dict(currency=currencies[0] if len(currencies)==1 else None,proofs=proofs,
                status='UNAMBIGUOUS_NON_DIMENSIONAL_REVENUE_UNIT' if len(currencies)==1 else 'MISSING_OR_MULTIPLE_REPORTING_CURRENCIES')


def standalone_tables(body,current_year):
    """Quarterly GAAP-like table quartets from original releases, no later 10-Q target values."""
    found=[]
    for typ,html in exhibits(body):
        soup=BeautifulSoup(html,'html.parser')
        for node in soup(['script','style','ix:header','ix:hidden']):node.decompose()
        for i,table in enumerate(soup.find_all('table')):
            if table.find('table') is not None:continue
            content=' '.join(table.stripped_strings)
            header=content[:1800]
            years=list(dict.fromkeys(int(y) for y in re.findall(r'\b20\d{2}\b',header)))
            scale=scale_in(header)
            if years[:2]!=[current_year,current_year-1] or not scale or not re.search(r'three\s+months|thirteen\s+weeks|quarter',header,re.I):
                continue
            # GAAP/consolidated statement evidence is not an adjusted EBITDA table.
            if re.search(r'non[ -]GAAP|adjusted|reconciliation',header[:350],re.I):continue
            metrics={};quotes={}
            for row in table.find_all('tr'):
                cells=[' '.join(c.stripped_strings) for c in row.find_all(['td','th'],recursive=False)]
                nonempty=[(j,x) for j,x in enumerate(cells) if x]
                if not nonempty:continue
                j,label=nonempty[0]
                metric=next((k for k,p in LABELS.items() if p.fullmatch(label.strip())),None)
                if metric is None:continue
                nums=numbers(' '.join(cells[j+1:]))
                if len(nums)>=2:
                    metrics.setdefault(metric,set()).add(tuple(x*scale for x in nums[:2]));quotes[metric]=' '.join(cells)
            if set(metrics)=={'revenue','operating'} and all(len(v)==1 for v in metrics.values()):
                rev=next(iter(metrics['revenue']));op=next(iter(metrics['operating']))
                found.append(dict(exhibit=typ,table_index=i,scale=scale,values=[*rev,*op],
                    header=header,rows=quotes))
    unique={tuple(x['values']) for x in found}
    return dict(values=list(next(iter(unique))) if len(unique)==1 else None,proofs=found)


def ancestor_sources(sources):
    """Record Git Windows CRLF conversion, never accept an actual source edit."""
    reconciled=[]
    for name,expected in sources.items():
        path=Path(name);actual=digest(path)
        if actual==expected:continue
        normalized=hashlib.sha256(path.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if path.suffix=='.py' and normalized==expected:
            reconciled.append(dict(path=str(path),original_sha256=expected,current_sha256=actual,
                equivalence='CRLF_TO_LF_ONLY_ORIGINAL_SEAL_UNCHANGED'))
        else:raise ValueError(f'Source content changed: {path}')
    return reconciled


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources']);return p
    if root.exists():raise ValueError('Fresh output directory required')
    reconciled=[]
    for parent in (TOP20,READY,OLD):
        reconciled+=ancestor_sources(READ(parent/'protocol.json')['sources'])
        verify_hashes(parent,READ(parent/'report.json')['files'])
    f=pd.read_parquet(TOP20/'qualified-cohort.parquet')
    f=f[f.pair_present & f.technical_pair.eq(True) & f.count_group.eq('UNCHANGED_COUNT') & f.numeric_pattern.ne('ABSTAIN')]
    pending=f[~f.supported_research_feature].sort_values('oracle_rank')
    top=pd.read_parquet(READY/'top10.parquet')
    q1=top[top.date.between('2024-01-01','2024-03-31')].copy()
    mapping={}
    for row in READ(MAP).values():mapping.setdefault(str(row['ticker']).upper(),set()).add(str(row['cik_str']).zfill(10))
    symbols=sorted(set(pending.symbol)|set(q1.symbol));identities={s:sorted(mapping.get(s,set())) for s in symbols}
    paths=[Path(__file__),Path('tests/test_us_public_information_followup.py'),MAP,
        TOP20/'protocol.json',TOP20/'report.json',TOP20/'qualified-cohort.parquet',
        READY/'protocol.json',READY/'report.json',READY/'top10.parquet',
        OLD/'protocol.json',OLD/'report.json',OLD/'documents.json',
        Path('scripts/research/us_earnings_release_reconstruction.py'),
        Path('scripts/research/us_earnings_release_table_review.py')]
    root.mkdir(parents=True);(root/'http').mkdir()
    pending.to_parquet(root/'consensus-candidates.parquet',index=False)
    q1.to_parquet(root/'q1-top10.parquet',index=False)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(x):digest(x) for x in paths},
        ancestor_source_newline_reconciliation=reconciled,
        consensus_symbols=pending.symbol.tolist(),q1_symbols=sorted(q1.symbol.unique()),identities=identities,
        consensus_scope='62 unchanged-count revenue patterns, no new feature or outcome selection. At most latest original financial statement and latest2.02 earnings release BEFORE old decision cutoff for each issuer.',
        consensus_currency='Unambiguous consolidated/nondimensional inline revenue unit in issuer filing, interpreted under provider statement that reporting currency applies. No USD inferred from US listing.',
        consensus_period='Explicit quarter ended/ending date with same-month month-end provider anchor; next-month early-days never mapped by invented threshold. Excerpts are routing evidence, require review before qualification.',
        event_scope='Fresh COMPLETE calendar window2024Q1,610TOP10symbol/dates61sessions32issuers. Enumerate earnings8K item2.02 and all6K from20Dec2023 through31Mar2024 independent of prior93cases, then exact TOP10 at first FULL reaction-session close. No outcomes read.',
        event_population='Union of all exact dailyTOP10 memberships is acquisition optimization, not a condition on later membership for any entry. Missing original issuer identity remains reserved; no promotion of current ticker-CIK to historical identity.',
        event_novelty='First SEC release per issuer/explicit fiscal period in complete bounded window; worldwide first IR not certified. An older repeat outside window or unparsed release remains a reserve.',
        limits=dict(max_requests=400,max_total_bytes=500*1024*1024,max_document_bytes=20*1024*1024,
            max_metadata_bytes=5*1024*1024,interval_seconds=.5,timeout_seconds=25,max_seconds=1200),
        public='Official SEC only; identified user agent, verified TLS, <=2requests/s, one attempt perURL, stop403/429, no redirects/challenge bypass. Reuse previously archived successful bodies with original receipts.',
        sql=False,paid_api_calls=0,llm_calls=0,training=False,pnl=False,orders=False,production_changes=False,
        price_outcomes=False,minimum_independent_history_met=False)
    atomic_json(root/'protocol.json',p)
    atomic_json(root/'inputs-ready.json',dict(files={n:digest(root/n) for n in ['consensus-candidates.parquet','q1-top10.parquet']}))
    return p


class ReusingFetcher(Fetcher):
    def __init__(self,root,p):
        super().__init__(root,p)
        self.cache={}
        for receipt in (OLD/'http').glob('*.json'):
            m=READ(receipt)
            if m.get('status')=='OK':self.cache[m['url']]=(OLD,m)

    def get(self,url,metadata=False):
        key=hashlib.sha256(url.encode()).hexdigest()
        if not (self.root/'http'/f'{key}.json').exists() and url in self.cache:
            parent,m=self.cache[url];path=parent/m['file']
            if digest(path)!=m['sha256']:raise ValueError('Cached source changed')
            if self.total+path.stat().st_size>self.p['limits']['max_total_bytes']:
                raise AccessStopped('BOUNDED_ACQUISITION_LIMIT')
            filename=f'http/{key}.body';(self.root/filename).write_bytes(path.read_bytes())
            receipt=dict(m,file=filename,reused_from=str(path),reused_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(self.root/'http'/f'{key}.json',receipt)
            self.total+=path.stat().st_size;self.calls+=1
        return super().get(url,metadata=metadata)


def metadata(root):
    p=prepare(root)
    if (root/'metadata.json').exists():raise ValueError('Immutable metadata')
    client=ReusingFetcher(root,p);rows=[];stop=None
    try:
        for index,(symbol,ciks) in enumerate(p['identities'].items(),1):
            item=dict(symbol=symbol,ciks=ciks,complete=False,rows=[])
            if len(ciks)!=1:
                item['reason']='CIK_UNKNOWN_OR_AMBIGUOUS';rows.append(item);continue
            cik=ciks[0];body,receipt=client.get(f'https://data.sec.gov/submissions/CIK{cik}.json',metadata=True)
            if body is None:
                item['reason']='SUBMISSIONS_UNAVAILABLE';rows.append(item);continue
            obj=json.loads(body)
            if str(obj['cik']).zfill(10)!=cik:raise ValueError('Issuer mismatch')
            filings=metadata_rows(obj);complete=True
            low=pd.Timestamp('2023-12-20') if symbol in p['q1_symbols'] else pd.Timestamp('2025-01-01')
            high=pd.Timestamp('2026-10-19') if symbol in p['consensus_symbols'] else pd.Timestamp('2024-03-31')
            for file in obj.get('filings',{}).get('files',[]):
                if pd.Timestamp(file['filingTo'])<low or pd.Timestamp(file['filingFrom'])>high:continue
                body2,_=client.get('https://data.sec.gov/submissions/'+file['name'],metadata=True)
                if body2 is None:complete=False;continue
                filings+=metadata_rows(json.loads(body2))
            unique={}
            for row in filings:
                accession=row['accessionNumber']
                if accession in unique and unique[accession]!=row:raise ValueError('Conflicting metadata')
                unique[accession]=row
            item.update(cik=cik,name=obj.get('name'),current_tickers=obj.get('tickers'),
                fiscal_year_end=obj.get('fiscalYearEnd'),complete=complete,
                rows=[r for r in unique.values() if low<=pd.Timestamp(r['filingDate'])<=high],receipt=receipt)
            rows.append(item)
            atomic_json(root/'progress.json',dict(phase='METADATA',completed=index,total=len(p['identities']),acquisitions=client.calls,bytes=client.total))
            print('Metadata',index,'/',len(p['identities']),symbol,flush=True)
    except AccessStopped as exc:stop=str(exc)
    finally:client.close()
    atomic_json(root/'metadata.json',dict(status='COMPLETE' if not stop and len(rows)==len(p['identities']) else 'INCOMPLETE',stop=stop,issuers=rows,
        files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


def documents(root):
    p=prepare(root);d=READ(root/'metadata.json');verify_hashes(root,d['files'])
    if (root/'documents.json').exists():raise ValueError('Immutable documents')
    candidates=pd.read_parquet(root/'consensus-candidates.parquet')
    indexes={i['symbol']:i for i in d['issuers']};requests={};consensus=[];events=[]
    schedule=mcal.get_calendar('NYSE').schedule(start_date='2023-12-01',end_date='2024-04-08')
    top=pd.read_parquet(root/'q1-top10.parquet');membership=set(zip(top.symbol,top.date))
    for symbol in p['consensus_symbols']:
        item=indexes.get(symbol,{});c=candidates[candidates.symbol.eq(symbol)].iloc[0]
        cutoff=pd.Timestamp(c.prior_entry_open_utc)
        prior=[r for r in item.get('rows',[]) if acceptance(r.get('acceptanceDateTime')) is not None and acceptance(r['acceptanceDateTime'])<cutoff]
        financial=sorted([r for r in prior if r['form'] in ('10-Q','10-K','20-F')],key=lambda r:r['acceptanceDateTime'],reverse=True)[:1]
        releases=sorted([r for r in prior if candidate_event(r)],key=lambda r:r['acceptanceDateTime'],reverse=True)
        # Foreign 6-K latest material report is not necessarily earnings; bounded
        # latest three are candidates, not silently certified financial reports.
        release=releases[:3] if item.get('cik') and not financial else releases[:1]
        links=[]
        for row in financial+release:
            key=(item['cik'],row['accessionNumber']);requests[key]=row;links.append(key[1])
        consensus.append(dict(symbol=symbol,metadata_complete=item.get('complete',False),accessions=links))
    for symbol in p['q1_symbols']:
        item=indexes.get(symbol,{})
        for row in item.get('rows',[]):
            if not '2023-12-20'<=row['filingDate']<='2024-03-31' or not candidate_event(row):continue
            key=(item['cik'],row['accessionNumber']);requests[key]=row
            reaction=reaction_day(row.get('acceptanceDateTime'),schedule)
            events.append(dict(symbol=symbol,cik=key[0],accession=key[1],metadata=row,
                reaction_date=str(reaction)[:10] if reaction is not None else None,
                in_q1_top10=(symbol,reaction) in membership,metadata_complete=item.get('complete',False)))
    atomic_json(root/'document-plan.json',dict(requests=[dict(cik=k[0],accession=k[1],metadata=v) for k,v in requests.items()],consensus=consensus,events=events))
    client=ReusingFetcher(root,p);downloaded=[];stop=d.get('stop')
    try:
        if not stop:
            for index,((cik,acc),row) in enumerate(sorted(requests.items()),1):
                body,receipt=client.get(document_url(cik,acc))
                downloaded.append(dict(cik=cik,accession=acc,metadata=row,receipt=receipt))
                atomic_json(root/'progress.json',dict(phase='DOCUMENTS',completed=index,total=len(requests),acquisitions=client.calls,bytes=client.total))
                print('Document',index,'/',len(requests),acc,flush=True)
    except AccessStopped as exc:stop=str(exc)
    finally:client.close()
    atomic_json(root/'documents.json',dict(status='COMPLETE' if not stop and len(downloaded)==len(requests) else 'INCOMPLETE',stop=stop,documents=downloaded,
        files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


def extract(root):
    p=prepare(root);d=READ(root/'documents.json');verify_hashes(root,d['files'])
    if (root/'extraction.json').exists():raise ValueError('Immutable extraction')
    plan=READ(root/'document-plan.json');byid={r['accession']:r for r in d['documents']};cache={};results=[]
    def body(acc):
        if acc not in cache:
            record=byid.get(acc,{}).get('receipt',{})
            cache[acc]=(root/record['file']).read_text(encoding='utf-8',errors='replace') if record.get('status')=='OK' else None
        return cache[acc]
    candidates=pd.read_parquet(root/'consensus-candidates.parquet')
    for link in plan['consensus']:
        c=candidates[candidates.symbol.eq(link['symbol'])].iloc[0];currencies=[];periods=[]
        for acc in link['accessions']:
            b=body(acc)
            if b is None:continue
            currency=inline_currencies(b)
            if currency['currency']:currencies.append(dict(accession=acc,**currency))
            for typ,part in primary_parts(b)+exhibits(b):
                text=visible(part)
                for q in quarter_dates(text,prospective=True):
                    if same_month_anchor(q['end'],c.fiscal_anchor):
                        periods.append(dict(accession=acc,form=typ,**q))
        unique=sorted({x['currency'] for x in currencies})
        results.append(dict(symbol=link['symbol'],oracle_rank=int(c.oracle_rank),anchor=c.fiscal_anchor,
            currency_candidate=unique[0] if len(unique)==1 else None,currency_proofs=currencies,
            period_candidates=periods,metadata_complete=link['metadata_complete'],
            semantic_qualified=False,live_admission=False))
    announcements=[]
    for event in plan['events']:
        b=body(event['accession']);parts=exhibits(b) if b else []
        records=[]
        for typ,part in parts:
            text=visible(part)
            if not re.search(r'financial results|quarter.{0,40}results|results.{0,40}quarter',text[:5000],re.I):continue
            periods=[x for x in quarter_dates(text) if x['end']<=event['metadata']['filingDate']]
            if not periods:continue
            latest=max(x['end'] for x in periods)
            quartet=standalone_tables(b,int(latest[:4]))
            records.append(dict(exhibit=typ,period_end=latest,period_quotes=[x for x in periods if x['end']==latest],**quartet))
        announcements.append(dict(**event,downloaded=b is not None,release_records=records,
            first_worldwide_release_verified=False,historical_identity_verified=False))
    atomic_json(root/'extraction.json',dict(consensus=results,announcements=announcements,
        status='ROUTING_EVIDENCE_NOT_AUTOMATIC_SEMANTIC_APPROVAL',
        files={n:digest(root/n) for n in ['protocol.json','inputs-ready.json','metadata.json','document-plan.json','documents.json']}))
    print('Extracted',len(results),'consensus issuers;',len(announcements),'earnings filing candidates',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','metadata','documents','extract'],required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    globals()[args.phase](args.output)
