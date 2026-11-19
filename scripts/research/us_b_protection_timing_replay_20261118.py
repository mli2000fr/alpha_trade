"""Secondary economic test of revised ON/OFF after user steering.

One additional fixed case, not a threshold grid. Previous four stay immutable.
No claim of a fresh holdout: timing diagnostics2024/25 were already inspected.
"""
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
import os
import shutil
import pandas as pd

from scripts.research import us_b_protection_partial_20261118 as base
from scripts.research.us_b_protection_timing_20261118 import observable
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_b_protection_timing_replay/20261118-v1')
CASE='HALF_LOCAL_TIMING'


def states(equity):
    f=observable(equity);phase='NORMAL';bad=good=stable=0;started=None;rows=[]
    for offset,(day,row) in enumerate(f.iterrows()):
        transition='';previous=phase
        danger=pd.notna(row.dd20) and row.dd20<=-.08 and row.return5<0
        improving=pd.notna(row.ema10) and row.return5>0 and row.shadow_equity>row.ema10
        bad=bad+1 if danger else 0
        if phase!='PROTECTED' and bad>=2:
            phase='PROTECTED';transition='ON';started=offset;bad=good=stable=0
        elif phase=='PROTECTED':
            good=good+1 if improving else 0
            if offset-started>=3 and good>=2:
                phase='PROBE';transition='PROBE';bad=stable=0
        elif phase=='PROBE':
            stable=stable+1 if improving and pd.notna(row.shadow_equity) and equity.loc[day]/equity.shift(10).loc[day]-1>0 else 0
            if stable>=5:phase='NORMAL';transition='OFF';bad=good=stable=0
        rows.append(dict(signal_date=day,phase=phase,active=phase!='NORMAL',transition=transition,
            previous_phase=previous,shadow_return5=row.return5,shadow_dd20=row.dd20,
            shadow_ema10=row.ema10,bad_count=bad,recovery_count=good,stable_count=stable))
    return pd.DataFrame(rows).set_index('signal_date')


def prepare():
    if (ROOT/'protocol.json').exists():return
    ROOT.mkdir(parents=True,exist_ok=True)
    plan=deepcopy(base.read(base.ROOT/'protocol.json'))
    shadow_path=base.source.ROOT/'cases/SL10/result/equity-daily.csv'
    shadow=pd.read_csv(shadow_path,index_col=0,parse_dates=True).equity
    shadow=pd.concat([pd.Series([4000.],index=pd.to_datetime(['2020-12-31'])),shadow])
    frame=states(shadow)
    for cut in ['2022-12-30','2024-11-29','2025-05-30']:
        pd.testing.assert_frame_equal(frame.loc[:cut],states(shadow.loc[:cut]))
    inputs=ROOT/'inputs';inputs.mkdir(exist_ok=True);frame.to_parquet(inputs/'states.parquet')
    sources=plan['sources']
    for name in [Path(__file__),shadow_path,inputs/'states.parquet']:
        sources[str(name)]=digest(name)
    market=base.read(base.ROOT/'inputs/manifest.json');files=dict(market['files'])
    tape=inputs/'intraday';tape.mkdir(exist_ok=True)
    for path in (base.ROOT/'inputs/intraday').iterdir():
        if not path.is_file():continue
        target=tape/path.name
        try:os.link(path,target)
        except OSError:shutil.copyfile(path,target)
        files[str(target)]=digest(target)
    atomic_json(inputs/'manifest.json',dict(files=files,provider_calls=0,SQL_reads=0))
    target=ROOT/'variants'/CASE/'signals.parquet';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(base.ROOT/'variants/SL10/signals.parquet',target);sources[str(target)]=digest(target)
    plan.update(study='Secondary revised timing, one partial-protection case',cases={CASE:dict(fraction=.5)},
        activation='Virtual unprotected B+antiSL DD20<=-8% and return5<0,2closes; enabled outside PROTECTED including during PROBE',
        recovery='After min3protected sessions, return5>0 and NAV>EMA10 for2closes -> PROBE;5further improving closes AND return10>0 -> NORMAL',
        no_old_peak_anchor=True,rearm='New deterioration qualifies at2closes after return to PROBE/NORMAL; no repeated basket while continuously PROTECTED',
        secondary_after_2024_inspection=True,threshold_optimization=False,independent_holdout=False,
        parameters_changed_after_this_replay=False,production_changes=False)
    atomic_json(ROOT/'protocol.json',plan)
    atomic_json(ROOT/'preflight.json',dict(status='PASS',prefix_checks=3,identical_reference_signals=True,
        half_core_policy_unchanged=True,matched_control_campaign=str(base.ROOT)))


def run():
    from backtesting.simulator import BacktestEngine
    prepare();frame=pd.read_parquet(ROOT/'inputs/states.parquet')
    native=BacktestEngine.run
    with patch.object(base.source,'ROOT',ROOT),patch.object(BacktestEngine,'run',
        base.protected_run(native,ROOT/'cases'/CASE/'result',frame,.5)):
        base.source.run_case(CASE)
    atomic_json(ROOT/'progress.json',dict(status='REPLAY_COMPLETE_REVIEW_PENDING',case=CASE,
        result=base.read(ROOT/'cases'/CASE/'result/report.json')))


if __name__=='__main__':run()
