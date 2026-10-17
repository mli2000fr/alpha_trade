"""All DB fixtures are SQLite memory; never alpha_trade or a paid service."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from sqlalchemy import create_engine

from event_sentiment import news_archive as archive
from scripts.research import us_news_event_qualification as pilot

SINCE = datetime(2026, 10, 14, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 10, 15, 18, tzinfo=timezone.utc)
OBSERVED = datetime(2026, 10, 15, 12)


def snapshot():
    content = ('EXAMPLE Corp announces a registered direct offering of common shares. '
        'The company expects gross proceeds of $20 million at $10 per share. '
        'The issuer will receive the proceeds from newly issued common shares. '
        'This synthetic fixture is not a real security or news announcement.')
    record = dict(article_id='eodhd:fixture', headline='EXAMPLE announces registered direct offering',
        summary=None, content=content, source='Fixture agency', author=None,
        url='https://source.example.test/story', published_at_utc=OBSERVED-timedelta(minutes=1),
        ingestion_source='eodhd', raw_payload={'created_at':'2026-10-15T11:59:00Z'})
    raw = dict(archive.raw_snapshot(record, record['article_id'], OBSERVED), id=1)
    mapping = dict(archive.mapping_snapshot(record['article_id'], 1,
        [dict(symbol='EXAMPLE')], {'identity_qualified':False}, True, OBSERVED), id=1)
    common = dict(article_id=record['article_id'], batch_id='fixture', origin='PROVIDER_COLLECTION',
        observed_at=OBSERVED, available_at=OBSERVED+timedelta(seconds=1))
    obs = [dict(common, id=1, stream_key='article', raw_version_id=1, mapping_version_id=None),
        dict(common, id=2, stream_key='mapping:payload:EXAMPLE', raw_version_id=None, mapping_version_id=1)]
    return dict(article_ids=[record['article_id']], truncated=False, pending_receipts=0,
        observations=obs, raw_versions=[raw], mapping_versions=[mapping])


def items(source=None):
    return pilot.evidence_items(source or snapshot(), {'EXAMPLE'}, SINCE, CUTOFF)[0]


def good_review(item):
    phrase = item['fields']['content'].split('. ')[0] + '.'
    return dict(evidence_key=item['evidence_key'], reviewer='Fixture technical reviewer, NOT independent human',
        reviewed_at_utc='2026-10-15T13:00:00Z', issuer_name='EXAMPLE Corp', identity_verified=True,
        event_type='PRIMARY_EQUITY_FINANCING', new_announcement_verified=True,
        prior_comparison_complete=True, novelty_evidence='Fixture prior announcements inspected',
        quotes=[dict(field='content', start=0, end=len(phrase), text=phrase)], facts=[])


def test_screen_is_not_identity_event_direction_or_sentiment_probability():
    item = items()[0]
    assert item['screened'] and item['status'] == 'REVIEW_REQUIRED'
    assert not item['identity_qualified'] and not item['tradable_signal']
    assert item['sentiment'] is None
    assert not item['temporal_reservations']
    assert pilot.review_template([item])[0]['identity_verified'] is None


def test_pending_and_cutoff_equality_never_qualify():
    data = snapshot()
    data['observations'][0]['available_at'] = CUTOFF.replace(tzinfo=None)
    assert not items(data)
    data['observations'][0]['available_at'] = None
    assert not items(data)


def test_no_current_mapping_or_partial_mapping_or_wrong_text_fallback():
    for change in ({'payload_scope_complete':False}, {'raw_version_id':99}, {'article_id':'wrong'}):
        data = snapshot()
        data['mapping_versions'][0].update(change)
        assert not items(data)
    data = snapshot()
    data['observations'][1]['stream_key'] = 'mapping:partial:fixture'
    assert not items(data)


def test_latest_stream_can_remove_symbol_and_current_row_review_is_not_provider():
    data = snapshot()
    empty = dict(data['mapping_versions'][0], id=2, mapping_rows=[])
    data['mapping_versions'].append(empty)
    data['observations'].append(dict(data['observations'][1], id=3, mapping_version_id=2))
    assert not items(data)
    data = snapshot()
    data['observations'][0]['stream_key'] = 'article:current_row_review'
    data['observations'][0]['origin'] = 'CURRENT_ROW_REVIEW'
    assert not items(data)


def test_return_to_old_version_uses_observation_order_not_first_seen():
    data = snapshot()
    other = dict(data['raw_versions'][0], id=2, headline='Not the latest state')
    data['raw_versions'].append(other)
    data['observations'] += [dict(data['observations'][0], id=3, raw_version_id=2),
        dict(data['observations'][0], id=4, raw_version_id=1)]
    assert items(data)[0]['raw_version_id'] == 1


@pytest.mark.parametrize('precision', ['DATE_ONLY', 'TIMEZONE_UNKNOWN', 'UNKNOWN', 'INVALID'])
def test_imprecise_publication_kept_but_reserved(precision):
    data = snapshot()
    data['raw_versions'][0].update(publication_precision=precision, publication_utc=None)
    item = items(data)[0]
    assert 'PUBLICATION_PRECISION_UNQUALIFIED' in item['temporal_reservations']
    result = pilot.qualify_review(item, good_review(item), CUTOFF)
    assert result['status'] == 'RESERVED'


def test_stale_import_truncation_bad_text_and_clock_all_reserved():
    data = snapshot()
    data['truncated'] = True
    raw = data['raw_versions'][0]
    raw.update(publication_utc=SINCE.replace(tzinfo=None)-timedelta(days=30), content='changed')
    data['observations'][0]['available_at'] = OBSERVED-timedelta(seconds=1)
    reasons = items(data)[0]['temporal_reservations']
    assert {'OLD_PUBLICATION_NEWLY_OBSERVED_NOT_A_NEW_EVENT', 'ARCHIVE_QUERY_TRUNCATED',
        'ARCHIVED_TEXT_HASH_MISMATCH', 'BODY_SHORT_OR_MISSING', 'TEXT_RECEIPT_CLOCK_INCONSISTENT'} <= set(reasons)


def test_verified_annotation_not_signal_and_available_only_after_analysis():
    item = items()[0]
    result = pilot.qualify_review(item, good_review(item), CUTOFF)
    assert result['status'] == 'QUALIFIED_RESEARCH_EVENT'
    assert result['available_at_utc'] == CUTOFF
    assert result['declared_reviewed_at_utc'] == datetime(2026,10,15,13,tzinfo=timezone.utc)
    assert result['direction'] is None and not result['tradable_signal']
    assert not result['independent_review_certified']


@pytest.mark.parametrize('field,value,reason', [
    ('identity_verified',None,'ISSUER_IDENTITY_UNVERIFIED'),
    ('event_type','SECONDARY_RESALE','NOT_VERIFIED_PRIMARY_EQUITY_FINANCING'),
    ('event_type','SHELF_ONLY','NOT_VERIFIED_PRIMARY_EQUITY_FINANCING'),
    ('event_type','DEBT_ONLY','NOT_VERIFIED_PRIMARY_EQUITY_FINANCING'),
    ('new_announcement_verified',None,'NOVELTY_UNVERIFIED'),
    ('reviewed_at_utc','2026-10-15T11:00:00Z','REVIEW_PREDATES_AVAILABLE_EVIDENCE'),
    ('reviewed_at_utc','2026-10-16T00:00:00Z','REVIEW_TIME_MISSING_OR_FUTURE'),
    ('reviewed_at_utc','2026-10-15','REVIEW_TIME_INVALID')])
def test_annotation_reservations(field,value,reason):
    item = items()[0]
    review = dict(good_review(item), **{field:value})
    result = pilot.qualify_review(item,review,CUTOFF)
    assert result['status'] == 'RESERVED' and reason in result['reasons']


def test_fake_quotes_and_unbacked_numeric_facts_rejected():
    item = items()[0]
    review = good_review(item)
    review['quotes'][0]['text'] = 'invented financing'
    review['facts'] = [dict(name='offering_amount', literal='$999 billion', quote_index=0)]
    result = pilot.qualify_review(item,review,CUTOFF)
    assert 'EXACT_SOURCE_QUOTES_REQUIRED' in result['reasons']
    assert 'UNSUPPORTED_NUMERIC_FACT' in result['reasons']


def test_missing_novelty_or_unreviewed_template_is_not_approved():
    item = items()[0]
    result = pilot.qualify_review(item, pilot.review_template([item])[0], CUTOFF)
    assert result['status'] == 'RESERVED' and result['available_at_utc'] is None


def test_bounded_sqlite_reader_and_empty_archive_not_no_event(tmp_path):
    engine = create_engine('sqlite:///:memory:')
    archive.META.create_all(engine)
    with engine.connect() as conn:
        data = pilot.read_snapshot(conn,SINCE,CUTOFF,cap=1)
    root = tmp_path/'empty'
    report = pilot.build_pack(root,data,{'EXAMPLE'},SINCE,CUTOFF,universe_sha256='fixture',now=CUTOFF)
    assert report['status'] == 'BLOCKED_NO_PROSPECTIVE_ARCHIVE'
    assert report['no_event_absence_claim'] and report['qualified_events'] == 0
    assert json.loads((root/'review_template.json').read_text()) == []
    with pytest.raises(FileExistsError):
        pilot.build_pack(root,data,{'EXAMPLE'},SINCE,CUTOFF,universe_sha256='fixture',now=CUTOFF)
    engine.dispose()


def test_reader_keeps_predecessor_version_and_detects_article_cap():
    engine = create_engine('sqlite:///:memory:')
    archive.META.create_all(engine)
    data = snapshot()
    with engine.begin() as conn:
        conn.execute(archive.RAW_VERSIONS.insert(),data['raw_versions'])
        conn.execute(archive.MAP_VERSIONS.insert(),data['mapping_versions'])
        conn.execute(archive.OBSERVATIONS.insert(),data['observations'])
        extra = dict(data['observations'][0],id=3,article_id='eodhd:second')
        conn.execute(archive.OBSERVATIONS.insert(),extra)
    with engine.connect() as conn:
        fetched = pilot.read_snapshot(conn,SINCE,CUTOFF,cap=1)
    assert fetched['truncated'] and len(fetched['article_ids']) == 1
    assert len(fetched['raw_versions']) == 1
    engine.dispose()


def test_pack_hash_review_integrity_and_duplicate_reviews(tmp_path):
    root = tmp_path/'pack'
    pilot.build_pack(root,snapshot(),{'EXAMPLE'},SINCE,CUTOFF,universe_sha256='fixture',now=CUTOFF)
    item = json.loads((root/'evidence.json').read_text())[0]
    reviews = tmp_path/'reviews.json'
    reviews.write_text(json.dumps([pilot.review_template([item])[0]]),encoding='utf-8')
    result = pilot.review_pack(root,reviews,tmp_path/'result.json')
    assert result['results'][0]['status'] == 'RESERVED'
    reviews.write_text(json.dumps([good_review(item)]*2),encoding='utf-8')
    with pytest.raises(ValueError,match='Duplicate'):
        pilot.review_pack(root,reviews,tmp_path/'other.json')
    (root/'evidence.json').write_text('[]',encoding='utf-8')
    with pytest.raises(ValueError,match='changed'):
        pilot.review_pack(root,reviews,tmp_path/'other.json')


def test_screening_catches_false_friend_cases_without_approval():
    for phrase in ('secondary offering', 'shelf registration', 'convertible notes', 'public offering'):
        assert pilot.SCREEN.search(phrase)


def test_naive_cli_cutoffs_and_future_cutoffs_refused(tmp_path):
    with pytest.raises(ValueError,match='timezone'):
        pilot.utc('2026-10-15')
    with pytest.raises(ValueError,match='cutoff'):
        pilot.build_pack(tmp_path/'future',snapshot(),{'EXAMPLE'},SINCE,CUTOFF,
            universe_sha256='fixture',now=CUTOFF-timedelta(hours=1))
