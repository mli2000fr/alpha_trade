"""B-only counterpart to SL30/pause100, scheduled alongside the T0 variant.

Reuse the sealed causal stop adapter without editing its running source. The
B no-pause curve must reproduce B_SIMPLE before any comparison is released.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from unittest.mock import patch

import numpy as np
import pandas as pd

from scripts.research import us_q051_sl_pause_20261116 as pause
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest

ROOT = Path('artifacts/research/us_q051_sl_pause/20261116-B-30sessions-pause100-v1')
T0 = pause.ROOT
BASELINE = pause.REFERENCE/'variants/B/cases/B_SIMPLE'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def reference_ready(folder=T0):
    """Actual causal-adapter control validation, not its mere local report."""
    file = Path(folder)/'cases/CONTROL/validation.json'
    if file.exists():
        r = read(file)
        if r.get('status') != 'PASS' or r.get('control_equivalence') is not True:
            raise ValueError('T0 control validation failed')
        return True
    state = read(Path(folder)/'progress.json')
    if state.get('status') == 'FAILED':
        raise ValueError('T0 campaign failed before releasing its pause variant: '+str(state.get('error')))
    return False


def baseline_csv_reader(reader):
    """Route only the unchanged adapter's exact baseline check to B_SIMPLE."""
    old = (pause.REFERENCE/'variants/T0/cases/T0_SIMPLE/result/equity-daily.csv').resolve()
    actual = BASELINE/'result/equity-daily.csv'
    def load(file, *args, **kwargs):
        if isinstance(file, (str, Path)) and Path(file).resolve() == old:
            file = actual
        return reader(file, *args, **kwargs)
    return load


def prepare():
    if (ROOT/'protocol.json').exists():
        return read(ROOT/'protocol.json')
    ROOT.mkdir(parents=True, exist_ok=True)
    source_plan = read(T0/'protocol.json')
    expected = pd.read_parquet(pause.REFERENCE/'variants/B/signals.parquet')
    sources = dict(source_plan['sources'])
    for file in [T0/'protocol.json',Path(__file__),Path('tests/test_q051_sl_pause_b.py'),
                 pause.REFERENCE/'variants/B/signals.parquet',BASELINE/'protocol.json',
                 BASELINE/'result/equity-daily.csv',BASELINE/'result/report.json']:
        sources[str(file)] = digest(file)
    for y in range(2021,2027):
        pieces=[]
        for task in (t for t in source_plan['tasks'] if t['year']==y):
            folder=T0/'jobs'/task['key'];file=folder/'B-probabilities.parquet'
            done=read(folder/'done.json')
            if digest(file)!=done['outputs'][file.name]:
                raise ValueError('Changed B score cache: '+str(file))
            pieces.append(pd.read_parquet(file))
            sources[str(file)]=done['outputs'][file.name]
        probabilities=pd.concat(pieces,ignore_index=True)
        oracle=pd.read_parquet(T0/'years'/str(y)/'pool.parquet')
        frame=oracle.merge(probabilities,on=['date','symbol'],how='left',validate='one_to_one')
        frame['short_probability']=np.nan
        control=pd.concat([pause.choose(g,set(),len(source_plan['universe']))[0]
            for _,g in frame.groupby('date',sort=True)],ignore_index=True)
        control['rank']=control['rank'].astype(int)
        e=expected[expected.entry_year.eq(y)].rename(columns={'trade_date':'date'})
        k=['date','rank','symbol']
        a=control.sort_values(k)[k+['long_probability']].reset_index(drop=True)
        b=e.sort_values(k)[k+['long_probability']].reset_index(drop=True)
        if not a[k].equals(b[k]) or not np.allclose(a.long_probability,b.long_probability,atol=1e-12,rtol=0):
            raise ValueError('B no-pause selection differs from original B '+str(y))
        folder=ROOT/'years'/str(y);folder.mkdir(parents=True,exist_ok=True)
        frame.to_parquet(folder/'rankings.parquet',index=False)
        sources[str(folder/'rankings.parquet')]=digest(folder/'rankings.parquet')
        atomic_json(folder/'equivalence.json',dict(status='PASS',selected=len(a),baseline='B_SIMPLE'))
        atomic_json(ROOT/'progress.json',dict(status='PREPARING_B_SELECTIONS',completed=y-2020,total=6))
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True)
    for name in ['open','high','low','close','volume','sectors','actions']:
        src=T0/'inputs'/(name+'.parquet');target=inputs/src.name
        if digest(src)!=read(T0/'inputs/manifest.json')['files'][str(src)]:
            raise ValueError('Changed common daily tape')
        shutil.copyfile(src,target);sources[str(target)]=digest(target)
    atomic_json(inputs/'manifest.json',dict(files={str(p):digest(p) for p in inputs.glob('*.parquet')},
        identical_to=str(T0/'inputs/manifest.json'),SQL_writes=0,provider_calls=0))
    plan=deepcopy(source_plan)
    plan.update(baseline='B_SIMPLE',variant='B',features=source_plan['features']['B'],
        reference=read(BASELINE/'protocol.json')['reference'],sources=sources,
        reference_root=str(BASELINE),reference_refits=0,
        score_cache=str(T0),new_training=0,
        launch='B control starts immediately; B pause starts when T0 control validation PASS releases T0 pause',
        publish='Require exact B selections and full B no-pause capital curve before releasing comparison',
        created_at_utc=datetime.now(timezone.utc).isoformat())
    if len(plan['features'])!=29:raise ValueError('Expected 24+5 B inputs')
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'score-cache-validation.json',dict(status='PASS',no_pause_selection='EXACT_B_2021_2026',
        features=29,reference_refits=0,new_training=0))
    return plan


