"""Bounded economic-link readiness audit: existing SQL/local archives only.

No HTTP client, LLM, model fitting, future outcomes, broker, or production DML.
The output is candidate source passages, not verified links or trade signals.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import pandas as pd
from sqlalchemy import bindparam,event,text

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_economic_links_feasibility/20261102-v1')
COHORT=Path('artifacts/options_directional/opt-1593e7178d7d4cc3bd74a6792cc0eab5/report.json')
HISTORY=Path('artifacts/research/us_news_embeddings/20261102-v1/population.parquet')
UNIVERSE=Path('config/univers_batch/univers_filtred_tradable.txt')
CIKS=Path('artifacts/sec_cache/company_tickers.json')
FORMS=['10-K','10-K/A','10-Q','10-Q/A','20-F','20-F/A','40-F','40-F/A','8-K','8-K/A','6-K','6-K/A']
MAX_DOCS=60
MAX_BYTES=15_000_000


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def readonly(_conn,_cursor,statement,_parameters,_context,_many):
    sql=statement.strip()
    if ';' in sql or re.search(r'(?i)\b(INTO\s+(OUTFILE|DUMPFILE)|GET_LOCK|RELEASE_LOCK)\b',sql):
        raise ValueError('Research reader refuses side-effecting SELECT or stacked SQL')
    if not re.match(r'(?i)^(SELECT|SHOW)\b',sql) and sql not in (
        'SET TRANSACTION READ ONLY',"SET SESSION time_zone='+00:00'",
        'SET SESSION MAX_EXECUTION_TIME=20000'):
        raise ValueError('Research reader refuses non-read-only SQL')


def inventory(root):
    from database.connection import get_sqlalchemy_engine
    if root.exists():
        raise ValueError('Fresh immutable audit directory required')
    root.mkdir(parents=True)
    source=read(COHORT)
    rows=source['rows']
    if source['status']!='COMPLETED' or len(rows)!=20 or sorted(r['oracle_rank'] for r in rows)!=list(range(1,21)):
        raise ValueError('Exactly the original complete TOP20 required')
    current=pd.DataFrame([{k:r[k] for k in ['symbol','oracle_rank','oracle_score']} for r in rows])
    current.to_parquet(root/'current-top20.parquet',index=False)
    history=pd.read_parquet(HISTORY,columns=['date','symbol','oracle_rank','score','batch_id'])
    history.to_parquet(root/'historical-top20.parquet',index=False)
    symbols=sorted(set(history.symbol)|set(current.symbol))
    universe=sorted(set(s for s in re.split(r'[\s,;]+',UNIVERSE.read_text(encoding='utf-8-sig')) if s))
    ticker_rows=read(CIKS)
    ticker_rows=list(ticker_rows.values()) if isinstance(ticker_rows,dict) else ticker_rows
    cik_map={str(r['ticker']).upper():str(r['cik_str']).zfill(10) for r in ticker_rows
             if isinstance(r,dict) and 'ticker' in r and 'cik_str' in r}
    ciks=sorted({cik_map[s] for s in symbols if s in cik_map})
    atomic_json(root/'lookup-cik-map.json',dict(mapping={s:cik_map.get(s) for s in symbols},
        warning='Current local SEC ticker cache used only for indexed retrieval, not a historical identity proof'))
    cutoff=datetime.now(timezone.utc)
    protocol=dict(status='FROZEN_BEFORE_DOCUMENT_REVIEW',cutoff_utc=cutoff.isoformat(),
        frozen_signal_cutoff_utc=source['cutoff_utc'],signal_date=source['trade_date'],
        cohort='Latest archived complete original TOP20 before options filtering; historical annual TOP20 secondary',
        batch_id=source['batch_id'],historical_candidate_days=len(history),historical_symbols=int(history.symbol.nunique()),
        current_symbols=current.symbol.tolist(),metadata_scope_symbols=len(symbols),counterparty_universe_count=len(universe),
        filings_since='2023-01-01',max_metadata_per_chunk=5000,max_primary_documents=MAX_DOCS,
        max_primary_documents_per_current_symbol=3,max_document_bytes=MAX_BYTES,
        document_choice='Per current symbol: annual first, quarterly second, other allowed filing third; newest within priority. No outcome selection.',
        review_cap=dict(candidate_owner_counterparty_pairs=20,negative_control_passages=10),
        relation_admission='Exact supplied quote + owner CIK/hash/receipt + operating relation + dated counterparty identity; no inference from co-mention',
        missing_or_truncated='Unknown, never no economic relationship',
        historical_policy='SQL local receipt after historical cutoff is not backdated to SEC filing date',
        outcome_reads=False,production_sql_writes=False,http_calls=False,llm_calls=False,budget_usd=0,
        indexed_lookup='Local SEC ticker cache CIK; missing historical ticker aliases remain unknown',
        sources={str(p):digest(p) for p in [COHORT,HISTORY,UNIVERSE,CIKS,Path(__file__)]})
    atomic_json(root/'protocol.json',protocol)
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    if engine.url.database!='alpha_trade':
        raise ValueError('US alpha_trade required')
    event.listen(engine,'before_cursor_execute',readonly)
    files=[]
    try:
        with engine.connect() as conn:
            conn.execute(text('SET TRANSACTION READ ONLY'))
            conn.execute(text("SET SESSION time_zone='+00:00'"))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=20000'))
            columns=[dict(r) for r in conn.execute(text('''SELECT TABLE_NAME,COLUMN_NAME FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME IN
                ('sec_filing_raw','sec_filing_documents','security_master_snapshots','pit_collection_runs','stock_metadata')''')).mappings()]
            names={r['TABLE_NAME']:set() for r in columns}
            for r in columns:
                names[r['TABLE_NAME']].add(r['COLUMN_NAME'])
            atomic_json(root/'schema.json',{k:sorted(v) for k,v in names.items()})
            needed={'sec_filing_raw','pit_collection_runs','stock_metadata','security_master_snapshots'}
            if not needed<=set(names):
                raise ValueError('Required source tables missing')
            company_fields='symbol,company_name'+(',cik' if 'cik' in names['stock_metadata'] else '')
            query=text('SELECT '+company_fields+' FROM stock_metadata WHERE symbol IN :symbols').bindparams(bindparam('symbols',expanding=True))
            companies=[dict(r) for r in conn.execute(query,dict(symbols=universe)).mappings()]
            atomic_json(root/'company-names.json',companies)
            # Current identity bridge retained as context, not silently applied to historical dates.
            q=text('''SELECT s.symbol,s.cik,s.snapshot_date,s.available_at,s.run_id,r.status run_status,r.finished_at
                FROM security_master_snapshots s LEFT JOIN pit_collection_runs r ON r.run_id=s.run_id
                WHERE s.symbol IN :symbols AND s.snapshot_date >= '2026-09-01'
                AND s.available_at < :cutoff ORDER BY s.snapshot_date DESC,s.available_at DESC LIMIT 20001''').bindparams(bindparam('symbols',expanding=True))
            masters=[dict(r) for r in conn.execute(q,dict(symbols=current.symbol.tolist(),cutoff=cutoff.replace(tzinfo=None))).mappings()]
            if len(masters)>20000:
                raise ValueError('Master inventory truncated')
            atomic_json(root/'current-master.json',masters)
            q=text('''SELECT f.id,f.accession_number,f.cik,f.symbol,f.company_name,f.form_type,
                f.filing_date,f.acceptance_datetime,f.filing_url,f.content_sha256,
                f.observed_at,f.available_at,f.run_id,
                r.status run_status,r.finished_at collection_finished_at
                FROM sec_filing_raw f LEFT JOIN pit_collection_runs r ON r.run_id=f.run_id
                WHERE f.cik IN :ciks AND f.form_type IN :forms
                AND f.filing_date >= '2023-01-01' AND f.available_at < :cutoff
                ORDER BY f.filing_date DESC,f.accession_number LIMIT 5001''').bindparams(
                    bindparam('ciks',expanding=True),bindparam('forms',expanding=True))
            metadata=[]
            for i in range(0,len(ciks),20):
                part=[dict(r) for r in conn.execute(q,dict(ciks=ciks[i:i+20],forms=FORMS,
                    cutoff=cutoff.replace(tzinfo=None))).mappings()]
                if len(part)>5000:
                    raise ValueError('Filing metadata truncated; partition required')
                metadata.extend(part)
            atomic_json(root/'filing-metadata.json',metadata)
            def priority(row):
                form=row['form_type'].replace('/A','')
                return 0 if form in ['10-K','20-F','40-F'] else 1 if form=='10-Q' else 2
            selected=[]
            for symbol in current.symbol:
                candidates=[r for r in metadata if r['cik']==cik_map.get(symbol) and r['content_sha256']]
                candidates=sorted(candidates,key=lambda r:(priority(r),-r['filing_date'].toordinal(),r['accession_number']))
                selected.extend([dict(r,requested_symbol=symbol) for r in candidates[:3]])
            if len(selected)>MAX_DOCS:
                raise ValueError('Document cap exceeded')
            bodyfolder=root/'raw';bodyfolder.mkdir()
            for row in selected:
                found=conn.execute(text('''SELECT OCTET_LENGTH(content_text) body_bytes,
                    CASE WHEN OCTET_LENGTH(content_text)<=:max_bytes THEN content_text ELSE NULL END content_text
                    FROM sec_filing_raw WHERE id=:id'''),dict(id=row['id'],max_bytes=MAX_BYTES)).mappings().one()
                record=dict(row,body_bytes=found['body_bytes'])
                content=found['content_text']
                if content is None:
                    files.append(dict(record,archive_status='OVERSIZED_OR_NO_BODY',hash_matches=False))
                    continue
                payload=content.encode('utf-8')
                actual=hashlib.sha256(payload).hexdigest()
                record.update(actual_sha256=actual,hash_matches=actual==row['content_sha256'],archive_status='COPIED')
                if len(payload)>MAX_BYTES:
                    raise ValueError('Body grew beyond frozen cap during snapshot')
                path=bodyfolder/(row['accession_number']+'.txt')
                if not path.exists():
                    with path.open('xb') as stream:
                        stream.write(payload)
                record['archive_path']=str(path.relative_to(root))
                files.append(record)
            atomic_json(root/'document-inventory.json',files)
        report=dict(status='INVENTORY_COMPLETE_NO_SIGNAL',signal_date=source['trade_date'],current_symbols=20,
            historical_symbols=int(history.symbol.nunique()),historical_candidate_days=len(history),
            metadata_filings=len(metadata),forms=dict(Counter(r['form_type'] for r in metadata)),
            metadata_with_content_hash=sum(bool(r['content_sha256']) for r in metadata),
            metadata_symbols_with_content_hash=len({r['symbol'] for r in metadata if r['content_sha256']}),
            selected_documents=len(files),selected_current_symbols=len({r['symbol'] for r in files}),
            hash_verified_documents=sum(r['hash_matches'] for r in files),
            indexed_ciks=len(ciks),symbols_without_current_cik_lookup=[s for s in symbols if s not in cik_map],
            oversized_selected_filings=sum(bool(r['body_bytes'] and r['body_bytes']>MAX_BYTES) for r in files),
            oldest_filing_date=min((str(r['filing_date']) for r in metadata),default=None),
            earliest_local_receipt=min((str(r['observed_at']) for r in metadata),default=None),
            llm_calls=0,http_calls=0,production_sql_writes=False,outcome_reads=False)
        atomic_json(root/'inventory-report.json',report)
        atomic_json(root/'progress.json',report)
        return report
    except Exception as exc:
        atomic_json(root/'progress.json',dict(status='STOPPED_INVENTORY',error_type=type(exc).__name__,
            raw_documents_already_archived=len(files),production_sql_writes=False,llm_calls=0))
        raise
    finally:
        event.remove(engine,'before_cursor_execute',readonly)
        engine.dispose()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT)
    args=parser.parse_args()
    print(json.dumps(inventory(args.output),default=str))


if __name__=='__main__':
    main()
