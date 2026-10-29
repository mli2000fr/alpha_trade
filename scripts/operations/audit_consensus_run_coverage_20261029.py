"""READ ONLY recent consensus coverage; counts symbols, not fiscal-period rows."""
from datetime import datetime,timezone
from collections import defaultdict
import json
from pathlib import Path
import re
from statistics import mean
from zoneinfo import ZoneInfo

from sqlalchemy import event,text
from common.config_loader import load_batch_config
from database.connection import get_sqlalchemy_engine


def main():
    cfg=load_batch_config()['eodhd_consensus_snapshot']
    count=lambda path:len({s.upper() for s in re.split(r'[,;\s]+',Path(path).read_text(encoding='utf-8-sig')) if s})
    universe=count(cfg['symbols_file']);reference=count(cfg['coverage_symbols_file'])
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    def readonly(conn,cursor,statement,parameters,context,many):
        if statement.lstrip().split()[0].upper() not in ('SELECT','SHOW','SET','DESCRIBE'):
            raise ValueError('Read-only audit')
    event.listen(engine,'before_cursor_execute',readonly)
    fields=['overall_coverage','coverage','reference_requested','reference_covered','skipped_symbols',
            'api_calls','no_consensus_count','invalid_symbol_count','unprocessed_symbols','received_rows']
    selections=','.join("JSON_UNQUOTE(JSON_EXTRACT(details_json,'$."+f+"')) AS "+f for f in fields)
    with engine.connect() as conn:
        rows=[dict(r) for r in conn.execute(text('SELECT run_id,status,started_at,finished_at,requested_count,'
            'received_count,persisted_count,empty_count,failed_count,'+selections+
            " FROM pit_collection_runs WHERE batch_name='eodhd_consensus_snapshot' ORDER BY started_at DESC LIMIT 35")).mappings()]
    for r in rows:
        r['snapshot_day_ny']=r['started_at'].replace(tzinfo=timezone.utc).astimezone(ZoneInfo('America/New_York')).date().isoformat()
        for key in fields:
            value=r.get(key)
            if value is not None:
                try:r[key]=float(value) if key in ('overall_coverage','coverage') else int(value)
                except (ValueError,TypeError):r[key]=None
        covered=r.get('received_count',0)+(r.get('skipped_symbols') or 0)
        r['calculated_overall_coverage']=covered/r['requested_count'] if r['requested_count'] else None
    byday={}
    for r in rows:
        if r['status'] in ('COMPLETED','COMPLETED_WITH_WARNINGS') and r['requested_count']==universe:
            byday.setdefault(r['snapshot_day_ny'],r)
    sample=list(byday.values())[:7]
    if not sample:raise ValueError('No complete runs on current file universe')
    summary=dict(collected_universe=universe,collected_file=cfg['symbols_file'],reference_universe=reference,
        reference_file=cfg['coverage_symbols_file'],dates=[r['snapshot_day_ny'] for r in sample],sample_days=len(sample),
        mean_overall_coverage=mean(r['overall_coverage'] if r['overall_coverage'] is not None else r['calculated_overall_coverage'] for r in sample),
        mean_reference_coverage=mean(r['coverage'] for r in sample if r['coverage'] is not None),
        mean_covered_symbols=mean(r['received_count']+(r['skipped_symbols'] or 0) for r in sample),
        mean_reference_covered=mean(r['reference_covered'] for r in sample if r['reference_covered'] is not None),
        mean_api_calls=mean(r['api_calls'] for r in sample if r['api_calls'] is not None))
    output=Path('artifacts/operations/consensus_coverage_audit')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output.mkdir(parents=True,exist_ok=False)
    (output/'report.json').write_text(json.dumps(dict(read_only=True,summary=summary,selected_runs=sample,all_recent_runs=rows),
        indent=2,default=str),encoding='utf-8')
    print(json.dumps(dict(summary=summary,selected_runs=sample,latest_run=rows[0],report=str((output/'report.json').resolve())),default=str),flush=True)
    engine.dispose()


if __name__=='__main__':main()
