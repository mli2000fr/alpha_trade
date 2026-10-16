import pytest
import json
from scripts.research import us_news_financing_second_review_20261016 as second


def row(i, screened=True, text=None, reserved=False):
    return dict(evidence_key=f'{i:03}', text_hash=text or f'text{i}', screened=screened,
                temporal_reservations=['RESERVED'] if reserved else [])


def test_second_sample_is_stable_bounded_unique_and_excludes_previously_read_texts():
    prior = [row(0)]
    items = [row(i, i<50) for i in range(80)]
    items += [row(1, text='text0'), row(2, text='text2'), row(3, reserved=True)]
    chosen = second.select_second(items, prior)
    assert len(chosen)==30
    assert sum(r['screened'] for r in chosen)==20
    assert len({r['text_hash'] for r in chosen})==30
    assert all(r['text_hash']!='text0' and not r['temporal_reservations'] for r in chosen)
    assert second.select_second(list(reversed(items)), prior)==chosen


def test_no_padding_with_old_or_reserved_texts():
    assert second.select_second([row(1, reserved=True), row(2)], [row(0)])==[row(2)]


def test_pack_tampering_is_rejected(tmp_path):
    second.evidence.save(tmp_path/'evidence.json', [])
    second.evidence.save(tmp_path/'report.json', dict(query_truncated=False,
        files={'evidence.json':'invalid'}))
    with pytest.raises(ValueError, match='Changed'):
        second.verified_pack(tmp_path)


def test_reading_requires_exact_quotes_and_never_certifies_novelty(tmp_path):
    item = dict(row(1), article_id='fixture:1', symbol='XYZ',
        fields={'content':'Issuer XYZ announces an equity offering.'},
        text_available_at='2026-01-01T00:00:00Z', mapping_available_at='2026-01-01T00:00:00Z')
    pack = tmp_path/'pack'
    pack.mkdir()
    second.evidence.save(pack/'evidence.json', [item])
    second.evidence.save(pack/'report.json', dict(query_truncated=False,
        files={'evidence.json':second.evidence.sha(pack/'evidence.json')}))
    notes = tmp_path/'notes.json'
    note = dict(issuer='XYZ', identity_symbols=['XYZ'], event_type='PRIMARY_EQUITY_FINANCING',
        quote='not in this archive', notes='Read source', category='FIXTURE',
        new_announcement_verified=True)
    second.evidence.save(notes, {'fixture:1':note})
    with pytest.raises(ValueError, match='Exact archived'):
        second.annotate(pack, notes)
    assert not (pack/'technical_review_filled.json').exists()
    # The manually entered 'new' flag alone cannot certify prior history.
    valid = tmp_path/'valid.json'
    second.evidence.save(valid, {'fixture:1':dict(note, quote='announces an equity offering')})
    summary = second.annotate(pack, valid)
    result = json.loads((pack/'technical_review_result.json').read_text())
    assert summary['qualified_pairs']==0
    assert 'NOVELTY_UNVERIFIED' in result['results'][0]['reasons']
    assert summary['independent_review_certified'] is False
