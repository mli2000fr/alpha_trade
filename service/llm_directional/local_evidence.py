"""Bounded, frozen local evidence at a REAL prospective cutoff. SELECT only.

No mutable news/sentiment fallback, provider calls, retrospective backdating,
qualification writes or price-outcome selection. Used by BOTH LLM modes.
"""
from datetime import datetime, timedelta, timezone
import json
from zoneinfo import ZoneInfo

from sqlalchemy import inspect, text

from .repository import dumps, digest
from .prompts import VERSION, DEEPSEEK_SEARCH_VERSION


CONSENSUS_TABLE='stock_analyst_consensus_eodhd_history'


def _utc(value):
    if isinstance(value,str):
        value=datetime.fromisoformat(value.replace('Z','+00:00'))
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _source(row):
    from service.eodhd.consensus_snapshot import FIELDS
    values={key:row.get(key) for key in FIELDS}
    facts=dict(symbol=row['symbol'],snapshot_date=str(row['snapshot_date']),
        fiscal_period_end=str(row['fiscal_period_end']),horizon_raw=row['horizon_raw'],
        currency=row.get('currency'),values=values)
    qualified=bool(row['units_qualified'] and row['fiscal_identity_qualified']
        and row['qualification_status'] in ('QUALIFIED','VALIDATED','PROSPECTIVE_QUALIFIED')
        and any(values.get(k) is not None for k in ('eps_avg','eps_current','revenue_avg')))
    return dict(source_id=f"consensus:{row['id']}:{row['raw_hash']}",kind='consensus',
        text=dumps(facts),available_at_utc=_utc(row['available_at']).isoformat(),
        observed_at_utc=_utc(row['observed_at']).isoformat(),run_id=row['run_id'],
        raw_hash=row['raw_hash'],qualification_status=row['qualification_status'],
        units_qualified=bool(row['units_qualified']),fiscal_identity_qualified=bool(row['fiscal_identity_qualified']),
        historical_pit_qualified=bool(row['historical_pit_qualified']),
        eligible_for_direction=qualified,
        caveat='Snapshot received at the recorded time, NOT historical fiscal-date PIT. '
               'Unqualified units/fiscal identity: provisional context only; do not assume USD or revenue scale.')


def _consensus(conn,symbol,cutoff,config):
    from service.eodhd.consensus_snapshot import FIELDS
    params=dict(symbol=symbol,cutoff=cutoff.replace(tzinfo=None),
        since=(cutoff-timedelta(days=config.consensus_max_age_days)).replace(tzinfo=None),
        day=cutoff.astimezone(ZoneInfo('America/New_York')).date(),cap=config.consensus_max_periods)
    bounds="""provider='eodhd' AND symbol=:symbol AND available_at<:cutoff
        AND observed_at<:cutoff AND available_at>=observed_at AND available_at>=:since
        AND snapshot_date<=:day"""
    snapshot=conn.execute(text(f'SELECT MAX(snapshot_date) FROM {CONSENSUS_TABLE} WHERE {bounds}'),params).scalar()
    if snapshot is None:
        return dict(status='NO_RECENT_OBSERVATION',sources=[])
    params['snapshot']=snapshot
    # An earnings period may have CLOSED weeks before its results announcement.
    # Do not drop that near-term consensus just because its fiscal end is < J.
    params['fiscal_since']=params['day']-timedelta(days=120)
    fields=['id','symbol','snapshot_date','fiscal_period_end','horizon_raw','currency',
        'observed_at','available_at','run_id','raw_hash','qualification_status','units_qualified',
        'fiscal_identity_qualified','historical_pit_qualified',*FIELDS]
    columns=','.join('`'+f+'`' for f in fields)
    distance=('ABS(DATEDIFF(fiscal_period_end,:day))' if conn.dialect.name=='mysql'
              else 'ABS(julianday(fiscal_period_end)-julianday(:day))')
    rows=[]
    for horizon in ('0q','+1q','0y','+1y'):
        candidates=conn.execute(text(f'''SELECT {columns} FROM {CONSENSUS_TABLE}
            WHERE {bounds} AND snapshot_date=:snapshot AND fiscal_period_end>=:fiscal_since
            AND horizon_raw=:horizon ORDER BY {distance},fiscal_period_end LIMIT 1'''),
            dict(params,horizon=horizon)).mappings().first()
        if candidates:
            rows.append(dict(candidates))
        if len(rows)>=config.consensus_max_periods:
            break
    sources=[]
    for row in rows:
        item=_source(row)
        history=[]
        if config.consensus_history_count:
            history_params=dict(params,period=row['fiscal_period_end'],horizon=row['horizon_raw'],
                                history_cap=config.consensus_history_count)
            prior=conn.execute(text(f'''SELECT {columns} FROM {CONSENSUS_TABLE}
                WHERE {bounds} AND fiscal_period_end=:period AND horizon_raw=:horizon
                AND snapshot_date<:snapshot ORDER BY snapshot_date DESC LIMIT :history_cap'''),history_params).mappings()
            history=[_source(dict(old)) for old in prior]
        item['prior_actual_snapshots']=history
        sources.append(item)
    return dict(status='AVAILABLE' if sources else 'NO_RELEVANT_FISCAL_PERIOD',
        snapshot_date=str(snapshot),period_limit=config.consensus_max_periods,sources=sources,
        note='Nearest reported period per raw horizon, including recently closed fiscal periods (120-day lower bound). '
             'Bounded sample; fiscal horizon identity remains unqualified unless explicitly validated.')


