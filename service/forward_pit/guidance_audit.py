"""E21-A: read-only SEC guidance data audit, no trading features or ML training."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path

from sqlalchemy import text

from database.connection import get_sqlalchemy_engine


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.hidden += 1
        if tag in ['p', 'div', 'tr', 'br', 'li']:
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.hidden = max(0, self.hidden-1)
        if tag in ['p', 'div', 'tr', 'li']:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data + ' ')


def money_range_candidates(content):
    """Extract visible numeric ranges only; metric, units and period need human validation."""
    parser = VisibleText()
    parser.feed(content)
    visible = re.sub(r'\s+', ' ', ''.join(parser.parts))
    pattern = re.compile(r'\$\s*([\d,]+(?:\.\d+)?)\s*(billion|million)?\s*'
        r'(?:to|and|[-–—])\s*\$?\s*([\d,]+(?:\.\d+)?)\s*(billion|million)?', re.I)
    rows = []
    for match in pattern.finditer(visible):
        rows.append({'low': float(match.group(1).replace(',', '')),
            'high': float(match.group(3).replace(',', '')),
            'explicit_unit': (match.group(2) or match.group(4) or '').lower() or None,
            'start': match.start(), 'end': match.end(),
            'context': visible[max(0,match.start()-150):match.end()+150],
            'status': 'UNCONFIRMED_RANGE_REQUIRES_METRIC_PERIOD_UNIT_REVIEW'})
    return rows


def guidance_candidates(content):
    """High-recall snippets for human review; never claim a confirmed revision."""
    parser = VisibleText()
    parser.feed(content)
    visible = re.sub(r'[ \t\r\f\v]+', ' ', ''.join(parser.parts))
    visible = re.sub(r'\n+', '\n', visible)
    cues = re.compile(r'\b(guidance|outlook|forecasts?|expects?|anticipates?|projects?|raises?|lowers?|reaffirms?|withdraws?)\b', re.I)
    metric = re.compile(r'\b(revenues?|net sales|earnings|EPS|EBITDA|margins?)\b', re.I)
    numbers = re.compile(r'(?:\$\s*\d|\d[\d,.]*\s*(?:%|million|billion)|\b20\d{2}\b)', re.I)
    results, spans = [], []
    for cue in cues.finditer(visible):
        start, end = max(0, cue.start()-200), min(len(visible), cue.end()+500)
        snippet = visible[start:end].strip()
        if not metric.search(snippet) or not numbers.search(snippet):
            continue
        if any(abs(cue.start()-s) < 250 for s in spans):
            continue
        spans.append(cue.start())
        results.append({'snippet': snippet, 'status': 'UNCONFIRMED_MANUAL_REVIEW',
            'metric_cues': sorted(set(m.group(0).lower() for m in metric.finditer(snippet))),
            'year_cues': sorted(set(re.findall(r'\b20\d{2}\b', snippet)))})
        if len(results) == 5:
            break
    return results


def run(output, universe_path, sample_limit=100):
    universe_path = Path(universe_path)
    universe = {s.strip().upper() for s in universe_path.read_text(encoding='utf-8-sig').split(',') if s.strip()}
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        filings = [dict(r) for r in conn.execute(text("""SELECT id, accession_number, cik,
            symbol, company_name, form_type, filing_date, acceptance_datetime, filing_url,
            observed_at, available_at, OCTET_LENGTH(content_text) AS body_bytes
            FROM sec_filing_raw ORDER BY filing_date, cik, accession_number""")).mappings()]
        exhibits = [dict(r) for r in conn.execute(text("""SELECT d.id,d.accession_number,
            d.document_type,d.document_name,d.document_url,d.content_bytes,
            d.content_blob IS NOT NULL AS has_content,d.observed_at,d.available_at,
            f.cik,f.symbol,f.acceptance_datetime,f.filing_date
            FROM sec_filing_documents d LEFT JOIN sec_filing_raw f USING(accession_number)""")).mappings()]
        bars_end = conn.execute(text('SELECT MAX(date) FROM stock_bars_daily')).scalar()
        metadata = [f for f in filings if f['symbol'] and f['symbol'].upper() in universe
            and f['form_type'] in ['8-K','6-K'] and f['body_bytes'] and f['body_bytes'] <= 2_000_000]
        # One issuer per sample avoids filling review with repeated filings of one company.
        chosen, seen = [], set()
        for f in metadata:
            if f['cik'] not in seen:
                chosen.append(f)
                seen.add(f['cik'])
            if len(chosen) >= sample_limit:
                break
        snippets = []
        for f in chosen:
            body = conn.execute(text('SELECT content_text FROM sec_filing_raw WHERE id=:id'),
                {'id': f['id']}).scalar()
            for item in guidance_candidates(body or ''):
                snippets.append({**{k:v for k,v in f.items() if k != 'id'}, **item,
                    'source': 'bounded_primary_or_submission_text',
                    'content_sha256': hashlib.sha256((body or '').encode()).hexdigest()})
    dates = sorted({f['filing_date'] for f in filings})
    linked = [f for f in filings if f['symbol'] and f['symbol'].upper() in universe]
    issuer_dates = {}
    for f in linked:
        if f['form_type'] in ['8-K','6-K']:
            issuer_dates.setdefault(f['cik'],set()).add(f['filing_date'])
    confirmed_pairs = 0  # Snippet heuristics do not resolve metric, fiscal period and old/new values.
    blockers = ['No confirmed like-for-like guidance revision pairs',
        'Manual numeric extraction validation not completed; snippets are not labels',
        'No historical guidance dataset aligned with price history']
    if not any(e['has_content'] for e in exhibits):
        blockers.append('All registered separate exhibits lack downloaded content')
    if dates and bars_end and dates[0] > bars_end:
        blockers.append('All local SEC filing dates are later than available daily bars')
    report = {'experiment':'E21_A_GUIDANCE_PIT_AVAILABILITY',
        'generated_at':datetime.now(UTC).isoformat(), 'verdict':'BLOCKED_DATA_NOT_READY',
        'research_only':True, 'trained':False, 'database_writes':False,
        'universe_path':str(universe_path), 'universe_symbols':len(universe),
        'universe_sha256':hashlib.sha256(universe_path.read_bytes()).hexdigest(),
        'filings':len(filings), 'filings_first_date':min(dates) if dates else None,
        'filings_last_date':max(dates) if dates else None, 'bar_last_date':bars_end,
        'filings_linked_to_universe':len(linked),
        'registered_exhibits':len(exhibits), 'exhibits_with_content':sum(bool(e['has_content']) for e in exhibits),
        'exhibits_missing_acceptance':sum(e['acceptance_datetime'] is None for e in exhibits),
        'issuers_with_two_filing_dates_in_universe':sum(len(v)>=2 for v in issuer_dates.values()),
        'eligible_bounded_sample_documents':len(metadata), 'scanned_sample_documents':len(chosen),
        'sample_documents_with_candidate':len({s['accession_number'] for s in snippets}),
        'unconfirmed_snippets':len(snippets), 'confirmed_revision_pairs':confirmed_pairs,
        'blockers':blockers,
        'limitations':['Deterministic bounded issuer sample; not prevalence estimate',
            'HTML/text only; no PDF or OCR parsing', 'No automatic fiscal period, currency or unit resolution',
            'SEC acceptance is not necessarily original press-release publication time',
            'available_at is collection time, not historical availability reconstructed from filing date']}
    output = Path(output)
    output.mkdir(parents=True,exist_ok=False)
    (output/'report.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    (output/'manual_review_candidates.json').write_text(json.dumps(snippets,indent=2,default=str),encoding='utf-8')
    (output/'manual_review.md').write_text('# E21-A : candidats NON CONFIRMES\n\n'
        +'Verifier manuellement periode fiscale, metrique, devise, unite, ancienne/nouvelle prevision, source et PIT.\n\n'
        +'\n\n'.join(f"## {s['symbol']} — {s['accession_number']}\n\nSource : {s['filing_url']}\n\n{s['snippet']}"
            for s in snippets),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--universe-file',type=Path,default=Path('config/univers_batch/univers_filtred_tradable.txt'))
    parser.add_argument('--sample-limit',type=int,default=100)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.sample_limit < 1:
        parser.error('--sample-limit must be positive')
    output=args.output or Path('artifacts/research/guidance_pit_availability')/datetime.now(UTC).strftime('e21a-%Y%m%d%H%M%S')
    report=run(output,args.universe_file,args.sample_limit)
    print(f"E21-A complete: {output}; {report['verdict']}; unconfirmed snippets={report['unconfirmed_snippets']}")


if __name__=='__main__':
    main()
