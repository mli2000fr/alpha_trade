"""Resume stopped Winner studies with their EXACT archived legacy core.

Only two engine modules changed since stop. Load their previously sealed copies
in this process and its research children; never restore/modify production files.
Source verification resolves those two original names to effective loaded bytes,
not to the newer DD engine. Every other source/input hash is checked normally.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib
import importlib.util
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path('F:/projets').resolve()
BACKUP=ROOT/'artifacts/research/us_winner_monthly_selector/20261024-dd15-full-v2/predecessor'
RECEIPTS=ROOT/'artifacts/operations/winner-legacy-resume-20261024-v1'
MODULE= 'scripts.research.us_winner_legacy_resume_20261024'
CORES={'backtesting.simulator':ROOT/'backtesting/simulator.py',
       'backtesting.winner_intraday':ROOT/'backtesting/winner_intraday.py'}
TARGETS={
    'grid':'scripts.research.us_winner_grid_supervisor_repair_20261023',
    'cent':'scripts.research.us_winner_cent_qualification_20261024',
    'top':'scripts.research.us_winner_topn_2017_comparison_20261023',
    'monthly':'scripts.research.us_winner_monthly_scope_repair_20261024',
}


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def legacy_paths():
    receipt=read(BACKUP/'receipt.json')
    if not receipt['original_sources_verified']:raise ValueError('Unverified legacy archive')
    result={}
    for module,current in CORES.items():
        rel=current.relative_to(ROOT);archived=BACKUP/'sources'/rel
        expected=receipt['source_backups'][str(rel)]
        if digest(archived)!=expected:raise ValueError('Archived core changed: '+str(archived))
        result[module]=(current,archived,expected)
    return result


def effective_source(name,paths):
    resolved=Path(name).resolve()
    return next((old for current,old,_ in paths.values() if resolved==current),Path(name))


def install_legacy():
    paths=legacy_paths()
    for module,(_,archived,_) in paths.items():
        if module in sys.modules:raise ValueError('Legacy isolation requires a fresh Python process')
        parent,leaf=module.rsplit('.',1);package=importlib.import_module(parent)
        spec=importlib.util.spec_from_file_location(module,archived)
        loaded=importlib.util.module_from_spec(spec);sys.modules[module]=loaded
        spec.loader.exec_module(loaded);setattr(package,leaf,loaded)
    from scripts.research import us_winner_bottom_rank_filter_20261022 as base
    def verify(items):
        for name,sha in items.items():
            effective=effective_source(name,paths)
            if digest(effective)!=sha:
                raise ValueError('Immutable effective legacy source/input changed: '+str(name))
    base.verify=verify
    return paths


def child_command(command):
    if not isinstance(command,(list,tuple)) or '-m' not in command:return command
    i=command.index('-m');target=command[i+1]
    if not target.startswith('scripts.research.'):return command
    if target not in TARGETS.values():raise ValueError('Unexpected legacy research child '+target)
    return [*command[:i],'-m',MODULE,'--target',target,*command[i+2:]]


def install_dispatch():
    original=subprocess.Popen
    def popen(command,*args,**kwargs):
        return original(child_command(command),*args,**kwargs)
    subprocess.Popen=popen
    # Avoid two processes replaying the same qualified year. The cents companion
    # owns those annual locks until its resolution receipt exists.
    from scripts.research import us_winner_grid_supervisor_repair_20261023 as supervisor
    from scripts.research import us_winner_cent_qualification_20261024 as cent
    old_next=supervisor.next_ready
    def next_ready(pending,completed,active,ready,profiles_per_year):
        kind=CURRENT_KIND
        deferred={y for y in pending if (cent.ROOT/f'{kind}-{y}'/'request.json').exists()
            and not (cent.ROOT/f'{kind}-{y}'/'resolution.json').exists()}
        return old_next([y for y in pending if y not in deferred],completed,active,ready,profiles_per_year)
    supervisor.next_ready=next_ready
    old_task=cent.next_task
    cent.next_task=lambda active:None if len(active)>=1 else old_task(active)


CURRENT_KIND=None


def prepare():
    from scripts.research import us_winner_grid_supervisor_repair_20261023 as supervisor
    from scripts.research import us_winner_cent_qualification_20261024 as cent
    from scripts.research import us_winner_topn_2017_comparison_20261023 as top
    from scripts.research import us_winner_monthly_scope_repair_20261024 as monthly
    from backtesting.winner_campaign_replay import atomic_json
    from datetime import datetime,timezone
    paths=legacy_paths();RECEIPTS.mkdir(parents=True,exist_ok=True)
    marker=RECEIPTS/'amendment.json'
    sources={str(p):digest(p) for p in [Path(__file__),ROOT/'doc/ml/winner_legacy_resume_20261024.md',
        ROOT/'tests/test_us_winner_legacy_resume_20261024.py',BACKUP/'receipt.json']}
    if marker.exists():
        old=read(marker)
        for p,sha in old['sources'].items():
            if digest(p)!=sha:raise ValueError('Legacy resume amendment changed')
        return old
    roots={'1x':supervisor.grid.ROOT,'2x':supervisor.lever.ROOT,
        'top':top.ROOT,'monthly':monthly.study.ROOT,'cent':cent.ROOT}
    inventory={};backups={}
    for kind,root in roots.items():
        p=read(root/'protocol.json')
        supervisor.grid.base.verify(p['sources'])
        if kind in ('1x','2x'):
            reports,_=supervisor.completed_records(root,p,verify_files=False)
        else:
            reports={str(f.relative_to(root)):digest(f) for f in root.glob('**/report.json')}
        inventory[kind]=dict(root=str(root),protocol_sha256=digest(root/'protocol.json'),completed_reports=reports)
        # Existing orchestration logs may be rewritten by its original launcher;
        # preserve exact evidence before allowing that normal restart behavior.
        candidates=[root/'progress.json']
        if kind in ('1x','2x'):candidates+=list((root/'supervisor-v2').glob('year-*-attempt-*'))
        for p in candidates:
            if p.is_file():
                target=RECEIPTS/'before-restart'/kind/p.relative_to(root)
                target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
                backups[str(target)]=digest(target)
    receipt=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        loaded_core={m:dict(current_name=str(cur),effective_archived_file=str(old),sha256=sha)
            for m,(cur,old,sha) in paths.items()},
        inventory=inventory,preserved_before_restart=backups,legacy_economic_rules_unchanged=True,
        new_DD_rules_applied=False,production_files_restored_or_edited=False,
        SQL_writes=False,provider_calls=0,orders=False,maximum_legacy_replay_workers=5,
        process_limits='One worker per grid, one cents worker, TOP50 and original monthly; later jobs queued')
    atomic_json(marker,receipt);return receipt


def probe():
    from dataclasses import asdict
    from tests.test_winner_intraday import fixture
    from backtesting.simulator import BacktestEngine
    cfg,args,_=fixture()
    result=BacktestEngine(cfg).run(**args)
    if 'winner_hard_drawdown_pct' in asdict(cfg):raise ValueError('New DD configuration leaked into legacy core')
    if 'global_liquidation' in result.tracker_snapshot['winner_replay']:raise ValueError('New DD engine leaked')
    print(json.dumps(dict(status='PASS_ISOLATED_LEGACY_NATIVE_REPLAY',
        final_equity=result.final_value(),core={m:str(sys.modules[m].__file__) for m in CORES})))


def main():
    global CURRENT_KIND
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase',choices=['prepare','probe'],default=None)
    p.add_argument('--target',choices=list(TARGETS.values()))
    if '--target' in sys.argv:
        index=sys.argv.index('--target')
        args=p.parse_args(sys.argv[1:index+2]);rest=sys.argv[index+2:]
    else:
        args=p.parse_args();rest=[]
    os.environ['SSLKEYLOGFILE']=''
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    install_legacy()
    import requests
    def forbidden(*_a,**_k):raise RuntimeError('No provider/broker/LLM HTTP in legacy resume')
    requests.Session.request=forbidden
    if args.phase=='probe':probe();return
    prepare()
    if args.phase=='prepare':return
    if args.target is None:raise ValueError('Explicit legacy target required')
    if '--kind' in rest:CURRENT_KIND=rest[rest.index('--kind')+1]
    install_dispatch();logging.basicConfig(level=logging.WARNING,force=True)
    module=importlib.import_module(args.target)
    sys.argv=[args.target,*rest]
    if args.target==TARGETS['grid']:module.main()
    elif args.target==TARGETS['cent']:
        cp=argparse.ArgumentParser();cp.add_argument('--phase',default='supervise');cp.add_argument('--kind');cp.add_argument('--year',type=int)
        a=cp.parse_args(rest)
        module.seal()
        if a.phase=='supervise':module.supervise()
        elif a.phase in ('qualify','resume'):getattr(module,a.phase)(a.kind,a.year)
        else:raise ValueError('Unexpected cents phase')
    elif args.target==TARGETS['top']:
        tp=argparse.ArgumentParser();tp.add_argument('--phase',default='supervise');tp.add_argument('--top',type=int)
        a=tp.parse_args(rest)
        if a.phase=='supervise':module.supervise()
        elif a.phase=='year':module.run_one(a.top)
        else:raise ValueError('Unexpected TOP-N phase')
    elif args.target==TARGETS['monthly']:module.run()


if __name__=='__main__':main()
