"""Versioned serialization-only repair; resume cents queue without stopping workers.

Sealed predecessors stay unchanged. Only two absent provenance fields in TOP-N
descriptive rows may map NaN -> null. Financial NaN/inf still fails strict JSON.
"""
from contextlib import contextmanager
from datetime import datetime,timezone
import argparse
import json
import math
import numbers
import os
from pathlib import Path

ROOT=Path('artifacts/operations/winner-consolidation-resume-20261026-v1')
DOC=Path('doc/ml/winner_consolidation_reprise_20261026.md')
TEST=Path('tests/test_us_winner_consolidation_resume_20261026.py')
OPTIONAL={'fill_price_correction','correction_amendment_sha256'}
LEGACY='scripts.research.us_winner_legacy_resume_20261024'
TARGET='scripts.research.us_winner_cent_qualification_20261024'


def clean_descriptive_report(payload):
    """Never invent financial zeroes or normalize a non-finite metric."""
    result=dict(payload);result['best_2017_descriptive_only']=[];changed=[]
    for i,row in enumerate(payload['best_2017_descriptive_only']):
        normalized=dict(row)
        for key in OPTIONAL:
            value=normalized.get(key)
            if isinstance(value,numbers.Real) and math.isnan(value):
                normalized[key]=None;changed.append(f'best_2017_descriptive_only[{i}].{key}')
        result['best_2017_descriptive_only'].append(normalized)
    json.dumps(result,allow_nan=False)
    return result,changed


def command_job(command):
    """Adopt only the exact legacy cents-resume command, not an arbitrary PID."""
    def value(flag):return command[command.index(flag)+1]
    try:
        if value('-m')!=LEGACY or value('--target')!=TARGET or value('--phase')!='resume':
            raise ValueError('Not a qualified legacy resume worker')
        kind,year=value('--kind'),int(value('--year'))
    except (IndexError,ValueError) as exc:raise ValueError('Unexpected adopted command') from exc
    if kind not in ('1x','2x','top20','top50') or not 2017<=year<=2026:
        raise ValueError('Unexpected adopted job')
    return f'{kind}-{year}'


def choose_job(jobs,active,adopted,*,available_bytes):
    if len(active)>=2 or len(active)+len(adopted)>=3 or available_bytes<6*2**30:return None
    candidates=[j for j in jobs if j['name'] not in active and j['name'] not in adopted
                and not j['blocked'] and not j['resolved']]
    candidates.sort(key=lambda j:(not j['qualified'],j['name']))
    if not candidates:return None
    item=candidates[0];return item['name'],'resume' if item['qualified'] else 'qualify'


@contextmanager
def serialization_scope(base,top_root,changes):
    original=base.save_new
    def saved(path,payload):
        if Path(path).resolve()==(Path(top_root)/'report.json').resolve():
            payload,normalized=clean_descriptive_report(payload)
            changes.extend(normalized)
        return original(path,payload)
    base.save_new=saved
    try:yield
    finally:base.save_new=original


def initialize():
    # Must precede imports of any simulator consumer.
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy();legacy.prepare();legacy.install_dispatch()
    from scripts.research import us_winner_cent_qualification_20261024 as cent
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('HTTP forbidden in consolidation/recovery'))
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    cent.seal();base=cent.grid.base
    sources={str(p):base.digest(p) for p in [Path(__file__),DOC,TEST,
        Path(cent.__file__),Path('scripts/research/us_winner_topn_2017_comparison_20261023.py'),
        Path('scripts/research/us_winner_top50_priority_20261025.py')]}
    sources.update({str(p):base.digest(p) for p in [cent.ROOT/'protocol.json',*(r/'protocol.json' for r in cent.RUNS.values())]})
    ROOT.mkdir(parents=True,exist_ok=True)
    path=ROOT/'protocol.json'
    if path.exists():
        old=base.read(path);base.verify(old['sources'])
        if old['sources']!=sources:raise ValueError('Amendment source drift')
    else:base.save_new(path,dict(created_at_utc=cent.now(),sources=sources,
        optional_metadata_nan_to_null=sorted(OPTIONAL),financial_nan_rejected=True,
        economic_rules_changed=False,sealed_sources_changed=False,active_workers_stopped=False,
        new_cents_workers_maximum=2,total_cents_workers_including_adopted_maximum=3,
        SQL_reads=0,SQL_writes=0,provider_calls=0,training=False,orders=False))
    return cent


