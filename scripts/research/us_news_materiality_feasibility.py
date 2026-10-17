"""Bounded read-only audit of news text availability; never load price outcomes.

Current DB versions can only provide a conservative availability diagnostic,
not proof of a complete immutable historical news feed.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import re

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from common.market_calendar import get_market_calendar
from database.connection import get_sqlalchemy_engine
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

SOURCE = Path('artifacts/research/us_oracle_path_protection_selector/20261014-v1/candidates.parquet')
LOG = logging.getLogger(__name__)
STAMPS = ('published_at_utc', 'created_at', 'updated_at', 'map_created_at', 'map_updated_at')
PERIODS = ('2025-01', '2025-07', '2026-01', '2026-07')


def freeze_protocol(source, months, row_cap):
    return dict(experiment='NEWS_PRIMARY_EQUITY_FINANCING_FEASIBILITY',
        frozen_at_utc=datetime.now(timezone.utc).isoformat(), candidate_sha256=digest(source),
        source=str(source), months=list(months), selection='ORIGINAL_TOP5_ALL_DAYS_IN_FIXED_MONTHS',
        providers=['eodhd', 'alpaca'], row_cap_per_symbol_month=row_cap,
        cutoff='STRICTLY_BEFORE_OFFICIAL_NYSE_CLOSE_J', lookback_calendar_days=30,
        target_if_qualified='TP20_BEFORE_SL5_LONG_NEXT_OPEN_WITHIN_20_SESSIONS',
        hypothesis='New primary equity financing/dilution announcement may veto a LONG entry',
        exclusions=['debt only', 'shelf registration alone', 'secondary shareholder resale',
                    'generic market opinion', 'buybacks', 'old announcement merely repeated'],
        novelty='Compare with prior 10 available same-symbol articles within previous 30 calendar days; '
                'fewer than 10 means novelty UNKNOWN, never NEW',
        screening='Fixed headline keyword screen; manual content validation required, not a feature',
        minimum_future_test=dict(validated_events_per_year=20, distinct_event_dates_per_year=10),
        decision='STOP if either year lacks timestamp-guarded event support or corpus coverage is unqualified',
        historical_absence_not_neutral=True, text_versions_append_only=False,
        sql='SELECT only, session UTC and READ ONLY, MySQL query timeout 15 seconds',
        training=False, price_outcomes_loaded=False, pnl=False, production_changes=False,
        code_sha256=digest(Path(__file__)))


def raw_publication_reason(value, published):
    """Do not invent an hour or UTC offset from a date-only/naive provider value."""
    if not isinstance(value, str) or not re.search(r'[T ]\d{2}:\d{2}', value):
        return 'PUBLICATION_DATE_ONLY_OR_MISSING'
    try:
        parsed = pd.Timestamp(value)
        if parsed.tzinfo is None:
            return 'PUBLICATION_TIMEZONE_UNKNOWN'
        if pd.isna(published) or abs((parsed.tz_convert('UTC')-published).total_seconds()) > 1:
            return 'PUBLICATION_NORMALIZATION_MISMATCH'
        if parsed.tz_convert('UTC').time().isoformat().startswith('00:00:00'):
            return 'MIDNIGHT_PRECISION_RESERVED'
    except (ValueError, TypeError, OverflowError):
        return 'PUBLICATION_INVALID'
    return None


def guarded_reasons(row, cutoff):
    cutoff = pd.Timestamp(cutoff)
    if cutoff.tzinfo is None:
        raise ValueError('Timezone-aware cutoff required')
    reasons = []
    if row.get('ingestion_source') not in ('eodhd', 'alpaca'):
        reasons.append('PROVIDER_OUTSIDE_SCOPE')
    if (row.get('content_chars') or 0) < 200:
        reasons.append('BODY_MISSING_OR_SHORT')
    reason = raw_publication_reason(row.get('provider_publication'), row['published_at_utc'])
    if reason:
        reasons.append(reason)
    for field in STAMPS:
        value = row.get(field)
        if pd.isna(value):
            reasons.append(field.upper()+'_MISSING')
        elif pd.Timestamp(value) >= cutoff:
            reasons.append(field.upper()+'_NOT_BEFORE_DECISION')
    return reasons


def headline_screen(headline):
    """A retrieval screen, intentionally not a verified dilution classifier."""
    s = str(headline).casefold()
    return bool(re.search(r'\b(public offering|registered direct|private placement|'
                          r'equity offering|stock offering|share offering|at.the.market offering)\b', s))


def audit_panel(candidates, news, closes):
    rows = []
    grouped = {key: value for key, value in news.groupby('symbol')}
    empty = news.iloc[:0]
    for candidate in candidates.sort_values(['date', 'oracle_rank']).itertuples(index=False):
        cutoff = closes[pd.Timestamp(candidate.date)]
        part = grouped.get(candidate.symbol, empty)
        recent = part[part.published_at_utc.lt(cutoff) &
                      part.published_at_utc.ge(cutoff-pd.Timedelta(days=30))]
        guards = [guarded_reasons(row, cutoff) for row in recent.to_dict('records')]
        qualified = recent.loc[[not x for x in guards]]
        current = recent[recent.published_at_utc.ge(cutoff-pd.Timedelta(days=1))]
        current_guarded = qualified[qualified.published_at_utc.ge(cutoff-pd.Timedelta(days=1))]
        reasons = Counter(reason for items in guards for reason in items)
        context = qualified[qualified.published_at_utc.lt(cutoff-pd.Timedelta(days=1))]
        if 'content_sha256' in context:
            context = context[context.content_sha256.notna()].drop_duplicates('content_sha256')
        rows.append(dict(date=candidate.date, year=candidate.year, symbol=candidate.symbol,
            oracle_rank=candidate.oracle_rank, cutoff_utc=cutoff,
            recent_article_mappings=len(recent), recent_guarded_mappings=len(qualified),
            last_24h_mappings=len(current), last_24h_guarded_mappings=len(current_guarded),
            screened_last_24h=int(current.headline_screen.sum()),
            screened_guarded_last_24h=int(current_guarded.headline_screen.sum()),
            available_novelty_context_count=min(10, len(context)),
            guard_reasons=json.dumps(dict(sorted(reasons.items())), sort_keys=True)))
    return pd.DataFrame(rows)


META_FIELDS = """SELECT /*+ MAX_EXECUTION_TIME(15000) */
    n.article_id,m.symbol,n.ingestion_source,n.source,n.published_at_utc,n.created_at,n.updated_at,
    m.created_at map_created_at,m.updated_at map_updated_at,m.is_primary_ticker,
    n.headline,CHAR_LENGTH(n.content) content_chars,SHA2(n.content,256) content_sha256,
    COALESCE(JSON_UNQUOTE(JSON_EXTRACT(JSON_UNQUOTE(n.raw_payload),'$.created_at')),
             JSON_UNQUOTE(JSON_EXTRACT(JSON_UNQUOTE(n.raw_payload),'$.date')),
             JSON_UNQUOTE(JSON_EXTRACT(JSON_UNQUOTE(n.raw_payload),'$.published_at'))) provider_publication,
    JSON_TYPE(n.raw_payload) payload_json_type,
    n.url,n.dedupe_hash """
MAP_FIRST_SQL = META_FIELDS+"""
    FROM news_ticker_map m FORCE INDEX (idx_news_ticker_map_symbol)
    STRAIGHT_JOIN news_raw n ON n.article_id=m.article_id
    WHERE m.symbol=:symbol AND n.published_at_utc>=:start AND n.published_at_utc<:end
      AND n.ingestion_source IN ('eodhd','alpaca') LIMIT :limit"""
META_SQL = META_FIELDS.replace('m.', 'p.').replace('p.created_at map_created_at,p.updated_at map_updated_at',
    'p.map_created_at,p.map_updated_at')+"""
    FROM (
      SELECT k.article_id,m.symbol,m.created_at map_created_at,m.updated_at map_updated_at,m.is_primary_ticker
      FROM news_raw k FORCE INDEX (idx_news_raw_source_published)
      STRAIGHT_JOIN news_ticker_map m ON m.article_id=k.article_id AND m.symbol=:symbol
      WHERE k.published_at_utc>=:start AND k.published_at_utc<:end
        AND k.ingestion_source IN ('eodhd','alpaca') LIMIT :limit
    ) p STRAIGHT_JOIN news_raw n ON n.article_id=p.article_id"""


def run(output, source=SOURCE, months=PERIODS, row_cap=5000):
    output, source = Path(output), Path(source)
    with exclusive_run(output):
        if (output/'protocol.json').exists():
            raise ValueError('New output folder required; never overwrite a frozen protocol')
        protocol = freeze_protocol(source, months, row_cap)
        atomic_json(output/'protocol.json', protocol)
        atomic_json(output/'progress.json', dict(status='RUNNING', phase='READ_ONLY_METADATA'))
        candidates = pd.read_parquet(source, columns=['date','symbol','oracle_rank','year'])
        candidates['date'] = pd.to_datetime(candidates.date).dt.normalize()
        candidates = candidates[candidates.date.dt.strftime('%Y-%m').isin(months)].copy()
        if candidates.empty or candidates.duplicated(['date','symbol']).any():
            raise ValueError('Invalid candidate sample')
        if not candidates.groupby('date').oracle_rank.apply(lambda x:set(x)==set(range(1,6))).all():
            raise ValueError('Original complete TOP5 required')
        calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
        sessions = calendar.sessions(candidates.date.min().date(), candidates.date.max().date())
        closes = {pd.Timestamp(s.session_date):pd.Timestamp(s.close_at_utc) for s in sessions if s.is_open}
        # Reuse the configured credentials without ever printing a connection URL.
        base = get_sqlalchemy_engine()
        engine = create_engine(base.url, connect_args={'read_timeout':25, 'write_timeout':10}, echo=False)
        base.dispose()
        all_rows, truncations, probes, query_errors = [], [], [], []
        try:
            with engine.connect() as conn:
                conn.execute(text("SET SESSION time_zone='+00:00'"))
                conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
                if conn.execute(text('SELECT DATABASE()')).scalar_one() != 'alpha_trade':
                    raise ValueError('US alpha_trade required')
                for month in months:
                    sub = candidates[candidates.date.dt.strftime('%Y-%m').eq(month)]
                    if sub.empty:
                        raise ValueError('Missing month in candidates: '+month)
                    start = pd.Timestamp(month+'-01')-pd.Timedelta(days=30)
                    end = pd.Timestamp(month+'-01')+pd.offsets.MonthBegin(1)
                    for symbol in sorted(sub.symbol.unique()):
                        atomic_json(output/'progress.json',dict(status='RUNNING',month=month,
                            symbol=symbol,phase='READ_ONLY_METADATA',rows=len(all_rows)))
                        values = dict(symbol=symbol, start=start.to_pydatetime(),
                                      end=end.to_pydatetime(), limit=row_cap+1)
                        count = conn.execute(text('SELECT /*+ MAX_EXECUTION_TIME(15000) */ COUNT(*) '
                            'FROM news_ticker_map FORCE INDEX (idx_news_ticker_map_symbol) WHERE symbol=:symbol'),
                            dict(symbol=symbol)).scalar_one()
                        plan = 'SYMBOL_FIRST' if count<=20000 else 'PERIOD_FIRST'
                        try:
                            part = [dict(x) for x in conn.execute(text(
                                MAP_FIRST_SQL if plan=='SYMBOL_FIRST' else META_SQL), values).mappings()]
                        except OperationalError as exc:
                            if getattr(exc.orig,'args',(None,))[0] != 3024:
                                raise
                            query_errors.append(dict(month=month,symbol=symbol,sql_errno=3024))
                            probes.append(dict(month=month,symbol=symbol,rows=None,error='QUERY_TIMEOUT',plan=plan))
                            LOG.warning('Lecture bornée indisponible %s/%s, jamais comptée comme absence',month,symbol)
                            continue
                        capped = len(part)>row_cap
                        if capped:
                            truncations.append(dict(month=month,symbol=symbol))
                        all_rows.extend(part[:row_cap])
                        probes.append(dict(month=month,symbol=symbol,rows=min(len(part),row_cap),capped=capped,plan=plan))
                    LOG.info('Metadata %s: %d symboles; %d associations cumulées',month,sub.symbol.nunique(),len(all_rows))
                    atomic_json(output/'progress.json',dict(status='RUNNING',month=month,rows=len(all_rows)))
                news = pd.DataFrame(all_rows)
                if news.empty:
                    raise ValueError('No text metadata returned')
                news = news.drop_duplicates(['article_id','symbol']).copy()
                for col in STAMPS:
                    news[col] = pd.to_datetime(news[col],utc=True)
                news['headline_screen'] = news.headline.map(headline_screen)
                panel = audit_panel(candidates,news,closes)
                unknown_keys={(x['month'],x['symbol']) for x in query_errors+truncations}
                panel['corpus_query_incomplete']=[(str(r.date)[:7],r.symbol) in unknown_keys
                    for r in panel.itertuples(index=False)]
                # Deterministic content sample: half screened, half other, no outcome loaded.
                articles = news.drop_duplicates('article_id').copy()
                articles['sample_key'] = articles.article_id.map(lambda x:hashlib.sha256(x.encode()).hexdigest())
                samples = []
                for year in (2025,2026):
                    for screened in (True,False):
                        picked = articles[articles.headline_screen.eq(screened) &
                            articles.published_at_utc.dt.year.eq(year)].sort_values('sample_key').head(6)
                        for row in picked.to_dict('records'):
                            value = conn.execute(text('SELECT /*+ MAX_EXECUTION_TIME(15000) */ '
                                'LEFT(content,12000) content_excerpt,SHA2(content,256) content_sha256 '
                                'FROM news_raw WHERE article_id=:id'),dict(id=row['article_id'])).mappings().one()
                            row['changed_during_audit'] = value['content_sha256']!=row['content_sha256']
                            row['content_excerpt'] = None if row['changed_during_audit'] else value['content_excerpt']
                            row['excerpt_truncated'] = (row['content_chars'] or 0)>12000
                            row['review_status'] = 'UNREVIEWED'
                            samples.append(row)
                conn.rollback()
        finally:
            engine.dispose()
        if digest(source)!=protocol['candidate_sha256']:
            raise ValueError('Candidate archive changed during audit')
        news.to_parquet(output/'news_metadata.parquet',index=False)
        panel.to_parquet(output/'candidate_availability.parquet',index=False)
        atomic_json(output/'content_sample.json',samples)
        atomic_json(output/'query_coverage.json',dict(probes=probes,truncations=truncations,query_errors=query_errors))
        summary = []
        for year,part in panel.groupby('year'):
            relevant_symbols = set(part.symbol)
            relevant = news[news.symbol.isin(relevant_symbols) & news.published_at_utc.dt.year.eq(year)]
            summary.append(dict(year=int(year),candidate_days=len(part),distinct_symbols=len(relevant_symbols),
                article_mappings=len(relevant),distinct_articles=relevant.article_id.nunique(),
                has_recent_text_days=int(part.recent_article_mappings.gt(0).sum()),
                has_guarded_recent_text_days=int(part.recent_guarded_mappings.gt(0).sum()),
                has_guarded_last24h_days=int(part.last_24h_guarded_mappings.gt(0).sum()),
                screened_candidate_days=int(part.screened_last_24h.gt(0).sum()),
                screened_guarded_candidate_days=int(part.screened_guarded_last_24h.gt(0).sum()),
                novelty_context_10_days=int(part.available_novelty_context_count.ge(10).sum())))
        # This command ends at qualification, even if a later content review can pass.
        report = dict(status='COMPLETED_FEASIBILITY_ONLY', years=summary,
            verdict='BLOCKED_HISTORICAL_TEXT_PIT' if any(x['has_guarded_recent_text_days']==0 for x in summary)
                else 'CONTENT_AND_CORPUS_COVERAGE_REVIEW_REQUIRED',
            sample_months=list(months),truncations=truncations,query_errors=query_errors,
            incomplete_query_candidate_days=int(panel.corpus_query_incomplete.sum()),metadata_mappings=len(news),
            unique_articles=news.article_id.nunique(),body_present_mappings=int(news.content_chars.ge(200).sum()),
            publication_precision_reasons=dict(Counter(raw_publication_reason(r.provider_publication,r.published_at_utc)
                or 'EXPLICIT_TIMESTAMP_MATCHES' for r in news.itertuples(index=False))),
            payload_json_types=news.payload_json_type.value_counts().to_dict(),
            ingestion_sources=news.ingestion_source.value_counts().to_dict(),
            first_db_insert_utc=str(news.created_at.min()),last_db_insert_utc=str(news.created_at.max()),
            code_findings=['Mutable news_raw upserts overwrite content and raw_payload',
                'Mutable news_ticker_map upserts overwrite mapping metadata',
                'created_at is local first insertion, not historical provider availability',
                'No append-only historical text version archive qualified',
                'Incomplete corpus cannot establish no-event days or reliable novelty'],
            limitations=['Bounded four-month TOP5 sample, not exhaustive universe audit',
                'Last24h event window excludes older weekend releases by design; not a production event window',
                'Overlap article/symbol mappings are deduplicated, no-event is not neutral',
                'Current timestamps are only a conservative diagnostic, not an immutable-vintage certification'],
            price_outcomes_loaded=False,training=False,pnl=False,sql_writes=False,
            hashes={name:digest(output/name) for name in ('protocol.json','news_metadata.parquet',
                'candidate_availability.parquet','content_sample.json','query_coverage.json')},
            source_files={str(p):digest(p) for p in (source,Path(__file__),Path('event_sentiment/db_io.py'),
                Path('event_sentiment/ingestion.py'),Path('service/eodhd/news_client.py'))})
        atomic_json(output/'report.json',report)
        atomic_json(output/'progress.json',dict(status='COMPLETED',verdict=report['verdict']))
        return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        print(json.dumps(run(args.output),indent=2,default=str))
    except Exception as exc:
        original_args = getattr(getattr(exc,'orig',None),'args',())
        error_code = original_args[0] if original_args and isinstance(original_args[0],int) else None
        if args.output.exists():
            path=args.output/'progress.json'
            progress=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
            atomic_json(path,dict(progress,status='FAILED',error_type=type(exc).__name__,sql_errno=error_code))
        # Do not log SQL connection/credential details or database payloads.
        LOG.error('Audit arrêté: %s, code SQL=%s',type(exc).__name__,error_code)
        raise SystemExit(1) from None


if __name__=='__main__':
    main()
