"""Read-only collection/5m-window feasibility; no returns, training or SQL writes.

Consumes a frozen prospective evidence/review pack. Coverage of an unqualified
article is only a technical diagnostic, never approval of its ticker or event.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path

import yaml
from sqlalchemy import create_engine, text

from scripts.research import us_news_event_qualification as evidence

FIVE = timedelta(minutes=5)
VERSION = 'FINANCING_FEASIBILITY_V2'


def read_pack(root):
    report = json.loads((root/'report.json').read_text(encoding='utf-8'))
    for name, expected in report['files'].items():
        if Path(name).name != name or evidence.sha(root/name) != expected:
            raise ValueError('Changed evidence pack')
    items = json.loads((root/'evidence.json').read_text(encoding='utf-8'))
    protocol = json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    review_path = root/'technical_review_result.json'
    review = json.loads(review_path.read_text(encoding='utf-8'))
    if (review['report_sha256'] != evidence.sha(root/'report.json') or
            review['review_sha256'] != evidence.sha(root/'technical_review_filled.json')):
        raise ValueError('Review does not bind this pack')
    keys = [r['evidence_key'] for r in items]
    reviewed = [r['evidence_key'] for r in review['results']]
    if len(set(keys)) != len(keys) or len(set(reviewed)) != len(reviewed) or not set(reviewed) <= set(keys):
        raise ValueError('Duplicate or unknown evidence keys')
    return protocol, report, items, review


def windows(publication, sessions):
    """Six completed 5m bars before and six after; official-calendar boundaries.

    RTH: exclude the bar containing an off-grid publication from both windows.
    Outside RTH: last 30m of preceding session vs first 30m of next session.
    Reaction is observable only at after_end, not at the publication timestamp.
    """
    publication = evidence.utc(publication)
    if publication is None:
        return dict(status='UNQUALIFIED_PUBLICATION_TIME')
    sessions = sorted((s for s in sessions if s.is_open), key=lambda s: s.open_at_utc)
    for i, session in enumerate(sessions):
        op, cl = evidence.utc(session.open_at_utc), evidence.utc(session.close_at_utc)
        if publication >= cl:
            continue
        if publication < op:
            if i == 0:
                return dict(status='PREVIOUS_SESSION_UNAVAILABLE')
            before_end = evidence.utc(sessions[i-1].close_at_utc)
            after_start = op
            bucket = 'outside_regular_session'
        else:
            seconds = int(publication.timestamp())
            floor = datetime.fromtimestamp(seconds//300*300, timezone.utc)
            before_end = floor
            after_start = floor if publication == floor else floor+FIVE
            bucket = 'regular_session'
        before_start, after_end = before_end-6*FIVE, after_start+6*FIVE
        if bucket == 'regular_session' and (before_start < op or after_end > cl):
            return dict(status='INSUFFICIENT_ROOM_WITHIN_REGULAR_SESSION', bucket=bucket)
        return dict(status='PLANNED', bucket=bucket, before_start=before_start,
            before_end=before_end, after_start=after_start, after_end=after_end,
            reaction_available_no_earlier_than=after_end)
    return dict(status='NEXT_SESSION_UNAVAILABLE')


def bar_ok(row):
    try:
        prices = {k: float(row[k]) for k in ('open','high','low','close')}
        return (row['market_code']=='US_EQ' and row['interval_code']=='5m'
            and row['session_tag']=='regular' and row['data_adjustment']=='raw'
            and row['is_filled']==0 and float(row['volume']) > 0
            and all(math.isfinite(v) and v > 0 for v in prices.values())
            and math.isfinite(float(row['volume']))
            and prices['high'] >= max(prices['open'],prices['close'])
            and prices['low'] <= min(prices['open'],prices['close'])
            and evidence.utc(row['bar_end_timestamp'], database=True)
                == evidence.utc(row['bar_timestamp'], database=True)+FIVE)
    except (ValueError,TypeError,KeyError):
        return False


def assess(plan, rows, cutoff):
    if plan['status'] != 'PLANNED':
        return dict(status=plan['status'], sources=[])
    if plan['after_end'] > cutoff:
        return dict(status='WINDOW_NOT_YET_COMPLETE', sources=[])
    expected = {start+i*FIVE for start in (plan['before_start'],plan['after_start']) for i in range(6)}
    sources = {}
    for row in rows:
        key = row['provider'], row['data_source']
        sources.setdefault(key, []).append(row)
    checked = []
    for (provider, source), group in sorted(sources.items()):
        relevant = [r for r in group if evidence.utc(r['bar_timestamp'], database=True) in expected]
        stamps = [evidence.utc(r['bar_timestamp'], database=True) for r in relevant]
        valid = {evidence.utc(r['bar_timestamp'], database=True) for r in relevant if bar_ok(r)}
        duplicate = len(stamps) != len(set(stamps))
        checked.append(dict(provider=provider, data_source=source, expected_bars=12,
            valid_bars=len(valid), duplicate_timestamp=duplicate,
            complete=valid==expected and not duplicate,
            historical_availability_certified=False))
    return dict(status='COMPLETE_SINGLE_SOURCE_WINDOW' if any(r['complete'] for r in checked)
        else 'MISSING_OR_INVALID_INTRADAY_WINDOW', sources=checked)


def collection_config(config_path, plans_root):
    cfg = yaml.safe_load(config_path.read_text(encoding='utf-8'))['us_pipeline']
    batch_path=config_path.parent/'batch.yaml'
    daily={}
    if batch_path.exists():
        batch=yaml.safe_load(batch_path.read_text(encoding='utf-8')) or {}
        section=batch.get('eodhd_news_ingestion_sync') or {}
        # Read only public scheduling/role fields, never credentials or commands.
        daily={key:section.get(key) for key in ('enabled','status','market_code','provider',
            'run_days','run_hours','run_minutes','timezone')}
    daily_configured=(daily.get('enabled') is True and daily.get('market_code')=='US_EQ'
        and daily.get('provider')=='eodhd' and str(daily.get('status','')).startswith('ACTIVE')
        and set(str(daily.get('run_days','')).split(','))==set('0123456'))
    plans = []
    for path in sorted(plans_root.glob('*/plan.json'))[-6:]:
        payload = json.loads(path.read_text(encoding='utf-8'))
        numbers = payload.get('selected_step_numbers')
        plans.append(dict(path=str(path), sha256=evidence.sha(path),
            trade_date=payload.get('trade_date'), selected_step_numbers=numbers,
            news_selected=8 in numbers if numbers is not None else None))
    return dict(steps=cfg['steps'], steps_friday=cfg['steps_friday'],
        news_selected_mon_thu=8 in cfg['steps'], news_selected_friday=8 in cfg['steps_friday'],
        separate_daily_ingestion_configured=daily_configured,daily_ingestion=daily,
        daily_ingestion_batch_sha256=evidence.sha(batch_path) if batch_path.exists() else None,
        daily_sentiment_scoring_demonstrated=False,
        config_sha256=evidence.sha(config_path), frozen_plans=plans,
        config_modified=False, task_installation_verified=False)


def run(pack, output, *, root=Path('.')):
    protocol, source_report, items, review = read_pack(pack)
    if len(items)>200:
        raise ValueError('Bounded feasibility cap exceeded; no partial success')
    if output.exists():
        raise FileExistsError('Use fresh immutable output directory')
    from common.market_calendar import get_market_calendar
    from database.connection import get_sqlalchemy_engine
    cutoff = evidence.utc(protocol['cutoff_utc'])
    start = evidence.utc(protocol['since_utc'])
    calendar = get_market_calendar('US_EQ', allow_us_weekday_fallback=False)
    publications = [evidence.utc(r['publication_utc']) for r in items if r['publication_utc']]
    sessions = calendar.sessions((min(publications,default=start)-timedelta(days=10)).date(),
        (max(publications,default=cutoff)+timedelta(days=10)).date())
    output.mkdir(parents=True)
    config = collection_config(root/'config.yaml',root/'artifacts/operations/us_pipeline')
    engine = create_engine(get_sqlalchemy_engine().url, pool_size=1,max_overflow=0,pool_pre_ping=True,
        connect_args={'connect_timeout':10,'read_timeout':25,'write_timeout':10},echo=False)
    diagnostics, cache = [], {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise ValueError('US alpha_trade required; no FR/CN access')
            checkpoints = [dict(r) for r in conn.execute(text('''SELECT source_name,status,
                COUNT(*) symbol_count,MAX(news_ingested_at) latest_success,
                MAX(watermark_published_at_utc) latest_watermark,
                SUM(last_error IS NOT NULL AND last_error<>'') checkpoints_with_error
                FROM news_ingestion_checkpoint GROUP BY source_name,status''')).mappings()]
            for row in checkpoints:
                # MySQL SUM(boolean) is Decimal, unlike COUNT; retain an integer count.
                row['checkpoints_with_error']=int(row['checkpoints_with_error'] or 0)
            receipts = [dict(r) for r in conn.execute(text('''SELECT DATE(available_at) available_day_utc,
                origin,COUNT(*) receipts,COUNT(DISTINCT article_id) articles,
                MIN(observed_at) first_observed,MAX(available_at) latest_available
                FROM news_archive_observations WHERE observed_at<:cutoff
                GROUP BY DATE(available_at),origin ORDER BY available_day_utc'''),
                {'cutoff':cutoff.replace(tzinfo=None)}).mappings()]
            # At most 12 indexed rows per source are needed for each two-window query.
            for item in items:
                plan = windows(item['publication_utc'],sessions)
                rows = []
                if plan['status']=='PLANNED' and plan['after_end']<=cutoff:
                    key = (item['symbol'],plan['before_start'],plan['after_start'])
                    if key not in cache:
                        params = {'symbol':item['symbol'],**{k:plan[k].replace(tzinfo=None)
                            for k in ('before_start','before_end','after_start','after_end')}}
                        fetched = [dict(r) for r in conn.execute(text('''SELECT symbol,bar_timestamp,
                            bar_end_timestamp,interval_code,market_code,provider,data_source,
                            open,high,low,close,volume,is_filled,data_adjustment,session_tag,observed_at,payload_hash
                            FROM stock_bars_intraday WHERE symbol=:symbol AND interval_code='5m'
                            AND ((bar_timestamp>=:before_start AND bar_timestamp<:before_end)
                              OR (bar_timestamp>=:after_start AND bar_timestamp<:after_end))
                            ORDER BY bar_timestamp,data_source LIMIT 241'''),params).mappings()]
                        if len(fetched)>240:
                            raise ValueError('Intraday query cap exceeded')
                        for row in fetched:
                            for field in ('open','high','low','close'):
                                row[field]=float(row[field])
                        cache[key]=fetched
                    rows = cache[key]
                diagnostics.append(dict(evidence_key=item['evidence_key'],symbol=item['symbol'],
                    article_id=item['article_id'],screened=item['screened'],plan=plan,
                    coverage=assess(plan,rows,cutoff),identity_event_approved=False,
                    available_at=evidence.utc(item['text_available_at']),
                    combined_evidence_available_at=max(evidence.utc(item['text_available_at']),
                        evidence.utc(item['mapping_available_at'])),
                    window_ended_before_evidence_available=(plan.get('after_end') is not None and
                        plan['after_end']<max(evidence.utc(item['text_available_at']),
                            evidence.utc(item['mapping_available_at']))),
                    price_returns_computed=False,not_an_event_approval=True))
            conn.rollback()
    finally:
        engine.dispose()
    known = {r['evidence_key'] for r in items}
    qualified = [r for r in review['results'] if r['evidence_key'] in known
        and r['status']=='QUALIFIED_RESEARCH_EVENT']
    complete = {r['evidence_key'] for r in diagnostics if r['coverage']['status']=='COMPLETE_SINGLE_SOURCE_WINDOW'}
    blockers = []
    if source_report['query_truncated']:
        blockers.append('ARCHIVE_TRUNCATED')
    if not qualified:
        blockers.append('NO_QUALIFIED_NEW_PRIMARY_FINANCING')
    if not any(r['evidence_key'] in complete for r in qualified):
        blockers.append('NO_QUALIFIED_EVENT_WITH_INTRADAY_WINDOW')
    if not config['news_selected_mon_thu'] and not config['separate_daily_ingestion_configured']:
        blockers.append('NO_DAILY_NEWS_INGESTION_CONFIGURED')
    result = dict(version=VERSION,status='BLOCKED_DATA_FEASIBILITY' if blockers else 'REQUIRES_FROZEN_EXPERIMENT_PROTOCOL',
        created_at_utc=datetime.now(timezone.utc),source_cutoff_utc=cutoff,blockers=blockers,
        archive_articles=source_report['article_ids'],archive_observations=source_report['confirmed_observations'],
        article_symbol_pairs=len(items),screened_pairs=source_report['screened_pairs'],
        unique_screened_texts=source_report['unique_screened_texts'],
        qualified_review_pairs=len(qualified),qualified_distinct_articles=len({
            r['article_id'] for r in items if r['evidence_key'] in {v['evidence_key'] for v in qualified}}),
        technical_window_counts=dict(Counter(r['coverage']['status'] for r in diagnostics)),
        technical_complete_pairs=len(complete),
        technical_complete_screened_pairs=sum(r['screened'] and r['evidence_key'] in complete for r in diagnostics),
        windows_ended_before_evidence_available=sum(r['window_ended_before_evidence_available'] for r in diagnostics),
        pending_receipts=source_report['pending_receipts'],collection_configuration=config,
        checkpoints=checkpoints,archive_receipt_days=receipts,
        population_selection=('hash-selected bounded review subset of frozen parent corpus' if
            source_report.get('sample_not_complete_corpus') else 'all frozen archive/universe pairs')+
            '; no future return or Oracle selection',
        archive_observations_count_scope=source_report.get('observations_count_scope','source pack'),
        limits={'pairs':200,'bars_per_query':240,'sql_timeout_ms':15000},
        historical_data_retrieval_not_pit_proof=True,technical_coverage_not_identity_or_novelty=True,
        independent_review_certified=False,api_calls=0,llm_cost_usd=0,sql_writes=False,
        production_changes=False,training=False,returns_computed=False,economic_test=False,
        source_hashes={str(pack/name):evidence.sha(pack/name) for name in
            ('protocol.json','report.json','evidence.json','technical_review_result.json','technical_review_filled.json')},
        code_sha256=evidence.sha(Path(__file__)))
    evidence.save(output/'intraday_windows.json',diagnostics)
    evidence.save(output/'intraday_rows.json',[
        dict(symbol=k[0],before_start=k[1],after_start=k[2],rows=v) for k,v in cache.items()])
    result['files']={p.name:evidence.sha(p) for p in output.iterdir() if p.is_file()}
    evidence.save(output/'report.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=run(args.pack,args.output)
    print(json.dumps({k:report[k] for k in ('status','blockers','article_symbol_pairs',
        'qualified_distinct_articles','technical_window_counts')},ensure_ascii=False))