def repair_top50(cent):
    from scripts.research import us_winner_top50_priority_20261025 as refresh
    base=cent.grid.base;root=cent.RUNS['top50'];receipt=ROOT/'consolidation.json'
    if receipt.exists():
        old=base.read(receipt);base.verify(old['preserved']);base.verify(old['outputs']);return old
    preserved={}
    for file in sorted((root/'cases').glob('*/report.json')):
        r=base.read(file);preserved[str(file)]=base.digest(file)
        preserved.update({str(file.parent/n):sha for n,sha in r['files'].items()})
    if len(list((root/'cases').glob('*/report.json')))!=300:raise ValueError('TOP50 incomplete')
    base.verify(preserved)
    csv=root/'comparison-vs-top10.csv';old_csv=base.digest(csv) if csv.exists() else None
    changes=[]
    with serialization_scope(base,root,changes):
        if not cent.finalize('top50'):raise ValueError('TOP50 finalization did not succeed')
    base.verify(preserved)
    if old_csv is not None and base.digest(csv)!=old_csv:raise ValueError('Derived financial CSV changed')
    report=base.read(root/'report.json');base.verify({str(root/n):h for n,h in report['files'].items()})
    if report['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Unfinished aggregate')
    json.dumps(report,allow_nan=False)
    # Execution progress only; no old protocol/source or case rewritten.
    refresh.refresh_top_parent(cent,cent.now)
    result=dict(status='PASS_METADATA_ONLY_CONSOLIDATION',completed_accounts=300,
        preserved=preserved,outputs={str(root/'report.json'):base.digest(root/'report.json'),str(csv):base.digest(csv)},
        normalized_fields=changes,previous_csv_sha256=old_csv,financial_csv_byte_identical=old_csv==base.digest(csv),
        no_account_rerun=True,completed_at_utc=cent.now())
    base.save_new(receipt,result);return result


def adopted_from_snapshot(cent,snapshot):
    import psutil
    adopted={}
    for name,item in snapshot.get('active',{}).items():
        folder=cent.ROOT/name
        if (folder/'resolution.json').exists():continue
        process=psutil.Process(item['pid'])  # Fail closed if an unresolved owner vanished.
        if not process.is_running() or process.status()==psutil.STATUS_ZOMBIE:raise ValueError('Dead unresolved owner')
        command=process.cmdline()
        if command_job(command)!=name:raise ValueError('Adopted identity mismatch')
        adopted[name]=dict(pid=process.pid,created=process.create_time(),command=command)
    return adopted


def living_adopted(cent,adopted,process_factory):
    import psutil
    living={}
    for name,item in adopted.items():
        if (cent.ROOT/name/'resolution.json').exists():continue
        try:
            process=process_factory(item['pid'])
            if (process.create_time()!=item['created'] or not process.is_running()
                    or process.status()==psutil.STATUS_ZOMBIE):raise ValueError('Adopted worker identity/liveness changed')
        except psutil.NoSuchProcess as exc:raise RuntimeError('Adopted worker exited without resolution: '+name) from exc
        living[name]=item
    return living


def supervise(cent):
    import psutil
    base=cent.grid.base
    # Capture old owners BEFORE original supervisor rewrites its own progress.
    old_snapshot=cent.read_json(cent.ROOT/'progress.json')
    adopted=adopted_from_snapshot(cent,old_snapshot)
    if (ROOT/'handoff.json').exists():raise ValueError('Already started; inspect before another supervisor')
    base.save_new(ROOT/'handoff.json',dict(created_at_utc=cent.now(),adopted=adopted,
        old_progress=old_snapshot,pid=os.getpid(),no_termination=True))
    original_next=cent.next_task
    def next_task(active):
        living=living_adopted(cent,adopted,psutil.Process)
        folders={p.name:p for p in sorted(cent.ROOT.glob('*-20*')) if (p/'request.json').exists()}
        jobs=[dict(name=n,qualified=(p/'qualified.json').exists(),blocked=(p/'blocked.json').exists(),
                   resolved=(p/'resolution.json').exists()) for n,p in folders.items()]
        memory=psutil.virtual_memory().available
        choice=choose_job(jobs,active,living,available_bytes=memory)
        cent.grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',adopted_active=living,
            active_new_jobs=list(active),next_job=choice,available_memory_bytes=memory,updated_at_utc=cent.now()))
        if choice is None:return None
        name,phase=choice;folder=folders[name]
        return folder,phase,cent.read_json(folder/'request.json')
    changes=[];cent.next_task=next_task
    try:
        with serialization_scope(base,cent.RUNS['top50'],changes):cent.supervise()
    finally:cent.next_task=original_next
    cent.grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED',updated_at_utc=cent.now()))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['consolidate','supervise'],default='supervise');args=parser.parse_args()
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    cent=initialize()
    # A task-owned OS lock prevents concurrent instances; cents annual/root locks
    # are still acquired by their original validated launcher and workers.
    try:
        with cent.grid.run_lock(ROOT):
            repair_top50(cent)
            if args.phase=='supervise':supervise(cent)
            else:print('PASS_TOP50_CONSOLIDATION_300_PRESERVED_ACCOUNTS')
    except BaseException as exc:
        cent.grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,
            error=str(exc),updated_at_utc=cent.now()))
        raise


if __name__=='__main__':main()
