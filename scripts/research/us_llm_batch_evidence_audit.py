"""Read-only inventory of US batch data worth considering for LLM context.

No provider/LLM call, training, risk/order action, schema creation or SQL DML.
Only a new local audit folder is written; observed coverage is not a signal test.
"""
import argparse
from datetime import datetime,timedelta,timezone
import hashlib
import json
from pathlib import Path

from sqlalchemy import bindparam,text
import yaml

TABLES={
    'stock_analyst_consensus_eodhd_history':('symbol','available_at'),
    'stock_earnings_calendar':('symbol','last_updated'),
    'stock_fundamentals_daily':('symbol','fetched_at'),
    'stock_market_cap_daily':('symbol','computed_at'),
    'sec_filing_raw':('symbol','available_at'),
    'sec_corporate_events':('symbol','available_at'),
    'sec_ownership_snapshots':('issuer_symbol','available_at'),
    'corporate_action_source_events':('symbol','available_at'),
    'security_master_snapshots':('symbol','available_at'),
    'stock_borrow_status_snapshots':('symbol','available_at'),
    'stock_quote_snapshots':('symbol','collected_at'),
    'stock_bars_daily_versions':('symbol','available_at'),
    'stock_option_snapshots':('underlying_symbol','available_at'),
    'stock_ipo_eodhd_history':('symbol','available_at'),
    'ticker_daily_sentiment_features':('symbol','updated_at'),
}


def query(conn,sql,params,*,symbols=None):
    if not sql.lstrip().upper().startswith('SELECT '):
        raise ValueError('SELECT only')
    statement=text(sql.replace('SELECT ','SELECT /*+ MAX_EXECUTION_TIME(15000) */ ',1))
    values=dict(params)
    if symbols is not None:
        statement=statement.bindparams(bindparam('symbols',expanding=True))
        values['symbols']=symbols
    return [dict(r) for r in conn.execute(statement,values).mappings()]


