"""SELECT-only preview of V7 context using an archived Oracle selection, no LLM.

Current UTC cutoff, immutable new output directory, no historical PIT claim.
Never calls prediction, collection, Repository.create, risk or a broker.
"""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path

from sqlalchemy import event,text

from service.llm_directional.config import load_filter_config
from service.llm_directional.fresh_evidence import enrich_contexts,validate_fresh_packet
from service.llm_directional.repository import dumps,digest


def run(engine,output,*,run_id=None,config=None):
    if engine.dialect.name=='mysql' and engine.url.database!='alpha_trade':
        raise ValueError('US alpha_trade only')
    config=config or load_filter_config()
    output=Path(output)
    output.mkdir(parents=True,exist_ok=False)
    cutoff=datetime.now(timezone.utc)
    statements=[]

    def guard(conn,cursor,statement,parameters,context,many):
        if not statement.lstrip().upper().startswith(('SELECT','SHOW','DESCRIBE','PRAGMA')):
            raise ValueError('Preview requires read-only queries')
        statements.append(statement.split(None,1)[0].upper())

    event.listen(engine,'before_cursor_execute',guard)
    try:
        with engine.connect() as conn:
            sql='''SELECT run_id,trade_date,batch_id,input_json FROM llm_directional_runs
                WHERE status='COMPLETED' '''
            sql+='AND run_id=:run_id ' if run_id else ''
            sql+='ORDER BY completed_at DESC,started_at DESC LIMIT 1'
            archived=conn.execute(text(sql),dict(run_id=run_id)).mappings().first()
        if archived is None:
            raise ValueError('No completed archived selection')
        snapshot=json.loads(archived['input_json'])
        candidates=sorted(snapshot['candidates'],key=lambda c:c['oracle_rank'])[:config.oracle_top_n]
        report=dict(cutoff_utc=cutoff.isoformat(),sql_mode='SELECT_ONLY',
            scope='ARCHIVED_SELECTION_CURRENT_DATA_PREVIEW_NOT_HISTORICAL_PIT',
            archived_run_id=archived['run_id'],trade_date=str(archived['trade_date']),batch_id=archived['batch_id'],
            candidate_count=len(candidates),configuration=config.snapshot(),candidates=[])
        for original in candidates:
            symbol=original['symbol']
            try:
                # Rebuild only from issuer/Oracle identity, never reuse an archived evidence packet.
                base={k:original[k] for k in ('symbol','trade_date','oracle_rank','oracle_score',
                    'issuer_reference','horizon_sessions')}
                packet=enrich_contexts(engine,[base],config,cutoff)[0]
                validate_fresh_packet(packet,config,cutoff)
                source_counts=dict(Counter(s['kind'] for s in packet['local_evidence']))
                eligible=sum(s.get('eligible_for_direction') is True for s in packet['local_evidence'])
                report['candidates'].append(dict(symbol=symbol,status='PREVIEW_BUILT',
                    sources_by_kind=source_counts,direction_eligible_sources=eligible,
                    local_data_status=packet['local_data_status'],exclusions=packet['evidence_exclusions'],
                    context_bytes=len(dumps(packet).encode('utf-8')),context_sha256=digest(packet)))
                (output/f'{symbol}.json').write_text(dumps(packet),encoding='utf-8')
                print(f'{symbol}: {source_counts}, eligible factual sources={eligible}',flush=True)
            except Exception as exc:
                # SQL exception representations can contain credentials/parameters: never echo them.
                message=str(exc)[:250] if isinstance(exc,ValueError) else type(exc).__name__
                report['candidates'].append(dict(symbol=symbol,status='BLOCKED',error=message))
                print(f'{symbol}: BLOCKED {message}',flush=True)
        report['sql_statement_count']=len(statements)
        report['preview_built']=sum(c['status']=='PREVIEW_BUILT' for c in report['candidates'])
        report['blocked']=len(candidates)-report['preview_built']
        (output/'report.json').write_text(dumps(report),encoding='utf-8')
        return report
    finally:
        event.remove(engine,'before_cursor_execute',guard)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True)
    parser.add_argument('--run-id')
    args=parser.parse_args()
    from database.connection import get_sqlalchemy_engine
    result=run(get_sqlalchemy_engine(),args.output,run_id=args.run_id)
    print(dumps({k:result[k] for k in ('archived_run_id','preview_built','blocked','sql_statement_count')}))


if __name__=='__main__':
    main()