def _news(conn,symbol,cutoff,config):
    if config.local_news_max_articles==0:
        return dict(status='DISABLED',sources=[])
    # Exact symbol test in the archived mapping, never a mutable ticker map.
    membership=("JSON_CONTAINS(m.mapping_rows,JSON_OBJECT('symbol',:symbol))" if conn.dialect.name=='mysql'
        else "EXISTS (SELECT 1 FROM json_each(m.mapping_rows) j WHERE json_extract(j.value,'$.symbol')=:symbol)")
    receipt="available_at IS NOT NULL AND available_at<:cutoff AND observed_at<:cutoff"
    query=f'''SELECT v.*,m.id AS map_id,m.mapping_context,o.id AS map_receipt_id,
        a.id AS text_receipt_id,a.available_at AS text_available_at,o.available_at AS map_available_at
        FROM news_archive_observations o JOIN news_ticker_map_versions m ON m.id=o.mapping_version_id
        JOIN news_raw_versions v ON v.id=m.raw_version_id
        JOIN news_archive_observations a ON a.raw_version_id=v.id AND a.article_id=o.article_id
        WHERE {membership} AND o.origin='PROVIDER_COLLECTION' AND a.origin='PROVIDER_COLLECTION'
        AND a.stream_key='article' AND o.stream_key LIKE 'mapping:payload:%'
        AND o.available_at<:cutoff AND o.observed_at<:cutoff AND o.available_at>=o.observed_at
        AND a.available_at<:cutoff AND a.observed_at<:cutoff AND a.available_at>=a.observed_at
        AND m.payload_scope_complete=1 AND v.ingestion_source IN ('eodhd','alpaca')
        AND v.publication_precision='EXPLICIT_TIMEZONE'
        AND v.publication_utc>=:since AND v.publication_utc<:cutoff
        AND o.id=(SELECT MAX(id) FROM news_archive_observations
            WHERE article_id=o.article_id AND stream_key=o.stream_key AND {receipt})
        AND a.id=(SELECT MAX(id) FROM news_archive_observations
            WHERE article_id=a.article_id AND stream_key='article' AND {receipt})
        ORDER BY v.publication_utc DESC,v.article_id,m.id DESC LIMIT :cap'''
    params=dict(symbol=symbol,cutoff=cutoff.replace(tzinfo=None),
        since=(cutoff-timedelta(days=config.max_source_age_days)).replace(tzinfo=None),
        cap=config.local_news_max_articles*5+1)
    rows=[dict(r) for r in conn.execute(text(query),params).mappings()]
    sources,seen=[],set()
    for row in rows:
        if row['article_id'] in seen:
            continue
        seen.add(row['article_id'])
        context=json.loads(row['mapping_context']) if isinstance(row['mapping_context'],str) else row['mapping_context']
        source_text='\n'.join(f'{name}: {row.get(name) or ""}' for name in ('headline','summary','content'))
        truncated=len(source_text)>config.local_news_max_chars
        sources.append(dict(source_id=f"news:{row['id']}:{row['map_id']}",kind='news',
            article_id=row['article_id'],provider=row['ingestion_source'],url=row.get('url'),
            text=source_text[:config.local_news_max_chars],text_truncated=truncated,
            source_text_hash=row['text_hash'],publication_utc=_utc(row['publication_utc']).isoformat(),
            available_at_utc=max(_utc(row['text_available_at']),_utc(row['map_available_at'])).isoformat(),
            raw_version_id=row['id'],mapping_version_id=row['map_id'],
            text_receipt_id=row['text_receipt_id'],mapping_receipt_id=row['map_receipt_id'],
            identity_qualified=isinstance(context,dict) and context.get('identity_qualified') is True,
            eligible_for_direction=isinstance(context,dict) and context.get('identity_qualified') is True,
            caveat='Provider ticker mapping alone is not independent issuer validation. No versioned sentiment score supplied.'))
        if len(sources)>=config.local_news_max_articles:
            break
    return dict(status='AVAILABLE' if sources else 'NO_QUALIFIED_ARCHIVED_NEWS',sources=sources,
        bounded_sample=True,candidate_query_truncated=len(rows)==params['cap'],
        note='Recent received versions only, no mutable news/sentiment fallback or exhaustive coverage claimed.')


def enrich_contexts(engine,contexts,config,cutoff):
    if engine.dialect.name=='mysql' and engine.url.database!='alpha_trade':
        raise ValueError('Contexte LLM réservé au marché US')
    cutoff=_utc(cutoff)
    if cutoff>datetime.now(timezone.utc):
        raise ValueError('Cutoff LLM futur interdit')
    names=set(inspect(engine).get_table_names())
    result=[]
    with engine.connect() as conn:
        for original in contexts:
            protocol=(DEEPSEEK_SEARCH_VERSION if config.provider=='deepseek'
                      and config.analysis_mode=='web_search' else VERSION)
            item=dict(original,analysis_protocol=protocol,analysis_mode=config.analysis_mode,
                      evidence_cutoff_utc=cutoff.isoformat(),assessment_objective='QUALITATIVE_TREND')
            consensus=_consensus(conn,item['symbol'],cutoff,config) if CONSENSUS_TABLE in names else dict(status='TABLE_MISSING',sources=[])
            news_tables={'news_raw_versions','news_ticker_map_versions','news_archive_observations'}
            news=_news(conn,item['symbol'],cutoff,config) if news_tables.issubset(names) else dict(status='ARCHIVE_TABLES_MISSING',sources=[])
            item['local_data_status']=dict(consensus={k:v for k,v in consensus.items() if k!='sources'},
                                           news={k:v for k,v in news.items() if k!='sources'})
            item['local_evidence']=consensus['sources']+news['sources']
            item['local_evidence_sha256']=digest(item['local_evidence'])
            result.append(item)
    return result