def run(output):
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    from common.universe_files import load_universe_file_symbols
    from database.connection import get_sqlalchemy_engine
    source='config/univers_batch/univers_filtred_tradable.txt'
    symbols=load_universe_file_symbols('universe-file:'+source)
    config=yaml.safe_load(Path('batch.yaml').read_text(encoding='utf-8-sig'))
    engine=get_sqlalchemy_engine()
    if engine.url.database!='alpha_trade':
        raise ValueError('US alpha_trade only')
    now=datetime.now(timezone.utc)
    params=dict(cutoff=now.replace(tzinfo=None),since=(now-timedelta(days=30)).replace(tzinfo=None),
                today=now.date(),future=(now+timedelta(days=35)).date())
    report=dict(audit_at_utc=now.isoformat(),sql_mode='READ_ONLY',universe=source,
        universe_count=len(symbols),universe_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),
        recent_window_days=30,tables={},checks={},errors={},
        p0_p1_catalog={k:{f:v.get(f) for f in ('priority','enabled','status','provider','tables')}
            for k,v in config.items() if v.get('priority') in ('P0','P1') and not k.startswith(('cn_','fr_'))})
    def check(conn,name,sql,*,scoped=True):
        print('Check '+name,flush=True)
        try:
            report['checks'][name]=query(conn,sql,params,symbols=symbols if scoped else None)
        except Exception as exc:
            report['errors'][name]=type(exc).__name__  # Never log DSNs, credentials or provider bodies.
    with engine.connect() as conn:
        conn.exec_driver_sql('SET SESSION TRANSACTION READ ONLY')
        report['server_clock']=query(conn,'SELECT DATABASE() AS db, UTC_TIMESTAMP() AS utc_now',{})
        for table,(symbol,stamp) in TABLES.items():
            print('Inspect '+table,flush=True)
            try:
                columns=query(conn,'SELECT column_name AS name FROM information_schema.columns '
                    'WHERE table_schema=DATABASE() AND table_name=:table ORDER BY ordinal_position',dict(table=table))
                if not columns:
                    report['tables'][table]=dict(status='MISSING')
                    continue
                counts=query(conn,f'''SELECT COUNT(*) AS rows_in_universe,
                    COUNT(DISTINCT `{symbol}`) AS symbols,MIN(`{stamp}`) AS earliest,
                    MAX(`{stamp}`) AS latest,COUNT(DISTINCT DATE(`{stamp}`)) AS observation_days
                    FROM `{table}` WHERE `{symbol}` IN :symbols AND `{stamp}`>=:since AND `{stamp}`<:cutoff''',
                    params,symbols=symbols)[0]
                report['tables'][table]=dict(status='AVAILABLE',timestamp_column=stamp,
                    timestamp_semantics='receipt' if stamp=='available_at' else 'mutable_update_or_fetch_time',
                    columns=[r['name'] for r in columns],recent=counts,
                    coverage_pct=100*counts['symbols']/len(symbols))
            except Exception as exc:
                report['errors'][table]=type(exc).__name__
        check(conn,'consensus_qualification','''SELECT qualification_status,units_qualified,
            fiscal_identity_qualified,COUNT(*) AS n,COUNT(DISTINCT symbol) AS symbols
            FROM stock_analyst_consensus_eodhd_history WHERE symbol IN :symbols
            AND available_at>=:since AND available_at<:cutoff
            GROUP BY qualification_status,units_qualified,fiscal_identity_qualified''')
        check(conn,'consensus_content','''SELECT COUNT(*) AS n,
            SUM(eps_current IS NOT NULL OR eps_avg IS NOT NULL) AS eps,
            SUM(revenue_avg IS NOT NULL) AS revenue,SUM(eps_analyst_count IS NOT NULL) AS analyst_counts,
            SUM(eps_7d_ago IS NOT NULL) AS eps_trend,SUM(revisions_up_30d IS NOT NULL OR revisions_down_30d IS NOT NULL) AS revisions
            FROM stock_analyst_consensus_eodhd_history WHERE symbol IN :symbols
            AND available_at>=:since AND available_at<:cutoff''')
        check(conn,'sec_forms','''SELECT form_type,COUNT(*) AS filings,COUNT(DISTINCT symbol) AS symbols,
            MAX(available_at) AS latest FROM sec_filing_raw WHERE symbol IN :symbols
            AND available_at>=:since AND available_at<:cutoff GROUP BY form_type ORDER BY filings DESC''')
        check(conn,'sec_documents','''SELECT d.document_type,COUNT(*) AS documents,
            COUNT(DISTINCT f.symbol) AS symbols,SUM(d.content_bytes>0) AS with_content,
            MAX(d.available_at) AS latest FROM sec_filing_documents d JOIN sec_filing_raw f
            ON f.accession_number=d.accession_number WHERE f.symbol IN :symbols
            AND d.available_at>=:since AND d.available_at<:cutoff GROUP BY d.document_type''')
        check(conn,'sec_documents_unique','''SELECT COUNT(*) AS documents,
            COUNT(DISTINCT f.symbol) AS symbols,MAX(d.available_at) AS latest
            FROM sec_filing_documents d JOIN sec_filing_raw f ON f.accession_number=d.accession_number
            WHERE f.symbol IN :symbols AND d.available_at>=:since AND d.available_at<:cutoff''')
        check(conn,'sec_events','''SELECT item_code,COUNT(*) AS n,COUNT(DISTINCT symbol) AS symbols,
            SUM(CHAR_LENGTH(event_text)>100) AS substantive_text FROM sec_corporate_events
            WHERE symbol IN :symbols AND available_at>=:since AND available_at<:cutoff GROUP BY item_code''')
        check(conn,'fundamentals_content','''SELECT source,COUNT(*) AS n,COUNT(DISTINCT symbol) AS symbols,
            MAX(fetched_at) AS last_fetch,MAX(trade_date) AS last_record_date,
            SUM(revenue IS NOT NULL) AS revenue,SUM(eps IS NOT NULL) AS eps,
            SUM(debt_to_equity IS NOT NULL) AS debt,SUM(net_margin IS NOT NULL) AS margin,
            SUM(available_date IS NOT NULL) AS availability_dated
            FROM stock_fundamentals_daily WHERE symbol IN :symbols AND fetched_at>=:since AND fetched_at<:cutoff
            GROUP BY source''')
        check(conn,'earnings_upcoming','''SELECT COUNT(*) AS events,COUNT(DISTINCT symbol) AS symbols,
            MIN(earnings_date) AS first_date,MAX(earnings_date) AS last_date,
            SUM(eps_estimate IS NOT NULL) AS eps_estimates,SUM(eps_actual IS NOT NULL) AS actuals
            FROM stock_earnings_calendar WHERE symbol IN :symbols AND earnings_date>=:today
            AND earnings_date<=:future AND last_updated<:cutoff''')
        check(conn,'macro_latest','''SELECT trade_date,mode,vix,vix9d,vxn,vix3m,move,ten_y,
            yield_10y_5d_pct,sentiment_score,created_at,updated_at FROM stock_macro_indicators_daily
            WHERE trade_date<=:today AND updated_at<:cutoff ORDER BY trade_date DESC LIMIT 3''',scoped=False)
        check(conn,'macro_public','''SELECT provider,metric_key,COUNT(*) AS n,MIN(period_end) AS first_period,
            MAX(period_end) AS latest_period,MAX(available_at) AS last_received
            FROM macro_public_observation_versions WHERE available_at<:cutoff GROUP BY provider,metric_key''',scoped=False)
        check(conn,'sentiment_recent_days','''SELECT trade_date,COUNT(*) AS symbols,SUM(news_count_1d>0) AS with_news,
            AVG(news_count_1d) AS mean_news_count,MAX(updated_at) AS last_updated
            FROM ticker_daily_sentiment_features WHERE symbol IN :symbols AND trade_date>=:since
            AND trade_date<=:today AND updated_at<:cutoff GROUP BY trade_date ORDER BY trade_date DESC LIMIT 10''')
        check(conn,'news_mapping_qualification','''SELECT COUNT(*) AS mappings,
            SUM(JSON_UNQUOTE(JSON_EXTRACT(mapping_context,'$.identity_qualified'))='true') AS identity_true,
            MAX(first_observed_at) AS last_observed FROM news_ticker_map_versions
            WHERE first_observed_at>=:since AND first_observed_at<:cutoff AND JSON_VALID(mapping_context)''',scoped=False)
        names=list(report['p0_p1_catalog'])+['sec_corporate_events_normalize','sec_institutional_ownership_normalize',
                                           'public_macro_snapshot_sync','oracle_options_indicative_snapshot']
        statement=text('''SELECT /*+ MAX_EXECUTION_TIME(15000) */ r.batch_name,r.status,r.started_at,r.finished_at,
            r.requested_count,r.received_count,r.persisted_count,r.failed_count FROM pit_collection_runs r
            JOIN (SELECT batch_name,MAX(id) AS id FROM pit_collection_runs WHERE batch_name IN :names
            AND started_at<:cutoff GROUP BY batch_name) x ON r.id=x.id ORDER BY r.batch_name''').bindparams(bindparam('names',expanding=True))
        report['latest_runs']=[dict(r) for r in conn.execute(statement,dict(names=names,cutoff=params['cutoff'])).mappings()]
        latest=query(conn,'''SELECT run_id,trade_date,status,protocol_version,config_json,input_json
            FROM llm_directional_runs WHERE started_at<:cutoff ORDER BY started_at DESC LIMIT 1''',params)
        if latest:
            row=latest[0];cfg=json.loads(row.pop('config_json'));ctx=json.loads(row.pop('input_json'))
            row['provider']=cfg.get('provider','openai');row['analysis_mode']=cfg.get('analysis_mode','web_search')
            row['candidates']=[dict(symbol=c['symbol'],keys=sorted(c),
                local_kinds=[s.get('kind') for s in c.get('local_evidence',[])]) for c in ctx.get('candidates',[])]
            report['latest_llm']=row
            top_symbols=[c['symbol'] for c in ctx.get('candidates',[])][:10]
            if top_symbols:
                top_sql='''SELECT s.symbol,
                    (SELECT COUNT(*) FROM sec_filing_raw f WHERE f.symbol=s.symbol AND f.available_at>=:since AND f.available_at<:cutoff) AS sec_filings,
                    (SELECT MIN(earnings_date) FROM stock_earnings_calendar e WHERE e.symbol=s.symbol AND e.earnings_date>=:today AND e.last_updated<:cutoff) AS next_earnings,
                    (SELECT MAX(snapshot_date) FROM stock_analyst_consensus_eodhd_history e WHERE e.symbol=s.symbol AND e.available_at<:cutoff) AS consensus_snapshot,
                    (SELECT MAX(fetched_at) FROM stock_fundamentals_daily f WHERE f.symbol=s.symbol AND f.source='SEC_EDGAR' AND f.fetched_at<:cutoff) AS fundamentals_sec_fetched,
                    (SELECT MAX(trade_date) FROM ticker_daily_sentiment_features t WHERE t.symbol=s.symbol AND t.updated_at<:cutoff) AS last_sentiment_day
                    FROM stock_metadata s WHERE s.symbol IN :symbols ORDER BY s.symbol'''
                report['latest_top10_inventory']=query(conn,top_sql,params,symbols=top_symbols)
        conn.rollback()
    engine.dispose()
    (output/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(output=str(output),coverage={t:v.get('recent') for t,v in report['tables'].items()},
        checks=report['checks'],errors=report['errors']),ensure_ascii=False,default=str),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True)
    args=parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    run(args.output_dir)
