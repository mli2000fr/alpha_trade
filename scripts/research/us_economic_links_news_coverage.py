"""Read-only availability count for the five document-supported counterparties.

No provider/LLM/download, price/outcome query or economic inference.
"""
from datetime import timedelta
import json
from pathlib import Path
import re

import pandas as pd
from sqlalchemy import text,bindparam,event

from scripts.research.us_economic_links_feasibility import readonly,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_economic_links_feasibility/20261102-v4')
PEERS=['AMAT','LRCX','CTVA','AVT','SMTC']


def run(root=ROOT):
    from database.connection import get_sqlalchemy_engine
    protocol=read(root/'protocol.json')
    cutoff=pd.Timestamp(protocol['frozen_signal_cutoff_utc'])
    start=cutoff-pd.Timedelta(days=7)
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    event.listen(engine,'before_cursor_execute',readonly)
    allrows=[]
    try:
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=20000'))
            query=text('''SELECT n.article_id,m.symbol,n.ingestion_source,n.published_at_utc,
                n.created_at,n.updated_at,m.created_at map_created_at,m.updated_at map_updated_at,
                m.is_primary_ticker,CHAR_LENGTH(n.content) content_chars,
                COALESCE(JSON_UNQUOTE(JSON_EXTRACT(JSON_UNQUOTE(n.raw_payload),'$.created_at')),
                    JSON_UNQUOTE(JSON_EXTRACT(JSON_UNQUOTE(n.raw_payload),'$.date')),
                    JSON_UNQUOTE(JSON_EXTRACT(JSON_UNQUOTE(n.raw_payload),'$.published_at'))) provider_publication
                FROM news_ticker_map m FORCE INDEX (idx_news_ticker_map_symbol)
                STRAIGHT_JOIN news_raw n ON n.article_id=m.article_id
                WHERE m.symbol=:symbol AND n.ingestion_source IN ('eodhd','alpaca')
                AND n.published_at_utc>=:start AND n.published_at_utc<:cutoff LIMIT 2001''')
            for symbol in PEERS:
                rows=[dict(r) for r in conn.execute(query,dict(symbol=symbol,
                    start=start.tz_convert(None).to_pydatetime(),cutoff=cutoff.tz_convert(None).to_pydatetime())).mappings()]
                if len(rows)>2000:
                    raise ValueError('News sample truncated; no full-coverage conclusion')
                allrows.extend(rows)
        atomic_json(root/'peer-news-metadata.json',allrows)
        counts=[]
        for symbol in PEERS:
            rows=[r for r in allrows if r['symbol']==symbol]
            conservative=[]
            for row in rows:
                stamps=[pd.to_datetime(row[k],utc=True,errors='coerce') for k in
                        ['created_at','updated_at','map_created_at','map_updated_at']]
                before=all(pd.notna(s) and s<cutoff for s in stamps)
                precise=bool(re.search(r'\d[ T]\d{2}:\d{2}',str(row['provider_publication'])))
                if before and precise and (row['content_chars'] or 0)>=300:
                    conservative.append(row)
            counts.append(dict(symbol=symbol,article_mappings=len(rows),
                distinct_articles=len({r['article_id'] for r in rows}),
                with_at_least_300_chars=sum((r['content_chars'] or 0)>=300 for r in rows),
                conservative_pre_cutoff_version_candidates=len(conservative),
                primary_mapping_candidates=sum(bool(r['is_primary_ticker']) for r in conservative),
                semantic_attribution_verified=False,paywall_free_fulltext_verified=False))
        report=dict(status='METADATA_AVAILABILITY_ONLY',start_utc=start.isoformat(),cutoff_utc=cutoff.isoformat(),
            counterparty_scope=PEERS,counts=counts,
            note='Timestamps and text length are preliminary checks, not issuer-relevance/novelty or directional qualification.',
            llm_calls=0,http_calls=0,sql_writes=False,prices_or_outcomes=False,
            metadata_sha256=digest(root/'peer-news-metadata.json'),source_sha256=digest(__file__))
        atomic_json(root/'peer-news-coverage.json',report)
        return report
    finally:
        event.remove(engine,'before_cursor_execute',readonly);engine.dispose()


if __name__=='__main__':
    print(json.dumps(run(),default=str))
