"""Bounded TOP10 news-cause feasibility. No prices, GPT, provider or database writes."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
import pandas_market_calendars as mcal
from sqlalchemy import bindparam, create_engine, select, text

from event_sentiment import news_archive as archive
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes
from scripts.research.us_news_event_qualification import evidence_items

SOURCE = Path('artifacts/research/us_news_gpt_top20_history/20261015-v1')
MONTH = SOURCE / 'months/2026-01'
RECENT = Path('artifacts/research/us_consensus_revenue_h10_evaluation/20261020-v1')
READ = lambda p: json.loads(Path(p).read_text(encoding='utf-8'))
FACT_SCREEN = re.compile(r'\b(announc\w*|reports?|results|earnings|agreement|contracts?|FDA|approval|'
                         r'offering|acquisition|merger|guidance|partnership|launch\w*)\b', re.I)
PRICE_SCREEN = re.compile(r'\b(stock|shares?)\b.{0,35}\b(ris\w*|fall\w*|jump\w*|drop\w*|soar\w*|surge\w*|plung\w*)\b', re.I)
LABELS = {'FACTUAL_ANNOUNCEMENT_CANDIDATE', 'PRICE_MOVEMENT_COMMENTARY', 'INVESTMENT_OPINION',
          'REPEATED_OR_OLD_FACT', 'MIXED_OR_UNRESOLVED'}
SELECT_COLUMNS = ['date', 'symbol', 'score', 'fold_start', 'model_sha256', 'feature_profile_sha256',
                  'model_available_date', 'target_name', 'target_horizon', 'lineage_fold', 'oracle_rank']


def key(symbol, article_id):
    return hashlib.sha256((symbol + '|' + article_id).encode()).hexdigest()


def source_reserved(url, source=''):
    return 'msci.com' in str(url).casefold() or str(source).casefold() == 'msci'


def screen(headline):
    return bool(FACT_SCREEN.search(str(headline)))


def prepare(root):
    if (root / 'protocol.json').exists():
        p = READ(root / 'protocol.json'); verify_hashes(Path('.'), p['sources']); return p
    if root.exists():
        raise ValueError('Fresh directory required')
    verify_hashes(MONTH, READ(MONTH / 'prepared.json')['files'])
    verify_hashes(RECENT, READ(RECENT / 'ready.json')['files'])
    if READ(RECENT / 'preparation-audit.json')['status'] != 'PASS_PREPARATION_NO_PRICES':
        raise ValueError('Recent selection not audited')
    paths = [Path(__file__), Path('tests/test_us_news_information_vs_noise_feasibility.py'),
        Path('scripts/research/us_news_event_qualification.py'), Path('event_sentiment/news_archive.py'),
        SOURCE / 'protocol.json', MONTH / 'prepared.json', MONTH / 'candidates.parquet',
        MONTH / 'news-metadata.parquet', MONTH / 'packets.json',
        RECENT / 'protocol.json', RECENT / 'ready.json', RECENT / 'evaluation-cohort.parquet']
    root.mkdir(parents=True)
    p = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), sources={str(p): digest(p) for p in paths},
        hypothesis='Information-associated initial movement may continue; unidentified-cause movement may reverse. Neither presumed profitable.',
        scope='Historical January2026 TOP10 200 decisions; separate prospective19Oct TOP10 known before open from16Oct scores available17Oct.',
        recent_timing='Rank known before19Oct open, news through19Oct close, hypothetical initial reaction19Oct, possible entry20Oct. Not a same-day Oracle19Oct reconstruction.',
        review='Up to20 screened plus10 unscreened unique symbol/article pairs per panel, SHA256 order. No price, sentiment/GPT direction, performance or quality-based return selection.',
        screen='Headline keywords route review only; actual subjects/events and novelty require evidence. No price movement headline treated as causal announcement.',
        novelty='UNKNOWN unless prior announcement/repeat is positively evidenced; source and query coverage unknown is never NO_NEWS.',
        historical='Frozen 24h packets and current-version metadata; excerpts may be truncated, no earlier text reconstructed. Historical PIT remains separate.',
        prospective='Read only versioned provider archives with sealed text/mapping receipts strictly before19Oct close, A->B->A latest-stream selection. Thirty-day requested context is not promised complete.',
        price_plan='Only after separate GO and feasibility: initial reaction known by Jclose, entry nextopen, H10 TP10/SL5 fixed, matched price-only controls. No realized prices read here.',
        sql='UTC READ ONLY REPEATABLE READ,15s statement limit; capped query overflow reserved, no retry or provider collection.',
        api_calls=0, llm_calls=0, sql_writes=False, training=False, price_data_read=False, orders=False, production_changes=False)
    atomic_json(root / 'protocol.json', p); return p


def pick(items):
    by_key = {}
    for row in sorted(items, key=lambda r: (r['decision_date'], r['evidence_key'])):
        if not row.get('rights_reserved'):
            by_key.setdefault(row['evidence_key'], row)
    rows = list(by_key.values())
    return sorted([r for r in rows if r['screened']], key=lambda r: r['evidence_key'])[:20] + sorted(
        [r for r in rows if not r['screened']], key=lambda r: r['evidence_key'])[:10]


def history(root):
    prepare(root)
    if (root / 'historical-report.json').exists():
        raise ValueError('Historical pass immutable')
    cfg = READ(SOURCE / 'protocol.json'); model = cfg['annual_models']['2026']
    f = pd.read_parquet(MONTH / 'candidates.parquet', columns=SELECT_COLUMNS)
    if f.duplicated(['date', 'symbol']).any() or not f.groupby('date').size().eq(20).all():
        raise ValueError('Incomplete original TOP20')
    if not (f.target_name.eq('oracle_path_extreme20') & f.target_horizon.eq(20)
        & f.model_sha256.eq(model['model_sha256']) & f.feature_profile_sha256.eq(model['profile_sha256'])).all():
        raise ValueError('Model lineage mismatch')
    if not (pd.to_datetime(f.model_available_date).lt('2026-01-01')
        & f.fold_start.astype(str).str.startswith(model['fold']) & f.lineage_fold.astype(str).str.startswith(model['fold'])).all():
        raise ValueError('Future or wrong annual fold')
    ordered = f.sort_values(['date', 'score', 'symbol'], ascending=[True, False, True])
    if not ordered.oracle_rank.eq(ordered.groupby('date').cumcount() + 1).all():
        raise ValueError('Original score order mismatch')
    top = ordered[ordered.oracle_rank.le(10)].copy()
    if len(top) != 200:
        raise ValueError('Expected complete January TOP10')
    packets = {(r['decision_date'], r['symbol']): r for r in READ(MONTH / 'packets.json')}
    metadata = pd.read_parquet(MONTH / 'news-metadata.parquet')
    if metadata.duplicated(['article_id', 'symbol']).any():
        raise ValueError('Duplicate historical metadata')
    meta = metadata.set_index(['article_id', 'symbol']).to_dict('index')
    items = []; panel = []
    for row in top.itertuples(index=False):
        day = str(row.date)[:10]; packet = packets[(day, row.symbol)]
        cutoff = pd.Timestamp(cfg['closes'][day])
        if packet['cutoff_utc'] != cfg['closes'][day] or packet['oracle_rank'] != row.oracle_rank or packet['batch_id'] != model['batch_id']:
            raise ValueError('Packet selection mismatch')
        strict = 0
        for a in packet['articles']:
            published = pd.Timestamp(a['publication_utc'])
            if published.tzinfo is None or not cutoff - pd.Timedelta(hours=24) <= published < cutoff:
                raise ValueError('Article outside frozen publication window')
            m = meta[(a['article_id'], row.symbol)]
            if m['content_sha256'] != a['body_sha256']:
                raise ValueError('Archived excerpt / metadata version mismatch')
            stamps = [pd.Timestamp(m[k]) for k in ('created_at', 'updated_at', 'map_created_at', 'map_updated_at')]
            guarded = all(pd.notna(t) and t.tzinfo is not None and t < cutoff for t in stamps)
            strict += int(guarded)
            item = dict(panel='HISTORICAL_JAN2026', decision_date=day, symbol=row.symbol,
                oracle_rank=int(row.oracle_rank), evidence_key=key(row.symbol, a['article_id']),
                article_id=a['article_id'], headline=a['headline'], summary=a['summary'], content=a['body'],
                body_truncated=bool(a['body_truncated']), body_sha256=a['body_sha256'],
                publication_utc=a['publication_utc'], source=m['source'], url=m['url'],
                strict_text_and_mapping_before_decision=guarded, archive_version_receipt_proven=False,
                screened=screen(a['headline']), rights_reserved=source_reserved(m['url'], m['source']),
                novelty='UNKNOWN', issuer_identity='TEXT_REVIEW_REQUIRED', no_news=False)
            item['excerpt_sha256'] = hashlib.sha256(a['body'].encode()).hexdigest()
            items.append(item)
        panel.append(dict(date=day, symbol=row.symbol, oracle_rank=int(row.oracle_rank),
            available_packet_articles=len(packet['articles']), strict_current_version_guards=strict,
            coverage='PACKET_PRESENT_HISTORICAL_COVERAGE_UNKNOWN' if packet['articles'] else 'UNKNOWN_NO_PACKET_TEXT_NOT_NO_NEWS'))
    top.to_parquet(root / 'historical-top10.parquet', index=False)
    pd.DataFrame(panel).to_parquet(root / 'historical-availability.parquet', index=False)
    atomic_json(root / 'historical-article-pairs.json', items)
    atomic_json(root / 'historical-review-pack.json', pick(items))
    report = dict(status='HISTORICAL_TEXT_FEASIBILITY_ONLY_NOT_PIT', decisions=len(top), sessions=top.date.nunique(),
        symbols=top.symbol.nunique(), with_packet_text=sum(bool(r['available_packet_articles']) for r in panel),
        unknown_no_packet_text=sum(not r['available_packet_articles'] for r in panel), article_occurrences=len(items),
        unique_symbol_article_pairs=len({r['evidence_key'] for r in items}),
        unique_articles=len({r['article_id'] for r in items}), truncated_occurrences=sum(r['body_truncated'] for r in items),
        strict_current_version_occurrences=sum(r['strict_text_and_mapping_before_decision'] for r in items),
        review_pairs=len(pick(items)), no_news_certified=0, prices_read=False, llm_calls=0,
        files={n: digest(root / n) for n in ['historical-top10.parquet', 'historical-availability.parquet', 'historical-article-pairs.json', 'historical-review-pack.json']})
    atomic_json(root / 'historical-report.json', report); return report


def selected_snapshot(conn, symbols, since, cutoff, cap=1000):
    """Narrow official-version reads, never current news projections or collection."""
    ids = set(); probes = []; start = since.replace(tzinfo=None); end = cutoff.replace(tzinfo=None)
    query = text('''SELECT DISTINCT r.article_id FROM news_raw_versions r
        JOIN news_ticker_map_versions m ON m.raw_version_id=r.id
        JOIN news_archive_observations o ON o.mapping_version_id=m.id
        WHERE r.published_at_utc>=:start AND r.published_at_utc<:end
        AND o.origin='PROVIDER_COLLECTION' AND o.available_at<:end AND o.observed_at<:end
        AND JSON_CONTAINS(JSON_EXTRACT(m.mapping_rows,'$[*].symbol'),JSON_QUOTE(:symbol))
        ORDER BY r.article_id LIMIT :cap''')
    truncated = False
    for symbol in sorted(symbols):
        found = list(conn.execute(query, dict(start=start, end=end, symbol=symbol, cap=cap + 1)).scalars())
        truncated |= len(found) > cap; ids.update(found[:cap])
        probes.append(dict(symbol=symbol, ids=min(len(found), cap), truncated=len(found) > cap))
    ids = sorted(ids)
    if len(ids) > cap:
        truncated = True; ids = ids[:cap]
    obs, raw, maps = archive.OBSERVATIONS, archive.RAW_VERSIONS, archive.MAP_VERSIONS
    observations = [dict(r) for r in conn.execute(select(obs).where(obs.c.article_id.in_(ids),
        obs.c.available_at.is_not(None), obs.c.available_at < end, obs.c.observed_at < end)
        .order_by(obs.c.id).limit(cap * 50 + 1)).mappings()] if ids else []
    truncated |= len(observations) > cap * 50; observations = observations[:cap * 50]
    map_ids = {r['mapping_version_id'] for r in observations if r['mapping_version_id'] is not None}
    mappings = [dict(r) for r in conn.execute(select(maps).where(maps.c.id.in_(map_ids))).mappings()] if map_ids else []
    raw_ids = {r['raw_version_id'] for r in observations if r['raw_version_id'] is not None} | {r['raw_version_id'] for r in mappings}
    bodies = [dict(r) for r in conn.execute(select(raw).where(raw.c.id.in_(raw_ids))).mappings()] if raw_ids else []
    return dict(article_ids=ids, observations=observations, raw_versions=bodies, mapping_versions=mappings,
                pending_receipts=None, pending_receipts_not_counted=True, truncated=truncated, probes=probes)


def prospective(root):
    prepare(root)
    if (root / 'prospective-report.json').exists():
        raise ValueError('Prospective pass immutable')
    frame = pd.read_parquet(RECENT / 'evaluation-cohort.parquet')
    top = frame[frame.oracle_rank.le(10)].copy()
    if len(top) != 10 or not top.prediction_date.eq('2026-10-16').all():
        raise ValueError('Recent frozen TOP10 mismatch')
    cutoff = mcal.get_calendar('NYSE').schedule(start_date='2026-10-19', end_date='2026-10-19').iloc[0].market_close.to_pydatetime()
    since = cutoff - pd.Timedelta(days=30); previous_close = pd.Timestamp('2026-10-16T20:00:00Z')
    from database.connection import get_sqlalchemy_engine
    base = get_sqlalchemy_engine()
    engine = create_engine(base.url, pool_size=1, max_overflow=0, pool_pre_ping=True,
        connect_args={'connect_timeout':10, 'read_timeout':25, 'write_timeout':10}, echo=False)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
                raise ValueError('US alpha_trade database required')
            snapshot = selected_snapshot(conn, set(top.symbol), since, cutoff)
            conn.rollback()
    finally:
        engine.dispose()
    atomic_json(root / 'prospective-archive-snapshot.json', archive.json_value(snapshot))
    items, diagnostics = evidence_items(snapshot, set(top.symbol), since, cutoff)
    current = []; context = []; rank = top.set_index('symbol').oracle_rank.to_dict()
    for item in items:
        pub = pd.Timestamp(item['publication_utc']) if item['publication_utc'] else None
        value = dict(panel='PROSPECTIVE_OCT19_PRIOR_AVAILABLE_ORACLE', decision_date='2026-10-19',
            symbol=item['symbol'], oracle_rank=int(rank[item['symbol']]), evidence_key=key(item['symbol'], item['article_id']),
            article_id=item['article_id'], headline=item['fields']['headline'], summary=item['fields']['summary'],
            content=item['fields']['content'], body_truncated=False, source=item['source'], url=item['url'],
            publication_utc=item['publication_utc'], text_available_at=item['text_available_at'],
            mapping_available_at=item['mapping_available_at'], raw_version_id=item['raw_version_id'],
            mapping_version_id=item['mapping_version_id'], text_hash=item['text_hash'],
            temporal_reservations=item['temporal_reservations'],
            screened=screen(item['fields']['headline']), rights_reserved=source_reserved(item['url'], item['source']),
            novelty='UNKNOWN_PRIOR_ANNOUNCEMENT_REVIEW_REQUIRED', issuer_identity='TEXT_REVIEW_REQUIRED', no_news=False)
        (current if pub is not None and previous_close <= pub < pd.Timestamp(cutoff) else context).append(value)
    atomic_json(root / 'prospective-current-pairs.json', archive.json_value(current))
    atomic_json(root / 'prospective-prior-context.json', archive.json_value(context))
    atomic_json(root / 'prospective-review-pack.json', archive.json_value(pick(current)))
    counts = Counter(r['symbol'] for r in current)
    report = dict(status='PROSPECTIVE_ARCHIVE_FEASIBILITY_PARTIAL_COVERAGE_NOT_NO_NEWS',
        candidate_dates=1, candidate_symbols=10, publication_start=previous_close, cutoff=cutoff,
        selection='Oracle16Oct available17Oct before19Oct open, not Oracle19Oct at close',
        current_pairs=len(current), prior_context_pairs=len(context), symbols_with_current_pairs=len(counts),
        symbols_without_current_pairs=sorted(set(top.symbol) - set(counts)),
        temporally_qualified_current_pairs=sum(not r['temporal_reservations'] for r in current),
        review_pairs=len(pick(current)), truncated=snapshot['truncated'], diagnostics=diagnostics,
        no_news_certified=0, novelty_certified=0, read_only_sql=True, sql_writes=False,
        api_calls=0, llm_calls=0, prices_read=False,
        files={n: digest(root / n) for n in ['prospective-archive-snapshot.json', 'prospective-current-pairs.json',
            'prospective-prior-context.json', 'prospective-review-pack.json']})
    atomic_json(root / 'prospective-report.json', archive.json_value(report)); return report


def validate_reviews(pack, reviews):
    by_key = {r['evidence_key']: r for r in pack}
    if len(reviews) != len(by_key) or {r['evidence_key'] for r in reviews} != set(by_key):
        raise ValueError('Every prespecified review pair must be accounted for')
    for row in reviews:
        item = by_key[row['evidence_key']]
        if row['category'] not in LABELS or row['novelty'] not in ('UNKNOWN', 'REPEAT_CONFIRMED'):
            raise ValueError('Unsupported event/novelty promotion')
        if row['subject'] not in ('TEXTUAL_SUBJECT_MATCH', 'OTHER_ISSUER', 'UNKNOWN'):
            raise ValueError('Subject review required')
        if not row.get('note') or not row.get('quotes'):
            raise ValueError('Evidence notes required')
        for quote in row['quotes']:
            if quote['field'] not in ('headline', 'summary', 'content') or not quote['text'] or quote['text'] not in item[quote['field']]:
                raise ValueError('Quote absent from exact archived fields')
        if row['novelty'] == 'REPEAT_CONFIRMED' and row['category'] != 'REPEATED_OR_OLD_FACT':
            raise ValueError('Repeat requires explicit old-fact classification')
    return dict(reviewed=len(reviews), categories=dict(Counter(r['category'] for r in reviews)),
        subjects=dict(Counter(r['subject'] for r in reviews)), fully_qualified_new_announcements=0,
        historical_availability_not_repaired=True, independent_human_review=False)


def review(root, notes):
    prepare(root)
    if (root / 'review-report.json').exists():
        raise ValueError('Review immutable')
    value = READ(notes); result = {}
    for panel in ('historical', 'prospective'):
        verify_hashes(root, READ(root / (panel + '-report.json'))['files'])
        result[panel] = validate_reviews(READ(root / (panel + '-review-pack.json')), value[panel])
    atomic_json(root / 'review-report.json', dict(status='FEASIBILITY_REVIEW_COMPLETE_NO_OUTCOMES',
        panels=result, review_notes_sha256=digest(notes), notes_path=str(notes), prices_read=False,
        supplier_calls=0, llm_calls=0, sql_writes=False, training=False, orders=False))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=['prepare', 'history', 'prospective', 'review'], required=True)
    parser.add_argument('--notes', type=Path)
    args = parser.parse_args()
    result = review(args.output, args.notes) if args.phase == 'review' else globals()[args.phase](args.output)
    print(json.dumps(archive.json_value(result), ensure_ascii=False, default=str))
