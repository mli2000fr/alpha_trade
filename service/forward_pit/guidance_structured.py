"""E21-B research extraction and fail-closed comparison. No network, SQL or serving."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, UTC
from pathlib import Path

from service.forward_pit.guidance_audit import money_range_candidates, VisibleText
from service.forward_pit.guidance_tables import TableLayout, table_context

METRICS = {
    'EPS': r'\b(?:EPS|earnings per (?:diluted )?share|diluted earnings per share)\b',
    'revenue': r'\b(?:revenues?|net sales)\b',
    'billings': r'\bbillings\b',
    'operating_income': r'\boperating (?:income|profit|loss)\b',
    'EBITDA': r'\bEBITDA\b',
}
REVIEW_FIELDS = ['metric', 'period', 'unit', 'basis', 'definition_id', 'scope']


def statement_role(visible, start, end):
    """Local evidence only: uncertain comparisons/tables abstain, never become labels."""
    before = visible[max(0, start - 350):start]
    # Do not carry a forecast cue across an unrelated completed sentence.
    before = re.split(r'(?<=[.!?;])\s+', before)[-1]
    after = visible[end:end + 40]
    forecast = r'\b(?:guidance|outlook|forecast|expects?|expected|anticipates?|projects?|reaffirm\w*)\b'
    comparison = r'\b(?:previously|prior|previous|compared to|versus|up from|down from)\b'
    actual = r'\b(?:reported|recorded|delivered|generated|realized|actual)\b'
    evidence = []
    for role, pattern in [('NEW_FORECAST', forecast), ('PRIOR_FORECAST', comparison), ('REALIZED_RESULT', actual)]:
        for m in re.finditer(pattern, before, re.I):
            evidence.append((m.end(), role, m.group()))
    prior_after = re.match(r'\s*(?:per (?:diluted )?share\s*)?(previously|prior forecast)\b', after, re.I)
    has_forecast = bool(re.search(forecast, before, re.I))
    if re.search(r'\b(?:previously|prior|previous)\s+(?:expected|anticipated|projected|forecast|guidance|outlook)\b', before, re.I):
        return {'role': 'PRIOR_FORECAST', 'evidence': 'explicit prior forecast', 'status': 'SUGGESTION_ONLY'}
    if prior_after and has_forecast:
        return {'role': 'PRIOR_FORECAST', 'evidence': prior_after.group(), 'status': 'SUGGESTION_ONLY'}
    if not evidence:
        return {'role': 'AMBIGUOUS', 'evidence': None, 'status': 'ABSTAIN'}
    _, role, cue = max(evidence)
    if role == 'PRIOR_FORECAST' and not has_forecast:
        # A prior-year actual is not a prior forecast.
        role = 'REALIZED_RESULT' if re.search(actual, before, re.I) else 'AMBIGUOUS'
    return {'role': role, 'evidence': cue, 'status': 'ABSTAIN' if role == 'AMBIGUOUS' else 'SUGGESTION_ONLY'}


def extract(content, source):
    rows = []
    parser = TableLayout()
    parser.feed(content)
    visible = re.sub(r'\s+', ' ', ''.join(parser.parts))
    for i, candidate in enumerate(money_range_candidates(content)):
        context = candidate['context']
        table = table_context(parser, candidate['start'], candidate['end'])
        role = statement_role(visible, candidate['start'], candidate['end'])
        if table:
            role = {'role': table['role'], 'evidence': table['reason'],
                'status': 'ABSTAIN' if table['role'] == 'AMBIGUOUS' else 'SUGGESTION_ONLY'}
        metrics = [m for m, pattern in METRICS.items() if re.search(pattern, context, re.I)]
        years = sorted(set(re.findall(r'\b(?:fiscal (?:year )?|FY\s*)(20\d{2})\b', context, re.I)))
        dates = sorted(set(re.findall(r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2},? 20\d{2}\b', context)))
        adjusted = bool(re.search(r'\badjusted\b|non[- ]GAAP', context, re.I))
        gaap = bool(re.search(r'(?<!non-)\bGAAP\b', context, re.I))
        table_suggestions = None
        if table and table.get('row_label'):
            label, cell = table['row_label'], table['cell_text']
            table_metrics = [m for m, pattern in METRICS.items() if re.search(pattern, label, re.I)]
            if len(table_metrics) == 1:
                metrics = table_metrics
            table_years = sorted(set(re.findall(r'\bfiscal (?:year )?(20\d{2})\b', table['heading'], re.I)))
            if table_years:
                years = table_years
            adjusted = bool(re.search(r'non[- ]GAAP|adjusted', cell, re.I))
            gaap = bool(re.search(r'(?<!non-)\bGAAP\b', cell, re.I))
            scale = candidate['explicit_unit']
            table_suggestions = {
                'unit': 'USD ' + scale if scale else 'USD per share' if metrics == ['EPS'] else None,
                'scope': label if re.search(r'\bsegment\b', label, re.I) else None,
                'period_heading': table['heading'],
                'quarter_candidates': re.findall(r'\b(first|second|third|fourth) quarter\b', table['heading'], re.I),
                'column_header': table.get('column_header')}
        risks = []
        if re.search(r'changed? (?:the )?definition|no longer exclud|redefin', content, re.I):
            risks.append('DOCUMENT_DEFINITION_CHANGE_REVIEW')
        if re.search(r'tariff|foreign exchange|constant.currency', context, re.I):
            risks.append('ASSUMPTIONS_REVIEW')
        if re.search(r'quarter|three months', context, re.I):
            risks.append('QUARTER_PERIOD_REVIEW')
        rows.append({
            'candidate_id': source['content_sha256'] + ':' + str(i),
            'source': source, 'low': candidate['low'], 'high': candidate['high'],
            'context': context,
            'range_role': role, 'table_context': table,
            'table_suggestions': table_suggestions,
            'validated_statement_role': None,
            'suggestions': {'metric': metrics[0] if len(metrics) == 1 else None,
                'metric_candidates': metrics, 'fiscal_year_candidates': years,
                'date_candidates': dates, 'explicit_scale': candidate['explicit_unit'],
                'basis': 'adjusted' if adjusted and not gaap else 'GAAP' if gaap and not adjusted else None},
            'validated': {f: None for f in REVIEW_FIELDS},
            'review_status': 'UNREVIEWED', 'reviewer': None,
            'historical_available_at': None, 'availability_evidence': None,
            'assumptions_reviewed': False, 'definition_change': None,
            'risks': risks, 'eligible_for_comparison': False,
        })
    return rows


def availability(row):
    """Require evidence and timezone; observation today is not historical publication."""
    value = row.get('historical_available_at')
    if not value or not row.get('availability_evidence'):
        raise ValueError('MISSING_HISTORICAL_AVAILABILITY')
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('NAIVE_AVAILABILITY_TIMESTAMP')
    acceptance = row.get('source', {}).get('acceptance_datetime')
    if not acceptance:
        raise ValueError('MISSING_SEC_ACCEPTANCE')
    accepted = datetime.fromisoformat(acceptance.replace('Z', '+00:00'))
    if accepted.tzinfo is None or stamp < accepted:
        raise ValueError('AVAILABILITY_BEFORE_SEC_ACCEPTANCE_OR_NAIVE')
    return stamp


def compare(old, new):
    reasons = []
    for row in (old, new):
        if row.get('review_status') != 'APPROVED' or not row.get('reviewer'):
            reasons.append('UNAPPROVED_SEMANTICS')
        if row.get('validated_statement_role') not in ['NEW_FORECAST', 'PRIOR_FORECAST']:
            reasons.append('NOT_A_VALIDATED_FORECAST')
        if any(not row.get('validated', {}).get(f) for f in REVIEW_FIELDS):
            reasons.append('INCOMPLETE_SEMANTICS')
        if not row.get('assumptions_reviewed') or row.get('definition_change') is not False:
            reasons.append('UNRESOLVED_ASSUMPTIONS_OR_DEFINITION')
        if not isinstance(row.get('low'), (int, float)) or not isinstance(row.get('high'), (int, float)):
            reasons.append('INVALID_RANGE')
        elif not (float('-inf') < row['low'] <= row['high'] < float('inf')):
            reasons.append('INVALID_RANGE')
    if old.get('source', {}).get('cik') != new.get('source', {}).get('cik') or not old.get('source', {}).get('cik'):
        reasons.append('ISSUER_MISMATCH')
    if old.get('validated') != new.get('validated'):
        reasons.append('SEMANTIC_MISMATCH')
    try:
        old_at, new_at = availability(old), availability(new)
        if old_at >= new_at:
            reasons.append('INVALID_CHRONOLOGY')
    except (ValueError, TypeError) as exc:
        reasons.append(str(exc))
    if reasons:
        return {'status': 'ABSTAIN', 'reasons': sorted(set(reasons))}
    delta = (new['low'] + new['high'] - old['low'] - old['high']) / 2
    return {'status': 'COMPARABLE', 'midpoint_delta': delta,
        'revision': 'HIGHER' if delta > 0 else 'LOWER' if delta < 0 else 'UNCHANGED',
        'available_at': new_at.isoformat(), 'stock_direction': None}


def pair_reviewed(rows):
    """Nearest observed predecessor, never claim completeness of historical filings."""
    groups, rejected, pairs = {}, [], []
    for row in rows:
        try:
            stamp = availability(row)
        except (ValueError, TypeError) as exc:
            rejected.append({'candidate_id': row.get('candidate_id'), 'reason': str(exc)})
            continue
        validated = row.get('validated', {})
        key = (row.get('source', {}).get('cik'), *(validated.get(f) for f in REVIEW_FIELDS))
        groups.setdefault(key, []).append((stamp, row))
    for group in groups.values():
        group.sort(key=lambda item: item[0])
        for (_, old), (_, new) in zip(group, group[1:]):
            result = compare(old, new)
            pairs.append({'old_candidate_id': old.get('candidate_id'),
                'new_candidate_id': new.get('candidate_id'), **result,
                'historical_predecessor_completeness_validated': False,
                'ml_eligible': False})
    return {'pairs': pairs, 'rejected': rejected}


def run(manifests, output, reviewed=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    candidates, errors, seen = [], [], set()
    for manifest in manifests:
        manifest = Path(manifest)
        report = json.loads(manifest.read_text(encoding='utf-8'))
        for doc in report.get('documents', []):
            if doc.get('status') != 'DOWNLOADED':
                continue
            path = (manifest.parent / doc['path']).resolve()
            if not path.is_relative_to(manifest.parent.resolve()):
                errors.append({'path': doc['path'], 'error': 'PATH_OUTSIDE_COLLECTION'})
                continue
            body = path.read_bytes()
            digest = hashlib.sha256(body).hexdigest()
            if digest != doc.get('content_sha256'):
                errors.append({'path': str(path), 'error': 'HASH_MISMATCH'})
                continue
            key = (doc['cik'], doc['accession'], digest)
            if key in seen:
                continue
            seen.add(key)
            source = {k: doc.get(k) for k in ['symbol', 'cik', 'accession', 'url', 'acceptance_datetime', 'observed_at']}
            source.update(content_sha256=digest, path=str(path))
            candidates.extend(extract(body.decode('utf-8', errors='replace'), source))
    summary = {'experiment': 'E21_B_STRUCTURED_EXTRACTION', 'documents': len(seen),
        'candidates': len(candidates), 'errors': errors, 'automatic_comparable_pairs': 0,
        'status': 'REQUIRES_INDEPENDENT_SEMANTIC_AND_PIT_REVIEW',
        'database_writes': False, 'training': False,
        'limitations': ['All numeric ranges include actual results and quarterly outlook false positives',
            'Suggestions are not semantic validation; table units and fiscal periods require review',
            'Acceptance timestamp alone does not prove original publication time',
            'Statement roles are local suggestions, not approved semantics',
            'Extractor only handles dollar ranges; single-point results and percentage ranges not measured']}
    summary['role_counts'] = {role: sum(r['range_role']['role'] == role for r in candidates)
        for role in ['NEW_FORECAST', 'PRIOR_FORECAST', 'REALIZED_RESULT', 'AMBIGUOUS']}
    (output / 'review_queue.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'report.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    if reviewed:
        supplied = json.loads(Path(reviewed).read_text(encoding='utf-8'))
        originals = {r['candidate_id']: r for r in candidates}
        checked = []
        for row in supplied:
            original = originals.get(row.get('candidate_id'))
            if original is None or any(row.get(k) != original[k] for k in ['source', 'low', 'high', 'context']):
                raise ValueError('Review changed immutable source/numeric fields or unknown candidate')
            checked.append(row)
        (output / 'reviewed_pairs.json').write_text(json.dumps(pair_reviewed(checked), indent=2), encoding='utf-8')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', action='append', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--reviewed', type=Path, help='Human-reviewed queue; immutable source/ranges checked')
    args = parser.parse_args()
    output = args.output or Path('artifacts/research/guidance_structured') / datetime.now(UTC).strftime('e21b-%Y%m%d%H%M%S')
    print(json.dumps(run(args.manifest, output, args.reviewed)))


if __name__ == '__main__':
    main()
