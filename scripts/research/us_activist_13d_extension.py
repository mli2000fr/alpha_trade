"""Bounded 2024 expansion, with an outcome-blind non-current-universe probe.

Official SEC originals only; no SQL, model, broker or LLM writes/calls. The old
sealed pilot is not changed. Semantic admission must be frozen before replay.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import io
import os
from pathlib import Path
import re
import time
from urllib.parse import urlsplit

from common.public_data_http import verified_session
from scripts.research.us_activist_13d_pilot import (
    READ, INITIAL, INDEX_ROOT, MAPPING, UNIVERSE, Stopped, parse,
)
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

PILOT = Path('artifacts/research/us_activist_13d/20261020-v1')


def allowed(url):
    u = urlsplit(url)
    return u.scheme == 'https' and u.netloc == 'www.sec.gov' and not u.query and not u.fragment and bool(
        re.fullmatch(r'/Archives/edgar/(?:full-index/202[45]/QTR[1-4]/master.gz|data/\d+/(?:\d{10}-\d{2}-\d{6}\.txt|\d{18}/[A-Za-z0-9_.-]+\.html?))', u.path))


class Client:
    def __init__(self, root, limits):
        ua = os.getenv('SEC_EDGAR_USER_AGENT', '').strip()
        if '@' not in ua or 'example.com' in ua:
            raise Stopped('REAL_IDENTIFIED_SEC_CONTACT_REQUIRED')
        self.root, self.limits = root, limits
        self.session = verified_session()
        self.session.headers['User-Agent'] = ua
        receipts = [READ(p) for p in (root/'http').glob('*.json')]
        self.calls = sum(not r.get('reused_from') for r in receipts)
        self.bytes = sum(r.get('streamed_bytes', 0) for r in receipts if not r.get('reused_from'))
        self.last, self.started = 0., time.monotonic()

    def get(self, url):
        if not allowed(url):
            raise ValueError('URL outside bounded official SEC allowlist')
        key = hashlib.sha256(url.encode()).hexdigest()
        receipt_file = self.root/'http'/f'{key}.json'
        if receipt_file.exists():
            r = READ(receipt_file)
            if r.get('http_status') in [403, 429] or r['status'] == 'ACCESS_CHALLENGE':
                raise Stopped('PREVIOUS_SEC_REFUSAL_NO_RETRY')
            if r['status'] == 'OK':
                p = self.root/r['file']
                if digest(p) != r['sha256']:
                    raise ValueError('Archived source changed')
                return p.read_bytes(), r
            return None, r
        b = self.limits
        if self.calls >= b['requests'] or self.bytes >= b['total_bytes'] or time.monotonic()-self.started > b['max_seconds']:
            raise Stopped('BOUNDED_ACQUISITION_LIMIT')
        time.sleep(max(0, b['interval_seconds']-(time.monotonic()-self.last)))
        self.last = time.monotonic()
        self.calls += 1
        r = dict(url=url, retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                 streamed_bytes=0, status='UNFINISHED', attempts=1)
        body, stop = None, None
        try:
            with self.session.get(url, timeout=(10, 30), stream=True, allow_redirects=False) as response:
                r['http_status'] = response.status_code
                if response.status_code in [403, 429]:
                    r['status'], stop = 'ACCESS_REFUSED', 'SEC_REFUSAL_NO_BYPASS'
                elif response.status_code != 200:
                    r['status'] = 'HTTP_UNAVAILABLE_NO_RETRY'
                else:
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        r['streamed_bytes'] += len(chunk)
                        self.bytes += len(chunk)
                        data.extend(chunk)
                        if self.bytes > b['total_bytes']:
                            r['status'], stop = 'TOTAL_BYTES_LIMIT', 'BOUNDED_ACQUISITION_LIMIT'
                            break
                        if len(data) > b['document_bytes']:
                            r['status'] = 'DOCUMENT_TOO_LARGE'
                            break
                    else:
                        if any(t in bytes(data[:3500]).lower() for t in [b'access denied', b'undeclared automated tool']):
                            r['status'], stop = 'ACCESS_CHALLENGE', 'SEC_REFUSAL_NO_BYPASS'
                        else:
                            body = bytes(data)
                            target = self.root/'http'/f'{key}.body'
                            target.write_bytes(body)
                            r.update(status='OK', file=str(target.relative_to(self.root)), sha256=digest(target), bytes=len(body))
        except Exception as exc:
            r.update(status='TECHNICAL_FAILURE_NO_RETRY', error_type=type(exc).__name__)
        atomic_json(receipt_file, r)
        if stop:
            raise Stopped(stop)
        return body, r


def reuse(root, receipt, source_root):
    """Preserve retrieval timestamp and actual original URL; no synthetic receipt."""
    if receipt['status'] != 'OK':
        return
    source = source_root/receipt['file']
    if digest(source) != receipt['sha256']:
        raise ValueError('Reused source changed')
    key = hashlib.sha256(receipt['url'].encode()).hexdigest()
    target = root/'http'/f'{key}.body'
    target.write_bytes(source.read_bytes())
    atomic_json(root/'http'/f'{key}.json', dict(receipt, file=str(target.relative_to(root)), reused_from=str(source_root)))


def prepare(root):
    if (root/'protocol.json').exists():
        p = READ(root/'protocol.json')
        verify_hashes(Path('.'), p['sources'])
        return p
    if root.exists():
        raise ValueError('Fresh extension directory required')
    root.mkdir(parents=True)
    (root/'http').mkdir()
    files = [Path(__file__), Path('tests/test_us_activist_13d_extension.py'), UNIVERSE, MAPPING,
             Path('scripts/research/us_activist_13d_pilot.py'),
             Path('scripts/research/us_activist_13d_review.py'),
             Path('scripts/research/us_activist_13d_replay.py'), PILOT/'documents.json', INDEX_ROOT/'index.json']
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources={str(f): digest(f) for f in files},
             event_year=2024, index_years=[2024, 2025],
             selection='All distinct initial13D in full2024 indexes with ANY indexedCIK in current1790mapping. '
                       'Plus10 per quarter outside that index route, smallest SHA256(accession), before reading originals/prices. '
                       'Dedup cofilers by accession first. Noncurrent probe is NOT a complete delisted cohort or historical universe.',
             noncurrent_probe_per_quarter=10,
             semantics='Same as sealedpilot: explicit current boardnomination/public strategic/operational/capital intervention. '
                       'Generic may/reservesrights, investmentonly, financing, donation, mergercontractualrights excluded. '
                       'SUBJECT COMPANY determines issuer, never filer. Governanceonly separate. All decisions cited and frozen before prices.',
             timing='Next full NYSE open strictly after filingdate and after SECacceptance. No assertion of firstworldwideannouncement. '
                    'Block sameissuer60sessions before price checks, including unknowns. PriorQ1 pilot outcomes already observed: '
                    'Q2-Q4 are extension, not pristine preregistered externalvalidation;2025 indexes only coverage planning.',
             economic=dict(horizons=[20,60], entry_session_included=True, notional_usd=1000.,
                           commission_per_order_usd=1., spread_bps_per_leg=5., slippage_bps_per_leg=5., stress_total_bps_per_leg=25.,
                           long_only=True, no_tp_sl_trailing_or_leverage=True, portfolio_pnl=False),
             prices='Only after semanticfreeze, existing adjusted researchbars. Historicalticker proof from originaldocument/earlierannual. '
                    'Missingidentity/price/action remainsUNKNOWN, retained in denominator. No survivor/fullmarket claim; no replacement.',
             limits=dict(requests=240,total_bytes=250*1024*1024,document_bytes=12*1024*1024,interval_seconds=.6,max_seconds=1800),
             no_sql=True,no_training=True,no_llm=True,no_orders=True,no_production_changes=True)
    atomic_json(root/'protocol.json', p)
    old = READ(INDEX_ROOT/'index.json')
    reuse(root, old['receipt'], INDEX_ROOT)
    for doc in READ(PILOT/'documents.json')['documents']:
        reuse(root, doc['receipt'], PILOT)
    return p


def parse_quarter(body, year, quarter, cap=80*1024*1024):
    with gzip.GzipFile(fileobj=io.BytesIO(body)) as stream:
        expanded = stream.read(cap+1)
    if len(expanded) > cap:
        raise ValueError('Expanded index size limit')
    text = expanded.decode('latin-1')
    if 'CIK|Company Name|Form Type|Date Filed|Filename' not in text:
        raise ValueError('Unexpected quarter index format')
    rows = []
    for line in text.splitlines():
        fields = line.split('|')
        if len(fields) != 5 or not fields[0].isdigit():
            continue
        cik, name, form, day, path = fields
        dt = datetime.strptime(day, '%Y-%m-%d')
        if dt.year != year or (dt.month-1)//3+1 != quarter:
            raise ValueError('Row outside prescribed quarter')
        if not re.fullmatch(r'edgar/data/\d+/\d{10}-\d{2}-\d{6}\.txt', path):
            raise ValueError('Unexpected filing path')
        rows.append(dict(cik=cik.zfill(10),name=name,form=form,filed=day,path=path,accession=path.rsplit('/',1)[1][:-4]))
    if not rows:
        raise ValueError('Empty index is not success')
    return rows


def distinct(rows, mapping):
    result = {}
    for r in rows:
        if r['form'] not in INITIAL:
            continue
        if r['accession'] not in result:
            result[r['accession']] = dict(accession=r['accession'],filed=r['filed'],quarter=(int(r['filed'][5:7])-1)//3+1,
                                           indexed_ciks=[],paths=[],index_names=[],mapped_symbols=[])
        obj = result[r['accession']]
        if obj['filed'] != r['filed']:
            raise ValueError('Conflicting accession dates')
        for key, values in [('indexed_ciks',[r['cik']]),('paths',[r['path']]),('index_names',[r['name']]),('mapped_symbols',mapping.get(r['cik'],[]))]:
            obj[key] = sorted(set(obj[key])|set(values))
    return sorted(result.values(),key=lambda r:(r['filed'],r['accession']))


def choose(rows, per_quarter):
    current = [dict(r,cohort='CURRENT_UNIVERSE_INDEX_ROUTE') for r in rows if r['mapped_symbols']]
    probe = []
    for q in range(1,5):
        outside = [r for r in rows if r['quarter']==q and not r['mapped_symbols']]
        outside.sort(key=lambda r:hashlib.sha256(r['accession'].encode()).hexdigest())
        probe += [dict(r,cohort='NONCURRENT_INDEX_ROUTE_HASH_PROBE') for r in outside[:per_quarter]]
    return sorted(current+probe,key=lambda r:(r['filed'],r['accession']))


def indexes(root):
    p = prepare(root)
    if (root/'selection.json').exists():
        raise ValueError('Immutable index selection already exists')
    universe = {s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s}
    mapping = {}
    for r in READ(MAPPING).values():
        if r['ticker'] in universe:
            mapping.setdefault(str(r['cik_str']).zfill(10),set()).add(r['ticker'])
    client = Client(root,p['limits'])
    all2024, summaries, stop = [], [], None
    try:
        for year in p['index_years']:
            for q in range(1,5):
                url = f'https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{q}/master.gz'
                body, receipt = client.get(url)
                if body is None:
                    raise Stopped('INDEX_UNAVAILABLE')
                rows = parse_quarter(body,year,q)
                unique = distinct(rows,mapping)
                summaries.append(dict(year=year,quarter=q,index_rows=len(rows),initial_rows=sum(r['form'] in INITIAL for r in rows),
                                      initial_accessions=len(unique),current_route_accessions=sum(bool(r['mapped_symbols']) for r in unique),receipt=receipt))
                if year==2024:
                    all2024.extend(rows)
                print(year,q,len(unique),'initial accessions',summaries[-1]['current_route_accessions'],'current route',flush=True)
    except Stopped as exc:
        stop = str(exc)
    finally:
        client.session.close()
    selected = choose(distinct(all2024,mapping),p['noncurrent_probe_per_quarter']) if sum(x['year']==2024 for x in summaries)==4 else []
    atomic_json(root/'selection.json',dict(status='FROZEN_WITHOUT_PRICE_OUTCOMES' if selected else 'INCOMPLETE',stop=stop,
                universe_count=len(universe),indexes=summaries,selected=selected,selected_counts=dict(Counter(r['cohort'] for r in selected)),
                selected_files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')},requests=client.calls,streamed_bytes=client.bytes))
    print('Selected',len(selected),Counter(r['cohort'] for r in selected),flush=True)


def acquire(root):
    p = prepare(root)
    chosen = READ(root/'selection.json')
    verify_hashes(root,chosen['selected_files'])
    if chosen['status']!='FROZEN_WITHOUT_PRICE_OUTCOMES' or (root/'documents.json').exists():
        raise ValueError('Frozen selection and fresh capture required')
    reused = {d['selection']['accession']:d['receipt']['url'] for d in READ(PILOT/'documents.json')['documents'] if d['receipt']['status']=='OK'}
    client = Client(root,p['limits'])
    done, stop = [], None
    try:
        for i,row in enumerate(chosen['selected'],1):
            url = reused.get(row['accession'],'https://www.sec.gov/Archives/'+row['paths'][0])
            _, receipt = client.get(url)
            done.append(dict(selection=row,receipt=receipt))
            atomic_json(root/'progress.json',dict(status='CAPTURING',completed=len(done),total=len(chosen['selected'])))
            print(i,'/',len(chosen['selected']),row['filed'],row['mapped_symbols'],receipt['status'],flush=True)
    except Stopped as exc:
        stop=str(exc)
    finally:
        client.session.close()
    atomic_json(root/'documents.json',dict(status='COMPLETE_ATTEMPTS' if len(done)==len(chosen['selected']) and not stop else 'INCOMPLETE',
                stop=stop,documents=done,requests=client.calls,streamed_bytes=client.bytes,
                files={str(f.relative_to(root)):digest(f) for f in (root/'http').glob('*')}))


def extract(root):
    prepare(root)
    docs = READ(root/'documents.json')
    verify_hashes(root,docs['files'])
    if (root/'extraction.json').exists():
        raise ValueError('Immutable extraction')
    folder=root/'review'
    folder.mkdir()
    universe = {s for s in re.split(r'[,;\s]+',UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s}
    allmapping = {}
    for obj in READ(MAPPING).values():
        allmapping.setdefault(str(obj['cik_str']).zfill(10),set()).add(obj['ticker'])
    rows=[]
    for doc in docs['documents']:
        row=dict(**doc['selection'],receipt=doc['receipt'],status=doc['receipt']['status'])
        if row['status']=='OK':
            try:
                obj=parse((root/row['receipt']['file']).read_bytes())
                file=folder/f"{row['accession']}.json"
                atomic_json(file,obj)
                symbols=sorted(allmapping.get(obj['subject_cik'],set()))
                current=sorted(set(symbols)&universe)
                row.update(status='READY_REVIEW',review_file=str(file.relative_to(root)),subject_cik=obj['subject_cik'],
                           subject_name=obj['subject_name'],current_mapping_symbols=symbols,current_tradable_symbols=current,
                           indexed_cik_includes_subject=obj['subject_cik'] in row['indexed_ciks'],item4_chars=len(obj['item4'] or ''))
            except ValueError as exc:
                row.update(status='RESERVED',reason=str(exc))
        rows.append(row)
    atomic_json(root/'extraction.json',dict(status='EXTRACTED_NO_PRICE_OUTCOMES',rows=rows,counts=dict(Counter(r['status'] for r in rows)),
                files={str(f.relative_to(root)):digest(f) for f in folder.glob('*')},no_prices_read=True))
    print(Counter(r['status'] for r in rows),'current trueissuer',sum(bool(r.get('current_tradable_symbols')) for r in rows),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--phase',choices=['indexes','acquire','extract'],required=True)
    args=parser.parse_args()
    globals()[args.phase](args.output)
