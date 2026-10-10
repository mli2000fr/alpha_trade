"""Explicit six-table Yahoo consensus purge with a targeted pre-delete archive."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import bindparam, text

from database.connection import get_sqlalchemy_engine

TABLES = (
    'stock_analyst_estimate_history',
    'stock_analyst_eps_trend_history',
    'stock_analyst_eps_revision_history',
    'stock_analyst_target_history',
    'stock_analyst_recommendation_history',
    'analyst_snapshot_collection_run',
)


def run(write=False):
    config=yaml.safe_load(Path('batch.yaml').read_text(encoding='utf-8-sig'))
    if config.get('analyst_snapshot_collection',{}).get('enabled'):
        raise RuntimeError('Yahoo collector must be disabled before purge')
    engine=get_sqlalchemy_engine()
    root=Path('backups/db/yahoo_consensus_before_clear')/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    report={'status':'PREVIEW','sql_database':'alpha_trade','tables':{},'backup_directory':str(root)}
    with engine.connect() as conn:
        if conn.execute(text('SELECT DATABASE()')).scalar()!='alpha_trade':
            raise RuntimeError('Refuse purge outside alpha_trade US database')
        names=tuple(TABLES)
        constraints=conn.execute(text('''SELECT TABLE_NAME,REFERENCED_TABLE_NAME
            FROM information_schema.KEY_COLUMN_USAGE
            WHERE TABLE_SCHEMA='alpha_trade' AND REFERENCED_TABLE_SCHEMA='alpha_trade'
            AND REFERENCED_TABLE_NAME IN :tables''').bindparams(bindparam('tables',expanding=True)),{'tables':names}).mappings().all()
        if any(row['TABLE_NAME'] not in TABLES for row in constraints):
            raise RuntimeError('External foreign-key dependency: refuse collateral deletion')
        # Child histories precede run table. Refuse any other graph rather than disabling FK checks.
        if any(row['REFERENCED_TABLE_NAME']!='analyst_snapshot_collection_run' for row in constraints):
            raise RuntimeError('Unexpected FK order: manual scoped review required')
        for table in TABLES:
            metadata=conn.execute(text('''SELECT ENGINE FROM information_schema.TABLES
                WHERE TABLE_SCHEMA='alpha_trade' AND TABLE_NAME=:table'''),{'table':table}).scalar()
            if metadata!='InnoDB':
                raise RuntimeError('Transactional InnoDB table required: '+table)
            count=conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{table}`')).scalar_one()
            report['tables'][table]={'before':count}
        conn.rollback()
        print(json.dumps(report),flush=True)
        if not write:return report
        root.mkdir(parents=True,exist_ok=False)
        with conn.begin():
            # A repeatable snapshot, row-count guards and disabled collector bound concurrency.
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
            for table in TABLES:
                info=report['tables'][table]
                info['before']=conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{table}`')).scalar_one()
                info['ddl']=conn.execute(text(f'SHOW CREATE TABLE alpha_trade.`{table}`')).first()[1]
                path=root/(table+'.jsonl.gz')
                read=0;last_id=0
                with gzip.open(path,'wt',encoding='utf-8') as stream:
                    while True:
                        rows=conn.execute(text(f'SELECT * FROM alpha_trade.`{table}` WHERE id>:id ORDER BY id LIMIT 2000'),{'id':last_id}).mappings().all()
                        if not rows:break
                        for row in rows:
                            stream.write(json.dumps(dict(row),default=str,separators=(',',':'))+'\n')
                        read+=len(rows);last_id=rows[-1]['id']
                if read!=info['before']:raise RuntimeError('Backup count mismatch: '+table)
                hasher=hashlib.sha256()
                with path.open('rb') as stream:
                    for block in iter(lambda:stream.read(1024*1024),b''):hasher.update(block)
                info.update({'backup_rows':read,'backup_file':path.name,'sha256':hasher.hexdigest()})
                print(json.dumps({'stage':'BACKED_UP','table':table,'rows':read}),flush=True)
            report['status']='BACKUP_COMPLETE_BEFORE_DELETE'
            (root/'manifest.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
            for table in TABLES:
                deleted=conn.execute(text(f'DELETE FROM alpha_trade.`{table}`')).rowcount
                if deleted!=report['tables'][table]['before']:
                    raise RuntimeError('Concurrent changes detected: rollback all deletes')
                after=conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{table}`')).scalar_one()
                if after:raise RuntimeError('Table not empty: rollback all deletes')
                report['tables'][table].update({'deleted':deleted,'after':after})
                print(json.dumps({'stage':'DELETED_IN_TRANSACTION','table':table,'rows':deleted}),flush=True)
        # Confirm empty using a fresh transaction after commit.
        for table in TABLES:
            after=conn.execute(text(f'SELECT COUNT(*) FROM alpha_trade.`{table}`')).scalar_one()
            report['tables'][table]['after_commit']=after
            if after:raise RuntimeError('Unexpected rows after commit: '+table)
        conn.rollback()
    engine.dispose()
    report['status']='COMMITTED_ALL_SIX_TABLES_EMPTY'
    report['total_deleted']=sum(info['deleted'] for info in report['tables'].values())
    (root/'manifest.json').write_text(json.dumps(report,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='tables'}),flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write',action='store_true')
    run(parser.parse_args().write)
