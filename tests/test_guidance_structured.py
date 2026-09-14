from copy import deepcopy

import pytest

from service.forward_pit.guidance_structured import compare, extract, pair_reviewed


def approved():
    return {'low': 1., 'high': 2., 'source': {'cik': '123', 'acceptance_datetime': '2025-01-01T12:00:00Z'},
        'review_status': 'APPROVED', 'reviewer': 'test',
        'validated_statement_role': 'NEW_FORECAST',
        'validated': {'metric': 'EPS', 'period': 'FY2025', 'unit': 'USD/share',
            'basis': 'GAAP', 'definition_id': 'v1', 'scope': 'group'},
        'historical_available_at': '2025-01-01T12:01:00Z',
        'availability_evidence': 'fixture', 'assumptions_reviewed': True, 'definition_change': False}


def test_extraction_never_auto_approves():
    row = extract('Fiscal year 2025 adjusted EPS outlook $4.00 to $5.00.', {'content_sha256': 'abc'})[0]
    assert row['suggestions']['metric'] == 'EPS'
    assert row['suggestions']['fiscal_year_candidates'] == ['2025']
    assert not row['eligible_for_comparison']
    assert row['validated']['unit'] is None
    assert compare(row, row)['status'] == 'ABSTAIN'


def test_comparable_revision_is_not_stock_direction():
    old = approved()
    new = deepcopy(old)
    new.update(low=2., high=3., historical_available_at='2025-02-01T12:01:00Z')
    result = compare(old, new)
    assert result['revision'] == 'HIGHER'
    assert result['stock_direction'] is None


@pytest.mark.parametrize('field,value', [
    ('review_status', 'UNREVIEWED'), ('definition_change', True),
    ('assumptions_reviewed', False), ('availability_evidence', None),
    ('historical_available_at', '2024-01-01T12:00:00Z'),
    ('historical_available_at', '2025-02-01T12:00:00'),
    ('low', float('nan')), ('high', float('inf')),
])
def test_fail_closed(field, value):
    old = approved()
    new = deepcopy(old)
    new.update(historical_available_at='2025-02-01T12:01:00Z')
    new[field] = value
    assert compare(old, new)['status'] == 'ABSTAIN'


@pytest.mark.parametrize('field', ['period', 'unit', 'basis', 'scope', 'definition_id', 'metric'])
def test_semantic_mismatch(field):
    old = approved()
    new = deepcopy(old)
    new['validated'][field] = 'different'
    new['historical_available_at'] = '2025-02-01T12:01:00Z'
    assert 'SEMANTIC_MISMATCH' in compare(old, new)['reasons']


def test_pairing_sorts_and_does_not_claim_complete_predecessor():
    old = approved()
    old['candidate_id'] = 'old'
    new = deepcopy(old)
    new.update(candidate_id='new', historical_available_at='2025-02-01T12:01:00Z')
    pair = pair_reviewed([new, old])['pairs'][0]
    assert pair['old_candidate_id'] == 'old'
    assert pair['status'] == 'COMPARABLE'
    assert not pair['ml_eligible']


def test_equal_publication_times_abstain():
    assert pair_reviewed([approved(), approved()])['pairs'][0]['status'] == 'ABSTAIN'


@pytest.mark.parametrize('sentence,roles', [
    ('Fiscal 2024 EPS guidance is $3.30 to $3.45, up from $3.20 to $3.40.', ['NEW_FORECAST', 'PRIOR_FORECAST']),
    ('The company expects EPS $2.52 to $2.72, compared to $2.43 to $2.63 previously.', ['NEW_FORECAST', 'PRIOR_FORECAST']),
    ('The company reported earnings $3.00 to $4.00 compared to $2.00 to $3.00 last year.', ['REALIZED_RESULT', 'REALIZED_RESULT']),
    ('Outlook was published. Reported earnings $3.00 to $4.00.', ['REALIZED_RESULT']),
    ('Fiscal year 2024 $3.00 to $4.00.', ['AMBIGUOUS']),
    ('Previously expected EPS $3.00 to $4.00.', ['PRIOR_FORECAST']),
])
def test_local_statement_roles(sentence, roles):
    assert [r['range_role']['role'] for r in extract(sentence, {'content_sha256': 'fixture'})] == roles


def test_actual_is_not_comparable_forecast():
    row = approved()
    row['validated_statement_role'] = 'REALIZED_RESULT'
    assert 'NOT_A_VALIDATED_FORECAST' in compare(row, approved())['reasons']
