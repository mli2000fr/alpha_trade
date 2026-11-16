"""Resume the completed training campaign at market preparation, without refits."""
from datetime import datetime,timezone
from pathlib import Path
import argparse
import json

from scripts.research.us_q051_feature_groups_20261116 import ROOT,GROUPS,read,launch_tasks
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def verify_and_reseal():
    from scripts.research import us_q051_feature_groups_replay_20261116 as replay
    changed=Path(replay.__file__);plan=read(ROOT/'protocol.json')
    previous=ROOT/'protocol-before-replay-import-fix.json'
    if not previous.exists():previous.write_bytes((ROOT/'protocol.json').read_bytes())
    allowed=str(changed)
    unexpected=[]
    for file,h in plan['sources'].items():
        if digest(Path(file))!=h and str(Path(file).resolve())!=str(changed.resolve()):unexpected.append(file)
    if unexpected:raise ValueError('Other sealed inputs changed: '+str(unexpected[:10]))
    total=0
    for n,task in enumerate(plan['tasks']):
        folder=ROOT/'jobs'/task['key'];done=read(folder/'done.json')
        if done['status']!='COMPLETED':raise ValueError('Training job not complete: '+task['key'])
        for file,h in done['outputs'].items():
            if digest(folder/file)!=h:raise ValueError('Training output changed: '+str(folder/file))
        models=read(folder/'models.json')['models'];groups={}
        for r in models:
            if digest(Path(r['file']))!=r['sha256']:raise ValueError('Model weights changed')
            if r['features']!=plan['features'][r['variant']]:raise ValueError('Feature ordering differs')
            key=(r['symbol'],r['model_year']);signature=tuple(r[c] for c in ['fit_rows','calibration_rows','fit_start','fit_end','calibration_start','calibration_end','available'])
            if key in groups and groups[key]!=signature:raise ValueError('Group fit/calibration samples differ')
            groups[key]=signature
        total+=len(models)
        atomic_json(ROOT/'progress.json',dict(status='VERIFYING_COMPLETED_MODELS',completed=n+1,total=len(plan['tasks']),models=total))
    old_hash=next((h for file,h in plan['sources'].items() if Path(file).resolve()==changed.resolve()),None)
    for file in list(plan['sources']):
        if str(Path(file).resolve())==str(changed.resolve()):plan['sources'][file]=digest(changed)
    plan['sources'][str(Path(__file__))]=digest(Path(__file__))
    plan['replay_import_fix']=dict(file=str(changed),old_sha256=old_hash,new_sha256=digest(changed),
        cause='EXT does not exist in extensions module; use its ROOT constant',
        training_jobs_verified=len(plan['tasks']),models_verified=total,refits=0,
        recovered_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'replay-import-recovery.json',plan['replay_import_fix'])


def main():
    try:
        verify_and_reseal()
        from scripts.research import us_q051_feature_groups_replay_20261116 as replay
        replay.prepare_market()
        launch_tasks([v+'_'+p for v in GROUPS for p in ['SIMPLE','VOL20_REGIME']],3,'case')
        replay.finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise


if __name__=='__main__':main()
