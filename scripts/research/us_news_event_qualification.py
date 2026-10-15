"""Read-only prospective equity-financing evidence packs; no signal or PnL.

Uses immutable archive versions, never current news/mappings/sentiment tables.
Keyword screening only routes documents to review. No issuer/event is auto-approved.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import re

from sqlalchemy import func, inspect, select, text

from event_sentiment import news_archive as archive

VERSION = 'PRIMARY_EQUITY_FINANCING_REVIEW_V1'
UNIVERSE = Path('config/univers_batch/univers_filtred_tradable.txt')
SCREEN = re.compile(r'\b(public offering|registered direct|private placement|equity offering|'
    r'stock offering|share offering|at.the.market offering|shelf registration|'
    r'secondary offering|selling stockholders?|convertible notes?)\b', re.I)
TYPES = {'PRIMARY_EQUITY_FINANCING', 'SECONDARY_RESALE', 'SHELF_ONLY',
         'DEBT_ONLY', 'BUYBACK', 'OTHER', 'UNKNOWN'}


def utc(value, *, database=False):
    if value is None:
        return None
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if value.tzinfo is None:
        if not database:
            raise ValueError('Explicit timezone required; no invented hour or offset')
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def save(path, value):
    """Exclusive immutable local artifact; partial output is never called complete."""
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(archive.json_value(value), stream, ensure_ascii=False, indent=2, allow_nan=False)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_snapshot(conn, since, cutoff, cap=2000):
    """One bounded transaction supplied by caller. Truncation blocks all approval."""
    obs, raw, maps = archive.OBSERVATIONS, archive.RAW_VERSIONS, archive.MAP_VERSIONS
    start = since.replace(tzinfo=None)
    end = cutoff.replace(tzinfo=None)
    ids = list(conn.execute(select(obs.c.article_id).where(
        obs.c.available_at >= start, obs.c.available_at < end,
        obs.c.observed_at < end, obs.c.origin == 'PROVIDER_COLLECTION')
        .distinct().order_by(obs.c.article_id).limit(cap + 1)).scalars())
    pending = conn.execute(select(func.count()).select_from(obs).where(
        obs.c.available_at.is_(None), obs.c.observed_at < end)).scalar_one()
    result = dict(article_ids=ids[:cap], truncated=len(ids) > cap,
        pending_receipts=int(pending), observations=[], raw_versions=[], mapping_versions=[])
    if not ids:
        return result
    # Include predecessor observations, not only changes inside the new window.
    # Last observation per stream (by id) handles A -> B -> A recurrence.
    bound = cap * 50
    rows = [dict(r) for r in conn.execute(select(obs).where(
        obs.c.article_id.in_(ids[:cap]), obs.c.available_at.is_not(None),
        obs.c.available_at < end, obs.c.observed_at < end)
        .order_by(obs.c.id).limit(bound + 1)).mappings()]
    result['truncated'] |= len(rows) > bound
    rows = rows[:bound]
    raw_ids = {r['raw_version_id'] for r in rows if r['raw_version_id'] is not None}
    map_ids = {r['mapping_version_id'] for r in rows if r['mapping_version_id'] is not None}
    result['observations'] = rows
    if map_ids:
        result['mapping_versions'] = [dict(r) for r in conn.execute(
            select(maps).where(maps.c.id.in_(sorted(map_ids)))).mappings()]
        raw_ids.update(r['raw_version_id'] for r in result['mapping_versions'])
    if raw_ids:
        result['raw_versions'] = [dict(r) for r in conn.execute(
            select(raw).where(raw.c.id.in_(sorted(raw_ids)))).mappings()]
    return result


def evidence_items(snapshot, universe, since, cutoff):
    raw = {r['id']: r for r in snapshot['raw_versions']}
    maps = {r['id']: r for r in snapshot['mapping_versions']}
    latest = {}
    for row in sorted(snapshot['observations'], key=lambda r: r['id']):
        if (row['available_at'] is not None and utc(row['available_at'], database=True) < cutoff
                and utc(row['observed_at'], database=True) < cutoff):
            latest[row['article_id'], row['stream_key']] = row
    items, diagnostics = [], Counter()
    for article_id in snapshot['article_ids']:
        receipt = latest.get((article_id, 'article'))
        if receipt is None or receipt['origin'] != 'PROVIDER_COLLECTION':
            diagnostics['NO_CONFIRMED_PROVIDER_TEXT'] += 1
            continue
        body = raw[receipt['raw_version_id']]
        relevant_maps = []
        for (aid, stream), observation in latest.items():
            if aid != article_id or not stream.startswith('mapping:payload:'):
                continue
            mapping = maps[observation['mapping_version_id']]
            if (observation['origin'] == 'PROVIDER_COLLECTION' and mapping['article_id'] == article_id
                    and mapping['payload_scope_complete'] and mapping['raw_version_id'] == body['id']):
                relevant_maps.append((observation, mapping))
        symbol_maps = defaultdict(list)
        for observation, mapping in relevant_maps:
            for row in archive.decode_json(mapping['mapping_rows']):
                if row['symbol'] in universe:
                    symbol_maps[row['symbol']].append((observation, mapping))
        if not symbol_maps:
            diagnostics['NO_MATCHING_FULL_VERSIONED_UNIVERSE_MAPPING'] += 1
        # All text fields are retained distinctly, with exact quotation positions.
        fields = {k: str(body.get(k) or '') for k in ('headline', 'summary', 'content')}
        hit = next((SCREEN.search(fields[k]) for k in fields if SCREEN.search(fields[k])), None)
        common = []
        published = utc(body.get('publication_utc'), database=True)
        normalized = utc(body.get('published_at_utc'), database=True)
        if body['article_id'] != article_id:
            common.append('ARTICLE_VERSION_IDENTITY_MISMATCH')
        if archive.canonical_hash({k: body.get(k) for k in fields}) != body['text_hash']:
            common.append('ARCHIVED_TEXT_HASH_MISMATCH')
        if utc(receipt['available_at'], database=True) < utc(receipt['observed_at'], database=True):
            common.append('TEXT_RECEIPT_CLOCK_INCONSISTENT')
        if body['publication_precision'] != 'EXPLICIT_TIMEZONE' or published is None:
            common.append('PUBLICATION_PRECISION_UNQUALIFIED')
        elif published >= cutoff:
            common.append('PUBLICATION_NOT_BEFORE_CUTOFF')
        elif published < since:
            common.append('OLD_PUBLICATION_NEWLY_OBSERVED_NOT_A_NEW_EVENT')
        if published and (normalized is None or abs((published - normalized).total_seconds()) > 1):
            common.append('PUBLICATION_NORMALIZATION_MISMATCH')
        if body['ingestion_source'] not in {'eodhd', 'alpaca'}:
            common.append('PROVIDER_OUTSIDE_EXISTING_SCOPE')
        if len(fields['content']) < 200:
            common.append('BODY_SHORT_OR_MISSING')
        if not re.match(r'^https?://[^/\s]+', body.get('url') or ''):
            common.append('SOURCE_URL_MISSING')
        if snapshot['truncated']:
            common.append('ARCHIVE_QUERY_TRUNCATED')
        for symbol, choices in sorted(symbol_maps.items()):
            observation, mapping = min(choices, key=lambda pair: pair[0]['id'])
            context = archive.decode_json(mapping['mapping_context'])
            reservations = list(common)
            if utc(observation['available_at'], database=True) < utc(observation['observed_at'], database=True):
                reservations.append('MAPPING_RECEIPT_CLOCK_INCONSISTENT')
            payload = dict(article_id=article_id, symbol=symbol, raw_version_id=body['id'],
                mapping_version_id=mapping['id'], text_hash=body['text_hash'],
                text_snapshot_hash=body['snapshot_hash'], mapping_snapshot_hash=mapping['snapshot_hash'],
                observation_id=receipt['id'], mapping_observation_id=observation['id'],
                source=body.get('source'), provider=body['ingestion_source'], url=body.get('url'),
                provider_publication=body.get('provider_publication'), publication_precision=body['publication_precision'],
                publication_utc=published, text_available_at=utc(receipt['available_at'], database=True),
                mapping_available_at=utc(observation['available_at'], database=True),
                mapping_identity_prequalified=context.get('identity_qualified') is True,
                identity_qualified=False, fields=fields, screened=hit is not None,
                screen_is_event_validation=False, temporal_reservations=reservations,
                novelty='UNKNOWN_REQUIRES_PRIOR_ANNOUNCEMENT_AND_SYNDICATION_REVIEW',
                sentiment=None, sentiment_status='NO_VERSIONED_SCORE_BINDING_PROVEN',
                tradable_signal=False, status='REVIEW_REQUIRED' if hit else 'UNSCREENED_CONTROL',
                extractor_version=VERSION)
            payload['evidence_key'] = archive.canonical_hash({k: payload[k] for k in
                ('article_id', 'symbol', 'raw_version_id', 'mapping_version_id', 'extractor_version')})
            items.append(payload)
    return items, dict(diagnostics)


def review_template(items, cap=20, controls=10):
    def order(row):
        return row['evidence_key']
    selected = sorted((r for r in items if r['screened']), key=order)[:cap]
    selected += sorted((r for r in items if not r['screened']), key=order)[:controls]
    return [dict(evidence_key=r['evidence_key'], reviewer=None, reviewed_at_utc=None,
        issuer_name=None, identity_verified=None, event_type='UNKNOWN',
        new_announcement_verified=None, novelty_evidence=None,
        prior_comparison_complete=None, quotes=[], facts=[], notes=None) for r in selected]


def qualify_review(item, review, now):
    """Validate evidence structure, not a substitute for independent human review."""
    reasons = list(item['temporal_reservations'])
    if review.get('evidence_key') != item['evidence_key']:
        reasons.append('EVIDENCE_KEY_MISMATCH')
    reviewed = None
    try:
        reviewed = utc(review.get('reviewed_at_utc'))
        if reviewed is None or reviewed > now:
            reasons.append('REVIEW_TIME_MISSING_OR_FUTURE')
        elif reviewed < max(utc(item['text_available_at']), utc(item['mapping_available_at'])):
            reasons.append('REVIEW_PREDATES_AVAILABLE_EVIDENCE')
    except (ValueError, TypeError):
        reasons.append('REVIEW_TIME_INVALID')
    if not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip():
        reasons.append('REVIEWER_MISSING')
    if not review.get('issuer_name') or review.get('identity_verified') is not True:
        reasons.append('ISSUER_IDENTITY_UNVERIFIED')
    event_type = review.get('event_type')
    if event_type not in TYPES:
        reasons.append('EVENT_TYPE_INVALID')
    if event_type != 'PRIMARY_EQUITY_FINANCING':
        reasons.append('NOT_VERIFIED_PRIMARY_EQUITY_FINANCING')
    if (review.get('new_announcement_verified') is not True or
            review.get('prior_comparison_complete') is not True or not review.get('novelty_evidence')):
        reasons.append('NOVELTY_UNVERIFIED')
    quotes = review.get('quotes') or []
    valid_quotes = []
    for q in quotes:
        field, start, end = q.get('field'), q.get('start'), q.get('end')
        valid = (field in item['fields'] and type(start) is int and type(end) is int
            and 0 <= start < end <= len(item['fields'][field])
            and isinstance(q.get('text'), str) and len(q['text'].strip()) >= 10
            and item['fields'][field][start:end] == q['text'])
        valid_quotes.append(bool(valid))
    if not quotes or not all(valid_quotes):
        reasons.append('EXACT_SOURCE_QUOTES_REQUIRED')
    for fact in review.get('facts') or []:
        index = fact.get('quote_index')
        # Keep literal units/currency; never coerce missing values or convert FX.
        if (fact.get('name') not in {'offering_amount', 'offering_price', 'shares_issued'}
                or type(index) is not int or not 0 <= index < len(quotes)
                or not fact.get('literal') or str(fact['literal']) not in quotes[index].get('text', '')):
            reasons.append('UNSUPPORTED_NUMERIC_FACT')
    reasons = sorted(set(reasons))
    return dict(evidence_key=item['evidence_key'], status='QUALIFIED_RESEARCH_EVENT' if not reasons else 'RESERVED',
        reasons=reasons, event_type=event_type, direction=None, tradable_signal=False,
        # A reviewer-declared earlier time is not proof that this validation
        # result existed then. Never backdate a freshly computed annotation.
        available_at_utc=max(now, reviewed, utc(item['text_available_at']), utc(item['mapping_available_at']))
            if reviewed else None,
        declared_reviewed_at_utc=reviewed,
        review_sha256=archive.canonical_hash(review), independent_review_certified=False,
        price_reaction=None, consensus_surprise=None,
        caveat='Validation of source/annotation, not a causal effect or trade recommendation')


def build_pack(root, snapshot, universe, since, cutoff, *, universe_sha256, now=None):
    now = now or datetime.now(timezone.utc)
    since, cutoff, now = utc(since), utc(cutoff), utc(now)
    if not since < cutoff <= now:
        raise ValueError('Require since < cutoff <= current time')
    if root.exists():
        raise FileExistsError('Use a fresh output directory; immutable evidence packs')
    root.mkdir(parents=True)
    items, diagnostics = evidence_items(snapshot, universe, since, cutoff)
    protocol = dict(family=VERSION, created_at_utc=now, since_utc=since, cutoff_utc=cutoff,
        universe_sha256=universe_sha256, universe_count=len(universe), universe_scope='current tradable file, no historical membership claim',
        selection='all mapped universe articles; hash-selected review sample, no Oracle/price/outcome selection',
        code_sha256=sha(Path(__file__)), tests_sha256=sha(Path('tests/test_us_news_event_qualification.py')),
        approved_providers=['eodhd', 'alpaca'], source_scope='already collected archives; no legal permission expansion',
        status='RESEARCH_QUARANTINE', auto_approval=False, training=False, sql_writes=False,
        api_calls=0, broker_orders=0, signal_publication=False, economic_test=False,
        actual_analysis_available_at=now, backdating_forbidden=True,
        historical_score_reuse=False, no_news_is_neutral=False)
    report_status = ('BLOCKED_ARCHIVE_TRUNCATION' if snapshot['truncated'] else
        'BLOCKED_NO_PROSPECTIVE_ARCHIVE' if not snapshot['article_ids'] else
        'REVIEW_REQUIRED' if any(r['screened'] for r in items) else 'NO_SCREEN_HIT_IN_OBSERVED_SAMPLE')
    save(root/'protocol.json', protocol)
    save(root/'archive_snapshot.json', snapshot)
    save(root/'evidence.json', items)
    save(root/'review_template.json', review_template(items))
    report = dict(status=report_status, article_ids=len(snapshot['article_ids']),
        confirmed_observations=len(snapshot['observations']), candidate_article_symbol_pairs=len(items),
        screened_pairs=sum(r['screened'] for r in items), unique_screened_texts=len({r['text_hash'] for r in items if r['screened']}),
        pending_receipts=snapshot['pending_receipts'], query_truncated=snapshot['truncated'],
        temporal_reservations=dict(Counter(reason for r in items for reason in r['temporal_reservations'])),
        diagnostics=diagnostics, qualified_events=0, independent_review=False,
        no_event_absence_claim=True, sql_writes=False, api_calls=0, training=False, economic_test=False,
        files={p.name: sha(p) for p in root.iterdir() if p.is_file()})
    save(root/'report.json', report)
    return report


def review_pack(root, review_path, output):
    """Separate immutable review result; never modify initial evidence/template."""
    report = json.loads((root/'report.json').read_text(encoding='utf-8'))
    for name, expected in report['files'].items():
        if sha(root/name) != expected:
            raise ValueError('Source evidence pack changed: ' + name)
    rows = json.loads((root/'evidence.json').read_text(encoding='utf-8'))
    known = {r['evidence_key']: r for r in rows}
    reviews = json.loads(review_path.read_text(encoding='utf-8'))
    keys = [r['evidence_key'] for r in reviews]
    if len(set(keys)) != len(keys) or not set(keys).issubset(known):
        raise ValueError('Duplicate or unknown review keys')
    now = datetime.now(timezone.utc)
    result = dict(status='ANNOTATION_REVIEW_COMPLETED_NOT_A_TRADE_SIGNAL', created_at_utc=now,
        report_sha256=sha(root/'report.json'), review_sha256=sha(review_path),
        results=[qualify_review(known[r['evidence_key']], r, now) for r in reviews],
        unreviewed_pairs=len(rows)-len(reviews), production_changes=False)
    save(output, result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--since', default='2026-10-14T00:00:00Z')
    parser.add_argument('--cutoff', help='aware UTC or offset timestamp; default now')
    parser.add_argument('--universe', type=Path, default=UNIVERSE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--article-cap', type=int, default=2000)
    parser.add_argument('--review-pack', type=Path)
    parser.add_argument('--reviews', type=Path)
    args = parser.parse_args()
    if args.review_pack:
        if args.reviews is None:
            parser.error('--reviews required with --review-pack')
        result = review_pack(args.review_pack, args.reviews, args.output)
        print(json.dumps(archive.json_value(result), ensure_ascii=False))
        return
    now = datetime.now(timezone.utc)
    since, cutoff = utc(args.since), utc(args.cutoff) if args.cutoff else now
    if not since < cutoff <= now or not 1 <= args.article_cap <= 5000:
        parser.error('Require since < cutoff <= now, article-cap in [1,5000]')
    symbols = set(filter(None, re.split(r'[,;\s]+', args.universe.read_text(encoding='utf-8-sig').strip())))
    if not symbols:
        parser.error('Empty universe')
    from database.connection import get_sqlalchemy_engine
    base = get_sqlalchemy_engine()
    # Dedicated pool and server-side READ ONLY: no accidental business-table write.
    from sqlalchemy import create_engine
    engine = create_engine(base.url, pool_size=1, max_overflow=0, pool_pre_ping=True,
        connect_args={'connect_timeout':10, 'read_timeout':25, 'write_timeout':10}, echo=False)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
                raise ValueError('US alpha_trade required')
            needed = {t.name for t in archive.META.tables.values()}
            if not needed.issubset(inspect(conn).get_table_names()):
                raise ValueError('Archive schema not installed; no automatic DDL')
            snapshot = read_snapshot(conn, since, cutoff, args.article_cap)
        result = build_pack(args.output, snapshot, symbols, since, cutoff,
            universe_sha256=sha(args.universe), now=now)
        print(json.dumps(archive.json_value(result), ensure_ascii=False))
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
