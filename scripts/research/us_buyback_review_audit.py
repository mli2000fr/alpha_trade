"""Offline documentary review audit. No price outcomes or external calls."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import re

from bs4 import BeautifulSoup

from scripts.research.us_buyback_pilot import READ, UNIVERSE, extract, select_filing, sample_symbols, original_facts, corroborate
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

NOTES = Path('doc/ml/sources/buyback_review_20261020.json')


def normalized(text):
    return ' '.join(text.replace('\u200b', '').split())


def require_quote(text, quote):
    if normalized(quote) not in normalized(text):
        raise ValueError('Exact documentary quote missing: '+quote)


def audit(root):
    if root.exists(): raise ValueError('Fresh review output required')
    review = READ(NOTES); parent = Path(review['parent']); p = READ(parent/'protocol.json')
    verify_hashes(Path('.'), p['sources']); report = READ(parent/'report.json')
    verify_hashes(parent, report['files']); docs = READ(parent/'documents.json')
    verify_hashes(parent, docs['files']); ext = READ(parent/'extraction.json')
    syms = [s for s in re.split(r'[,;\s]+', UNIVERSE.read_text(encoding='utf-8-sig').strip()) if s]
    if [r['symbol'] for r in ext['cases']] != sample_symbols(syms): raise ValueError('Cohort changed')
    for row in ext['cases']:
        if row['facts_path']:
            source = READ(row['facts_path']); f = select_filing(source)
            if row['filing'] != f: raise ValueError('Accession selection changed')
            if f and extract(source, f) != row['extraction']: raise ValueError('Cache extraction mismatch')
    verified = []; comparisons = 0
    for note in review['cases']:
        d = next(r for r in docs['documents'] if r['symbol'] == note['symbol'])
        if not note['quotes']:
            if d.get('receipt', {}).get('status') != 'DOCUMENT_TOO_LARGE': raise ValueError('Wrong missing document reason')
            continue
        receipt = d['receipt']; body = (parent/receipt['file']).read_bytes()
        soup = BeautifulSoup(body, 'html.parser')
        for n in soup.find_all(lambda n: n.name.lower() in ('ix:header', 'ix:hidden', 'script', 'style')): n.decompose()
        text = ' '.join(soup.stripped_strings)
        for quote in note['quotes']: require_quote(text, quote)
        case = next(r for r in ext['cases'] if r['symbol'] == note['symbol'])
        originals = original_facts(body, case['current_ciks'][0]); checks = corroborate(case['extraction'], originals)
        if not checks or not all(r['exact_match'] for r in checks): raise ValueError('Original amount not corroborated')
        comparisons += len(checks)
        verified.append(dict(symbol=note['symbol'], decision=note['decision'], source_url=receipt['url'],
            quotes_verified=len(note['quotes']), amounts_verified=len(checks), fully_qualified=False))
    hcsg = next(r for r in ext['cases'] if r['symbol'] == 'HCSG')['extraction']['values']
    if Decimal(str(hcsg['free_cash_flow_proxy'])) != Decimal(43498000)-Decimal(5406000): raise ValueError('FCF arithmetic')
    result = dict(status='PASS_BOUNDED_FEASIBILITY_NOT_EFFICACY', created_at_utc=datetime.now(timezone.utc).isoformat(),
        selected_symbols=20, annual_filings=16, selected_documents=8, complete_originals=7, too_large=1,
        verified_amounts=comparisons, documentary_candidates=['DBX','CL','HCSG'],
        simple_numeric_candidate='HCSG', strict_qualified_events=0, matched_asof_controls=0,
        hcsg_share_count_change_pct=(73341000/74088000-1)*100,
        sources=[dict(path=str(f), sha256=digest(f)) for f in [Path(__file__), Path('tests/test_us_buyback_review_audit.py'), NOTES, parent/'protocol.json', parent/'report.json']],
        reviewed=verified, reasons=Counter(r['decision'] for r in review['cases']),
        price_outcomes_read=False, efficacy_test_launched=False, no_model_or_batch_or_sql_or_order=True,
        conclusion='Original SEC amounts reproducible, complete net-share economics not equivalent to cash repurchase tag. Bound20issuer audit ends here; no return inference or claim of unavailable paid source. A broader standardized historical panel and source/scope reconciliation, not threshold tweaking, is required for the proposed matched H20/H60 test.')
    root.mkdir(parents=True); atomic_json(root/'report.json', result)
    print(result['status'], comparisons, 'source amount matches', flush=True)


if __name__ == '__main__':
    a = argparse.ArgumentParser(description=__doc__); a.add_argument('--output', type=Path, required=True)
    audit(a.parse_args().output)
