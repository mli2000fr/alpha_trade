"""Bounded annual buyback feasibility, offline first, no SQL/model/order writes.

Cash repurchases minus cash issuance are a proxy, NOT net share retirement:
stock compensation/noncash issuance and acquisitions must also be reviewed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_public_information_compact import Client, LimitStopped

UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
MAPPING = Path('artifacts/sec_cache/company_tickers.json')
CACHE = Path('artifacts/sec_cache/companyfacts')
TAGS = {
    'repurchases': 'PaymentsForRepurchaseOfCommonStock',
    'issuance_cash': 'ProceedsFromStockIssuance',
    'common_issuance_cash': 'ProceedsFromIssuanceOfCommonStock',
    'option_exercises_cash': 'ProceedsFromStockOptionsExercised',
    'treasury_sale_cash': 'ProceedsFromSaleOfTreasuryStock',
    'operating_cash': 'NetCashProvidedByUsedInOperatingActivities',
    'capex': 'PaymentsToAcquirePropertyPlantAndEquipment',
    'stock_compensation': 'ShareBasedCompensation',
    'cash_balance': 'CashAndCashEquivalentsAtCarryingValue',
    'shares': 'CommonStockSharesOutstanding',
}
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))


def sample_symbols(symbols, n=20):
    return sorted(set(symbols), key=lambda s: hashlib.sha256(
        ('BUYBACK-PILOT-20261020|' + s).encode()).hexdigest())[:n]


def annual(row):
    try:
        start, end = pd.Timestamp(row['start']), pd.Timestamp(row['end'])
        return (350 <= (end-start).days+1 <= 378 and row.get('form') == '10-K'
                and pd.Timestamp(row['filed']) >= end)
    except (KeyError, ValueError, TypeError):
        return False


def unique(rows):
    if not rows:
        return None, 'MISSING_NOT_ZERO'
    try:
        values = {Decimal(str(r['val'])) for r in rows}
    except (InvalidOperation, KeyError):
        return None, 'INVALID'
    if len(values) != 1 or not next(iter(values)).is_finite():
        return None, 'CONFLICTING_OR_NONFINITE'
    return float(next(iter(values))), 'OK'


def select_filing(payload):
    """First 2024 original annual accession, regardless of financial values."""
    rows = []
    for namespace in payload.get('facts', {}).values():
        for obj in namespace.values():
            for entries in obj.get('units', {}).values():
                rows.extend(r for r in entries if r.get('form') == '10-K'
                            and '2024-01-01' <= r.get('filed', '') <= '2024-12-31'
                            and r.get('accn') and annual(r))
    if not rows:
        return None
    key = min((r['filed'], r['accn']) for r in rows)
    chosen = [r for r in rows if (r['filed'], r['accn']) == key]
    end = max(r['end'] for r in chosen)
    starts = sorted({r['start'] for r in chosen if r['end'] == end})
    return dict(filed=key[0], accession=key[1], end=end, starts=starts)


def extract(payload, filing):
    out = {}; evidence = {}; statuses = {}
    if len(filing['starts']) != 1:
        return dict(reason='ANNUAL_INTERVAL_AMBIGUOUS', values={}, evidence={}, statuses={})
    start, end = filing['starts'][0], filing['end']
    for metric, tag in TAGS.items():
        unit = 'shares' if metric == 'shares' else 'USD'
        all_rows = payload.get('facts', {}).get('us-gaap', {}).get(tag, {}).get('units', {}).get(unit, [])
        rows = [r for r in all_rows if r.get('accn') == filing['accession']
                and r.get('filed') == filing['filed'] and r.get('end') == end
                and (not r.get('start') if metric in ('shares', 'cash_balance') else r.get('start') == start)]
        value, status = unique(rows); out[metric] = value; statuses[metric] = status
        evidence[metric] = [dict(r, tag=tag, unit=unit) for r in rows]
        if metric == 'shares':
            prior = [r for r in all_rows if r.get('accn') == filing['accession']
                     and r.get('filed') == filing['filed'] and not r.get('start')
                     and 350 <= (pd.Timestamp(end)-pd.Timestamp(r['end'])).days <= 378]
            old, why = unique(prior); out['prior_shares'] = old; statuses['prior_shares'] = why
            evidence['prior_shares'] = [dict(r, tag=tag, unit=unit) for r in prior]
    # Never sum overlapping issuance tags. A total and a common-stock component
    # are not interchangeable, particularly when preferred stock is issued.
    out['free_cash_flow_proxy'] = (out['operating_cash']-out['capex']
        if out['operating_cash'] is not None and out['capex'] is not None else None)
    out['shares_change'] = (out['shares']/out['prior_shares']-1
        if out['shares'] is not None and out['prior_shares'] is not None
        and out['prior_shares'] > 0 else None)
    return dict(reason=None, start=start, end=end, values=out, evidence=evidence, statuses=statuses)


def prepare(root):
    if (root/'protocol.json').exists():
        p = READ(root/'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    if root.exists():
        raise ValueError('Fresh output required')
    symbols = [s for s in re.split(r'[,;\s]+', UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s]
    mapping = {}
    for r in READ(MAPPING).values():
        mapping.setdefault(r['ticker'], set()).add(str(r['cik_str']).zfill(10))
    cohort = []; inputs = [Path(__file__), Path('tests/test_us_buyback_pilot.py'), UNIVERSE, MAPPING,
        Path('scripts/research/us_public_information_compact.py')]
    for symbol in sample_symbols(symbols):
        ciks = sorted(mapping.get(symbol, set()))
        file = CACHE/f'CIK{ciks[0]}.json' if len(ciks) == 1 else None
        present = file is not None and file.exists()
        cohort.append(dict(symbol=symbol, current_ciks=ciks, facts_path=str(file) if present else None))
        if present: inputs.append(file)
    root.mkdir(parents=True); (root/'http').mkdir()
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(f): digest(f) for f in inputs}, cohort=cohort,
        hypothesis='Executed net share reduction with positive financing capacity may identify favorable future returns, not guaranteed direction.',
        sample='20 current tradable symbols sorted by SHA256(BUYBACK-PILOT-20261020|symbol), BEFORE values or future prices; no replacement. Current universe/mapping survivor bias explicit.',
        observations='First original 10-K filed in calendar2024 per symbol using cached facts. Annual350..378days, original accession + exact start/end + USD. Foreign20-F/40-F/no10K reserved, never treated as zero.',
        accounting='Missing issuance is NOT0. Cash issuance tags overlap, never summed or assumed exhaustive. SBC/noncash/acquisition changes and share classes require original-document review. Repurchase authority is NOT execution; cash proxy NOT net retirement.',
        rule='Exploratory candidate only: positive executed common buybacks, actual total common shares down YoY, positive CFO-capex, reviewed original issuance/employee-stock coverage and no unexplained classes/identity/split/leverage. No threshold fitted.',
        temporal='Next full NYSE open strictly after filing date, no invented filing hour. Original publication may precede10K. Source retrieved now != historical local receipt. No claim of novel announcement.',
        comparison='If qualified, H20/H60 open-to-close total-return proxy, fixed10bps per side; sector/cap matched controls only with historical as-of metadata. TOP10 membership from frozen concurrent scores only. No replacement of missing controls or future prices.',
        gate='No performance before source/identity/cash-issuance/share-class/leverage gates. At least30qualified independent issuer observations + matched controls for association pilot;20sample feasibility cannot establish efficacy. No ML/production promotion. Report a real gate failure, not a negative efficacy result.',
        limits=dict(max_requests=40, max_total_bytes=120*1024*1024,
                    max_document_bytes=8*1024*1024, interval_seconds=.6),
        capture='First8 selected annual filings, in frozen cohort order, irrespective of values. Index plus primary10K only; no retries, stop403/429/challenge, TLS and identified SEC agent, all streamed bytes counted.',
        no_training=True, no_llm=True, no_sql=True, no_orders=True, no_production_changes=True)
    atomic_json(root/'protocol.json', p); return p


def build(root):
    p = prepare(root)
    if (root/'extraction.json').exists(): raise ValueError('Immutable extraction')
    cases = []
    for item in p['cohort']:
        case = dict(item, filing=None, extraction=None, source_identity_match=False)
        if item['facts_path']:
            data = READ(item['facts_path'])
            case['source_identity_match'] = str(data.get('cik')).zfill(10) == item['current_ciks'][0]
            case['entity_name'] = data.get('entityName'); case['filing'] = select_filing(data)
            if case['filing']: case['extraction'] = extract(data, case['filing'])
        cases.append(case)
    atomic_json(root/'extraction.json', dict(cases=cases,
        annual_candidates=sum(r['filing'] is not None for r in cases),
        selected_documents=[r['symbol'] for r in cases if r['filing']][:8],
        fully_qualified=0, price_outcomes_read=False))
    print('Selected', len(cases), 'annuals', sum(r['filing'] is not None for r in cases), flush=True)


def primary_from_index(body):
    soup = BeautifulSoup(body, 'html.parser'); matches = []
    for tr in soup.find_all('tr'):
        td = tr.find_all('td')
        if len(td) >= 4 and td[3].get_text(strip=True) == '10-K':
            a = td[2].find('a', href=True)
            if a:
                # Use displayed filename, not ixviewer route.
                name = a.get_text(strip=True)
                if re.fullmatch(r'[A-Za-z0-9_.-]+\.html?', name): matches.append(name)
    if len(set(matches)) != 1: raise ValueError('Missing or ambiguous original10K')
    return matches[0]


def acquire(root):
    p = prepare(root); extraction = READ(root/'extraction.json')
    if (root/'documents.json').exists(): raise ValueError('Immutable acquisition')
    client = Client(root, p); docs = []; stop = None
    try:
        for case in extraction['cases']:
            if case['symbol'] not in extraction['selected_documents']: continue
            filing = case['filing']; acc = filing['accession']; cik = case['current_ciks'][0]
            base = f'https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace("-", "")}/'
            # The shared client permits this official directory and basename.
            body, index_receipt = client.get(base+acc+'-index.html')
            row = dict(symbol=case['symbol'], accession=acc, index_receipt=index_receipt)
            if body is not None:
                try:
                    name = primary_from_index(body); _, receipt = client.get(base+name)
                    row.update(primary=name, receipt=receipt)
                except ValueError as exc: row['parse_error'] = str(exc)
            docs.append(row)
            atomic_json(root/'progress.json', dict(status='RUNNING', documents=len(docs), total=len(extraction['selected_documents'])))
            print(case['symbol'], row.get('receipt', {}).get('status', 'NO_PRIMARY'), flush=True)
    except LimitStopped as exc: stop = str(exc)
    finally: client.http.close()
    atomic_json(root/'documents.json', dict(status='COMPLETE_ATTEMPTS' if stop is None else 'INCOMPLETE',
        stop=stop, documents=docs, requests=client.calls, streamed_bytes=client.bytes,
        files={str(f.relative_to(root)): digest(f) for f in (root/'http').glob('*')}))


def ix_number(node):
    text = node.get_text('', strip=True).replace(',', '').replace('\u00a0', '').replace(' ', '')
    if text in ('—', '–', '-', ''): text = '0'
    if text.startswith('(') and text.endswith(')'): text = '-'+text[1:-1]
    value = Decimal(text) * (Decimal(10) ** int(node.get('scale', '0')))
    if node.get('sign') == '-': value = -value
    if not value.is_finite(): raise ValueError('Nonfinite inline fact')
    return value


def original_facts(body, cik):
    """Undimensioned issuer contexts only; preserve instants and durations."""
    soup = BeautifulSoup(body, 'html.parser'); contexts = {}; units = {}; output = []
    for u in soup.find_all(lambda n: n.name.lower() in ('xbrli:unit', 'unit')):
        measures = [x.get_text(strip=True).split(':')[-1] for x in u.find_all(lambda n: n.name.lower().endswith('measure'))]
        units[u.get('id')] = measures[0] if len(measures) == 1 else None
    for c in soup.find_all(lambda n: n.name.lower() in ('xbrli:context', 'context')):
        def txt(suffix):
            n = c.find(lambda n: n.name.lower().split(':')[-1] == suffix)
            return n.get_text(strip=True) if n else None
        ident = txt('identifier')
        if not ident or ident.zfill(10) != cik: continue
        if c.find(lambda n: n.name.lower().split(':')[-1] in ('explicitmember', 'typedmember')): continue
        contexts[c.get('id')] = dict(start=txt('startdate'), end=txt('enddate') or txt('instant'))
    for n in soup.find_all(lambda n: n.name.lower() == 'ix:nonfraction'):
        name = n.get('name', '')
        if not name.startswith('us-gaap:') or name.split(':')[-1] not in TAGS.values(): continue
        ctx = contexts.get(n.get('contextref')); unit = units.get(n.get('unitref'))
        if not ctx or unit not in ('USD', 'shares'): continue
        try: val = ix_number(n)
        except (InvalidOperation, ValueError): continue
        output.append(dict(tag=name.split(':')[-1], unit=unit, **ctx, val=str(val)))
    return output


def corroborate(extraction, facts):
    checks = []
    for metric, rows in extraction['evidence'].items():
        for r in rows:
            matches = [f for f in facts if all(f.get(k) == r.get(k) for k in ('tag', 'unit', 'start', 'end'))]
            values = {Decimal(str(f['val'])) for f in matches}
            checks.append(dict(metric=metric, tag=r['tag'], start=r.get('start'), end=r['end'],
                cache_value=r['val'], original_values=sorted(str(v) for v in values),
                exact_match=values == {Decimal(str(r['val']))}))
    return checks


def audit(root):
    p = prepare(root); ext = READ(root/'extraction.json'); docs = READ(root/'documents.json')
    verify_hashes(root, docs['files'])
    if (root/'report.json').exists(): raise ValueError('Immutable report')
    bysymbol = {r['symbol']: r for r in ext['cases']}; reviews = []
    for doc in docs['documents']:
        receipt = doc.get('receipt', {})
        if receipt.get('status') != 'OK': continue
        case = bysymbol[doc['symbol']]; body = (root/receipt['file']).read_bytes()
        facts = original_facts(body, case['current_ciks'][0]); checks = corroborate(case['extraction'], facts)
        soup = BeautifulSoup(body, 'html.parser')
        for n in soup.find_all(lambda n: n.name.lower() in ('ix:header', 'ix:hidden', 'script', 'style')): n.decompose()
        text = ' '.join(soup.stripped_strings)
        snippets = []; seen = set()
        for m in re.finditer(r'repurchase|withholding|treasury stock|issuance of common|share-based compensation', text, re.I):
            a = max(0, m.start()-180); b = min(len(text), m.end()+400)
            if a//300 in seen: continue
            seen.add(a//300); snippets.append(text[a:b])
            if len(snippets) == 35: break
        review = dict(symbol=doc['symbol'], original_url=receipt['url'], facts=facts,
            checks=checks, matched=sum(c['exact_match'] for c in checks), total=len(checks), snippets=snippets,
            semantic_issuance_scope_qualified=False, share_classes_and_historical_identity_qualified=False,
            leverage_and_acquisition_scope_qualified=False, fully_qualified=False)
        atomic_json(root/f"review-{doc['symbol']}.json", review); reviews.append(review)
    counts = Counter()
    for c in ext['cases']:
        if not c['filing']: counts['NO_ORIGINAL_2024_10K_IN_CACHE'] += 1; continue
        ex = c['extraction']
        for metric in TAGS:
            counts[metric+'_'+ex['statuses'].get(metric, 'INTERVAL_AMBIGUOUS')] += 1
    result = dict(status='FEASIBILITY_COMPLETE_SEMANTIC_REVIEW_REQUIRED_NO_EFFICACY',
        selected_symbols=len(ext['cases']), annual_candidates=ext['annual_candidates'],
        original_documents=len(reviews), original_facts_checked=sum(r['total'] for r in reviews),
        original_exact_matches=sum(r['matched'] for r in reviews), counts=dict(counts),
        fully_qualified_events=0, eligible_matched_controls=0, price_outcomes_read=False,
        request_count=docs['requests'], streamed_bytes=docs['streamed_bytes'], stop=docs['stop'],
        reasons=['cash proceeds not automatically exhaustive of common-share issuance',
            'SBC/noncash issuance/share classes/splits/identity/leverage require issuer-level review',
            'annual historical source reconstructed now, not local historical receipt or first announcement',
            '20selectedissuers < frozen30issuerassociationgate; not a negative efficacy result'],
        no_sql=True, no_training=True, no_orders=True, no_llm=True,
        files={str(f.relative_to(root)): digest(f) for f in root.iterdir() if f.is_file() and f.name != 'progress.json'})
    atomic_json(root/'report.json', result)
    atomic_json(root/'progress.json', dict(status=result['status'], documents=len(reviews), total=8))
    print(json.dumps({k: result[k] for k in ('status', 'selected_symbols', 'annual_candidates', 'original_documents', 'original_facts_checked', 'original_exact_matches')}), flush=True)


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output', type=Path, required=True)
    a.add_argument('--phase', choices=['prepare', 'build', 'acquire', 'audit'], required=True)
    args = a.parse_args(); globals()[args.phase](args.output)
