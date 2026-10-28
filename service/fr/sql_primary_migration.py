"""One-time local-to-SQL transition. No provider request, deletion or activation."""
from datetime import UTC,datetime
import json
from pathlib import Path
import uuid

from service.fr import batch_research_store as old,collection_storage as sql
from common.config_loader import load_batch_config


def migrate():
    engine=old.engine_fr()
    repo=sql.Repository(engine)
    started=datetime.now(UTC).isoformat()
    run='fr-sql-transition-'+uuid.uuid4().hex
    report=dict(batch='fr_sql_primary_migration',status='RUNNING',started_at=started,api_calls=0,
                binary_resources=0,binary_bytes=0,inputs=[],legacy_sql=[],storage_backend='sql')
    cfg=load_batch_config('batch_fr.yaml')
    try:
        repo.check_schema()
        # Do not migrate while another collector is still writing old archives.
        for lock in old.OPS.rglob('*.lock'):
            raise RuntimeError('Verrou de collecte présent : vérifier avant migration : '+str(lock))
        with repo.lock_many(sorted(old.PROVIDERS)):
            repo.save_run(run,report)
            # Explicit historical import only. Future runners never scan files.
            for batch in old.PROVIDERS:
                item=old.publish_batch(engine,batch)
                report['legacy_sql'].append(item)
                print('SQL transition historique '+batch+' documents='+str(item.get('documents_inserted',0)),flush=True)
            with sql.use(repo):
                inputs={str(v) for section in cfg.values() if isinstance(section,dict)
                        for k,v in section.items() if k in ('identities_file','baseline_history')}
                for value in sorted(inputs):
                    path=(Path.cwd()/value).resolve()
                    if not path.is_relative_to(repo.root):
                        raise ValueError('Entrée de référence hors FR')
                    raw=path.read_bytes()  # Explicit initial import, not operational fallback.
                    repo.put(path,raw)
                    if repo.get(path)!=raw: raise ValueError('Entrée SQL différente de la source')
                    report['inputs'].append(dict(key=value,sha256=sql.sha(raw),bytes=len(raw)))
                folders=[old.OPS/'fr_options_mifir_trade_sync/objects',old.OPS/'fr_security_master_sync/archives']
                for folder in folders:
                    for path in sorted(folder.rglob('*')):
                        if not path.is_file(): continue
                        raw=path.read_bytes()
                        if folder.name=='objects' and sql.sha(raw)!=path.name:
                            raise ValueError('Objet MiFIR corrompu avant import')
                        repo.put(path,raw)
                        if repo.get(path)!=raw:
                            raise ValueError('Objet SQL différent de la source')
                        report['binary_resources']+=1
                        report['binary_bytes']+=len(raw)
                        if report['binary_resources']%25==0:
                            print('SQL transition binaires='+str(report['binary_resources']),flush=True)
            report['status']='SUCCESS'
    except Exception as exc:
        report.update(status='FAILED',error_message=str(exc))
        raise
    finally:
        report['finished_at']=datetime.now(UTC).isoformat()
        try: repo.save_run(run,report)
        finally:engine.dispose()
    return report


if __name__=='__main__':
    print(json.dumps(migrate(),ensure_ascii=True,default=str),flush=True)
