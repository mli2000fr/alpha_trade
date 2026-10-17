"""Explicit, bounded EODHD pilot using the existing writer, no production checkpoints.

At most 12 HTTP attempts including retries, one page per selected symbol.
Not a backfill of historical availability and not a scheduled batch.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import logging
from pathlib import Path
import re
from urllib.parse import urlsplit

from sqlalchemy import select, text

from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.ingestion import NewsIngestionService
from scripts.research import us_news_event_qualification as qualification
from service.eodhd.news_client import fetch_news_page


class AttemptLimit(RuntimeError):
    pass


class Transport:
    def __init__(self, cap=12):
        self.cap, self.attempts = cap, 0

    def proxy(self, session):
        budget = self
        class Proxy:
            def request(self, method, url, **kwargs):
                parsed = urlsplit(url)
                if method.upper() != 'GET' or parsed.scheme != 'https' or parsed.hostname != 'eodhd.com' or parsed.path != '/api/news':
                    raise RuntimeError('Pilot allows only the existing EODHD news GET endpoint')
                if budget.attempts >= budget.cap:
                    raise AttemptLimit('Pilot HTTP attempt limit reached')
                budget.attempts += 1
                kwargs['allow_redirects'] = False
                return session.request(method, url, **kwargs)
        return Proxy()


class PilotRepository(EventSentimentRepository):
    def get_checkpoint(self, *args, **kwargs):
        return None

    def upsert_checkpoint(self, *args, **kwargs):
        # A one-page research probe must never move the production watermark.
        return None


def shortlist(symbols, count=12):
    return sorted(set(symbols), key=lambda s: hashlib.sha256(('financing-pilot-v1|' + s).encode()).hexdigest())[:count]


def run(root, universe, *, execute=False):
    if root.exists():
        raise FileExistsError('Fresh output directory required')
    symbols = set(filter(None, re.split(r'[,;\s]+', universe.read_text(encoding='utf-8-sig').strip())))
    chosen = shortlist(symbols)
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=7)
    root.mkdir(parents=True)
    protocol = dict(experiment='BOUNDED_PROSPECTIVE_NEWS_PILOT', created_at_utc=now,
        window_start_utc=start, window_end_utc=now, universe=str(universe), universe_sha256=qualification.sha(universe),
        symbols=chosen, selection='fixed SHA256 order, no price/outcome selection',
        page_limit=25, maximum_pages_per_symbol=1, http_attempt_cap_including_retries=12,
        collection_requested=execute, scheduled=False, checkpoint_writes=False,
        source='existing EODHD news API; no new subscription',
        business_writes_if_execute=['news_raw','news_ticker_map','news_raw_versions','news_ticker_map_versions','news_archive_observations'],
        scoring=False, llm_calls=0, orders=False, training=False,
        code_sha256=qualification.sha(Path(__file__)))
    qualification.save(root/'protocol.json',protocol)
    if not execute:
        return dict(status='PREPARED_NOT_COLLECTED', symbols=chosen)
    repository = PilotRepository()
    checkpoint_table = repository._table('news_ingestion_checkpoint')
    stmt = select(checkpoint_table).where(checkpoint_table.c.source_name=='eodhd_news', checkpoint_table.c.symbol.in_(chosen))
    with repository.engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
            raise ValueError('US database alpha_trade required')
        before = [dict(r) for r in conn.execute(stmt).mappings()]
    config = EventSentimentConfig.for_provider('eodhd', page_limit=25, allow_sector_fallback=False)
    service = NewsIngestionService(repository, config)
    transport, pages = Transport(), []
    def single_page(**kwargs):
        articles, token = fetch_news_page(start_utc=kwargs['start_utc'], end_utc=kwargs['end_utc'],
            symbols=kwargs['symbols'], limit=25, offset=0, session=transport.proxy(kwargs['session']))
        pages.append(dict(symbol=kwargs['symbols'][0], received=len(articles),
            more_pages_available=token is not None, scope='ONE_PAGE_ONLY_NOT_EXHAUSTIVE'))
        yield articles, None
    service._iter_news_pages = single_page
    results = []
    for symbol in chosen:
        if transport.attempts >= transport.cap:
            results.append(dict(symbol=symbol, status='NOT_ATTEMPTED_BUDGET_LIMIT'))
            continue
        try:
            stats = service._run_symbol(symbol, start, now, resume_checkpoint=False)
            results.append(dict(symbol=symbol, status='COLLECTED_ONE_PAGE', stats=stats))
        except Exception as exc:
            # Provider exceptions can contain authentication query strings.
            # Never serialize exception messages, reprs or full request URLs.
            results.append(dict(symbol=symbol, status='FAILED', error_type=type(exc).__name__))
    with repository.engine.connect() as conn:
        after = [dict(r) for r in conn.execute(stmt).mappings()]
    key = lambda r: (r['source_name'], r['symbol'])
    unchanged = qualification.archive.canonical_hash(sorted(before,key=key)) == qualification.archive.canonical_hash(sorted(after,key=key))
    result = dict(status='COMPLETED_BOUNDED_PILOT' if all(r['status']=='COLLECTED_ONE_PAGE' for r in results) else 'PARTIAL_PILOT',
        http_attempts=transport.attempts, results=results, pages=pages,
        production_checkpoint_writer_disabled=True, production_checkpoints_equal_before_after=unchanged,
        equality_caveat='Concurrent production collectors may legitimately change checkpoints; pilot never writes them',
        business_sql_writes=True, llm_calls=0, training=False, orders=False,
        availability='actual provider observation/commit time only, never publication time backdating')
    qualification.save(root/'report.json',result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--universe',type=Path,default=qualification.UNIVERSE)
    parser.add_argument('--collect',action='store_true')
    args=parser.parse_args()
    logging.basicConfig(level=logging.CRITICAL)
    result=run(args.output,args.universe,execute=args.collect)
    import json
    print(json.dumps(qualification.archive.json_value(result),ensure_ascii=False))
