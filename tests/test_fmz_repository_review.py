import hashlib

import pytest

from scripts.research.fmz_repository_review import (
    LAST, FIRST_PREFIX, attach_targeted_review, index_markdown, screen, select_range,
)


def item(path):
    return {'path': path, 'type': 'blob', 'sha': 'example'}


def test_inclusive_ordinal_range_not_locale_order():
    first = FIRST_PREFIX + '.md'
    tree = [item('Z-after.md'), item('The-A.md'), item(LAST), item(first), item('a-after.md')]
    assert [row['path'] for row in select_range(tree)] == [first, 'The-A.md', LAST]


def test_refuse_missing_endpoint():
    with pytest.raises(ValueError, match='missing or ambiguous'):
        select_range([item(LAST)])


def test_exclude_nested_and_nonmarkdown():
    first = FIRST_PREFIX + '.md'
    tree = [item(first), item(LAST), item('ABC.py'), item('ABC/nested.md')]
    assert len(select_range(tree)) == 2


def test_screen_flags_are_not_proven_findings():
    body = b'> Name\nTest\n```pine\nx=request.security(syminfo.tickerid,"D",high,lookahead=barmerge.lookahead_on)\n```'
    row = screen(item('A-squeeze-breakout.md'), body, 'fixed-commit')
    assert row['sha256'] == hashlib.sha256(body).hexdigest()
    assert row['title_families'] == ['volatility_compression', 'breakout']
    assert row['flags_for_manual_check']['lookahead_on_literal'][0]['line'] == 4
    assert 'fixed-commit' in row['source_url']
    assert row['status'] == 'FETCHED_HASH_VERIFIED_MECHANICAL_SCREEN'


def test_unicode_description_preserved():
    row = screen(item('测试.md'), '> Name\n测试\n```pine\nx=1\n```'.encode(), 'commit')
    assert '测试' in row['description_excerpt']
    assert '%E6%B5%8B%E8%AF%95' in row['source_url']


def test_positional_lookahead_is_flagged():
    row = screen(item('Test.md'), b'request.security(s, "D", close, barmerge.gaps_off, barmerge.lookahead_on)', 'commit')
    assert 'lookahead_on_literal' in row['flags_for_manual_check']


def test_targeted_annotations_require_exact_snapshot_and_unique_match():
    rows = [{'path': 'ABC.md'}]
    annotations = {'commit': 'commit', 'entries': [{'prefix': 'ABC', 'note': 'code inspected'}]}
    assert attach_targeted_review(rows, annotations, 'commit') == 1
    with pytest.raises(ValueError, match='duplicated'):
        attach_targeted_review(rows, annotations, 'commit')
    with pytest.raises(ValueError, match='commit differs'):
        attach_targeted_review(rows, annotations, 'different')


def test_index_does_not_claim_detailed_review_for_screen_only():
    row = screen(item('A.md'), b'> Name\nA', 'commit')
    value = index_markdown([row], 'commit')
    assert 'pas audit détaillé' in value
    assert '1 documents lus' in value