def run_case(name):
    # The imported adapter is only rebound in this isolated child process.
    reader=pd.read_csv
    with patch.object(pause,'ROOT',ROOT),patch.object(pd,'read_csv',baseline_csv_reader(reader)):
        pause.run_case(name!='CONTROL')
    folder=ROOT/'cases'/name
    report=read(folder/'result/report.json')
    report.update(variant='B',directional_features=29,baseline='B_SIMPLE',
        comparison_release='REQUIRES_B_CONTROL_VALIDATION')
    atomic_json(folder/'result/report.json',report)


def finish():
    if read(ROOT/'cases/CONTROL/validation.json').get('control_equivalence') is not True:
        raise ValueError('Cannot release comparison without B control equity equivalence')
    from scripts.research.us_q051_feature_groups_replay_20261116 import validate_case
    for name in ['CONTROL','PAUSE100_SL30']:validate_case(ROOT/'cases'/name)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rows=[];curves=[];annual=[]
    for name,folder in [('B_SIMPLE',BASELINE),('B_SL30_PAUSE100',ROOT/'cases/PAUSE100_SL30')]:
        r=read(folder/'result/report.json')
        keys=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','win_pct',
            'average_gross_capital','average_gross_equity_ratio','average_winning_pnl','average_losing_pnl']
        rows.append(dict(case=name,**{k:r.get(k) for k in keys}))
        curves.append(pd.read_csv(folder/'result/equity-daily.csv',index_col=0,parse_dates=True).equity.rename(name))
        a=pd.read_csv(folder/'result/annual-summary.csv');a['case']=name;annual.append(a)
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(ROOT/'annual-comparison.csv',index=False)
    curve=pd.concat(curves,axis=1);curve.to_csv(ROOT/'capital-curves.csv')
    ax=curve.plot(figsize=(13,7),title='Q051 B / B + deux SL dans30 séances → pause100 avant Oracle')
    ax.set_ylabel('Capital ($)');ax.grid(alpha=.2);ax.figure.tight_layout()
    ax.figure.savefig(ROOT/'capital-comparison.png',dpi=140);plt.close(ax.figure)
    atomic_json(ROOT/'validation.json',dict(status='ARITHMETIC_AND_B_CONTROL_EQUIVALENCE_PASS_RESEARCH_ONLY',
        strict_pit=False,full_live_parity=False,price_scope='NEW_HOLDING_WINDOWS_REQUIRE_PRICE_REVIEW',production_changes=False))
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',cases=rows,production_changes=False))


def run():
    active={};handles=[];completed=[];started_pause=False
    def launch(name):
        logs=ROOT/'logs';logs.mkdir(exist_ok=True)
        out=(logs/(name+'.stdout.log')).open('ab');err=(logs/(name+'.stderr.log')).open('ab');handles.extend([out,err])
        cmd=[sys.executable,'-X','utf8','-u','-m',__spec__.name,'--phase','case','--key',name]
        active[name]=subprocess.Popen(cmd,cwd=Path.cwd(),stdout=out,stderr=err,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        prepare()
        control=ROOT/'cases/CONTROL/validation.json'
        if control.exists():
            if read(control).get('control_equivalence') is not True:raise ValueError('B control not qualified')
            completed.append('CONTROL')
        else:launch('CONTROL')
        if (ROOT/'cases/PAUSE100_SL30/validation.json').exists():
            started_pause=True;completed.append('PAUSE100_SL30')
        while active or not started_pause:
            if not started_pause and reference_ready():
                launch('PAUSE100_SL30');started_pause=True
                atomic_json(ROOT/'pause-launch.json',dict(started_at_utc=datetime.now(timezone.utc).isoformat(),
                    trigger=str(T0/'cases/CONTROL/validation.json'),parallel_with='T0 PAUSE100_SL30'))
            for name,child in list(active.items()):
                code=child.poll()
                if code is None:continue
                if code:raise RuntimeError(name+' failed; inspect its case-local stderr log')
                completed.append(name);del active[name]
            atomic_json(ROOT/'progress.json',dict(status='REPLAYING' if started_pause else 'B_CONTROL_AND_WAITING_FOR_T0_CONTROL',
                completed=completed,active=list(active),pause_started=started_pause,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            if active or not started_pause:time.sleep(2)
        finish()
    except BaseException as exc:
        atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
    finally:
        for child in active.values():
            if child.poll() is None:child.terminate();child.wait()
        for stream in handles:stream.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['all','prepare','case','finish'],required=True)
    parser.add_argument('--key');args=parser.parse_args()
    if args.phase=='all':run()
    elif args.phase=='prepare':prepare()
    elif args.phase=='case':run_case(args.key)
    else:finish()
