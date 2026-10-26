"""One fixedSL5/H20 TOP20 account with cycleDD15/3m pause and matched deposit.

Reuse sealed local inputs and existing native cycle adapter. No SQL, network,
training, broker or production change; do not rerun the already audited control.
"""
from contextlib import contextmanager
from copy import copy
from dataclasses import asdict,replace
from datetime import datetime,timezone
import logging
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from scripts.research import us_winner_monthly_cycle15_20261025 as cycle
from scripts.research import us_winner_start_state_audit_20261025 as control_audit

study=cycle.study
grid,base=study.capacity.grid,study.capacity.grid.base
ROOT=Path('artifacts/research/us_winner_cycle15_matched_capital/20261025-v1')
PARENT=cycle.ROOT
CONTROL=control_audit.ROOT/'cases/FRESH_2020_MATCHED_CAPITAL'
ARM='FIXED_SL5_H20_CYCLE15_PAUSE3M_MATCHED_CAPITAL'
DOC=Path('doc/ml/winner_cycle15_capital_7980_20261025.md')
TEST=Path('tests/test_us_winner_cycle15_matched_capital_20261025.py')


def matched_configuration(parent,start,initial):
    if not np.isfinite(initial) or initial<=0:raise ValueError('Positive explicit initial deposit required')
    cfg=cycle.configuration(parent,start)
    return replace(cfg,initial_equity=initial,risk_config=replace(cfg.risk_config,account_equity=initial),
        exec_config=replace(cfg.exec_config,simulated_account_equity=initial))


def verify_capital_only(before,after,initial):
    a,b=asdict(before),asdict(after)
    if (b['initial_equity']!=initial or b['risk_config']['account_equity']!=initial
            or b['exec_config']['simulated_account_equity']!=initial):
        raise ValueError('Inconsistent account deposit')
    b['initial_equity']=a['initial_equity']
    b['risk_config']['account_equity']=a['risk_config']['account_equity']
    b['exec_config']['simulated_account_equity']=a['exec_config']['simulated_account_equity']
    if a!=b:raise ValueError('A non-capital configuration field changed')


def financial_events(events):
    events=events[events.event.notna()].copy()
    money={'BUY_FILL','SELL_FILL','FINANCING'}
    markers=events[~events.event.isin(money)]
    if not markers.event.isin(['GLOBAL_DD_TRIGGER','GLOBAL_DD_RESUME']).all():
        raise ValueError('Unknown accounting event')
    for key in ['costs','quantity']:
        if key in markers and markers[key].fillna(0).ne(0).any():
            raise ValueError('Monetary mutation hidden inside a risk marker')
    return events[events.event.isin(money)]


def explicit_normal_audit(result,summary,metadata,tape):
    # cycle.audit has already removed global trades from scalar exit checking,
    # but cash MUST include all fills, including the full liquidation sales.
    checked=copy(result);checked.trade_events_df=financial_events(result.trade_events_df)
    return control_audit.audit_case(study,checked,summary,metadata,tape,
        summary['initial_equity'],study.inputs.END)


@contextmanager
def scope(folder):
    old_base_audit,old_folder=cycle.BASE_AUDIT,cycle.CURRENT_FOLDER
    with cycle.installed():
        cycle.BASE_AUDIT,cycle.CURRENT_FOLDER=explicit_normal_audit,folder
        try:yield
        finally:cycle.BASE_AUDIT,cycle.CURRENT_FOLDER=old_base_audit,old_folder


def verify_old_control(protocol):
    # The comparator used the exact archived pre-global-liquidation engine.
    # Verify those bytes without loading that old engine into THIS cycle run.
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    paths=legacy.legacy_paths()
    for name,sha in protocol['sources'].items():
        if base.digest(legacy.effective_source(name,paths))!=sha:
            raise ValueError('Archived comparator source changed: '+name)


def prepare():
    parent=base.read(PARENT/'protocol.json');base.verify(parent['sources'])
    baseline=base.read(PARENT/'cases/FIXED_REFERENCE/report.json')
    prior_control=base.read(CONTROL/'report.json')
    parent_control=base.read(control_audit.ROOT/'protocol.json');verify_old_control(parent_control)
    if baseline['audit']['status']!='PASS_CYCLE15_FULL_SALES_PAUSES_RESETS_CASH_FEES_ENTRIES':
        raise ValueError('Audited4000 cycle comparator required')
    if prior_control['audit']['status']!='PASS_EXPLICIT_DEPOSIT_CASH_FEES_SCALAR_EXITS_ENTRIES_COVERAGE':
        raise ValueError('Audited matched-capital no-pause control required')
    initial=float(prior_control['initial_equity'])
    if abs(initial-7980.17)>.01:raise ValueError('Unexpected control capital')
    start=min(s.session_date for s in study.inputs.sessions(start=study.inputs.START) if s.session_date>=study.inputs.START)
    cfg=matched_configuration(parent,start,initial)
    verify_capital_only(cycle.configuration(parent,start),cfg,initial)
    actual_policy=asdict(study.profile_policy(cfg.exec_config,study.REFERENCE))
    if actual_policy!=prior_control['actual_campaign_policy']:
        raise ValueError('ActualSL5/H20 policy differs from no-pause comparator')
    sources=dict(parent['sources'])
    for folder,report in [(PARENT/'cases/FIXED_REFERENCE',baseline),(CONTROL,prior_control)]:
        files={str(folder/n):h for n,h in report['files'].items()};base.verify(files);sources.update(files)
        sources[str(folder/'report.json')]=base.digest(folder/'report.json')
    for path in [Path(__file__),DOC,TEST,Path(control_audit.__file__),PARENT/'protocol.json',
            control_audit.ROOT/'protocol.json',control_audit.ROOT/'report.json']:
        sources[str(path)]=base.digest(path)
    ROOT.mkdir(parents=True,exist_ok=False)
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        experiment='FIXED_SL5_H20_CYCLE15_MATCHED_CAPITAL',initial_equity=initial,display_initial_equity=7980.17,
        start=str(start),end=str(study.inputs.END),reference_config=parent,
        actual_policy=actual_policy,effective_config=asdict(cfg),
        changed_fields=['initial_equity','risk_config.account_equity','exec_config.simulated_account_equity'],
        control_no_pause=prior_control,control_cycle_4000=baseline,
        input_root=str(cycle.INPUT_ROOT),new_accounts=1,monthly_selection=False,
        TOP=20,gross_cap=1.,full_position=True,no_reinforcement=True,fee_per_leg=.0008,
        cycle_drawdown=.15,pause_calendar_months=3,hard_historical_cap=None,
        no_annual_reset=True,no_recapitalization=True,
        historical_model_and_sector_limits_preserved=True,future_coverage_selection_bias=True,
        independent_holdout=False,full_live_parity=False,SQL_reads=0,SQL_writes=False,
        provider_calls=0,LLM_calls=0,orders=False,production_changed=False)
    base.save_new(ROOT/'protocol.json',p)
    grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return p


def run():
    protocol=prepare();initial=protocol['initial_equity'];started=time.monotonic()
    with grid.run_lock(ROOT):
        grid.atomic_json(ROOT/'process.json',dict(pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat()))
        grid.atomic_json(ROOT/'progress.json',dict(status='VERIFYING_FROZEN_LOCAL_INPUTS',completed_runs=0,total_runs=1))
        tape=cycle.BASE_TAPE(cycle.INPUT_ROOT)
        start=pd.Timestamp(protocol['start']).date()
        cfg=matched_configuration(protocol['reference_config'],start,initial)
        signals=tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
        prior=max(d for d in tape.schedule if d<start)
        signals=signals[signals.trade_date.ge(pd.Timestamp(prior))];signals['side']='long'
        folder=ROOT/'cases'/ARM;folder.mkdir(parents=True)
        def progress(done,total,day):
            elapsed=time.monotonic()-started
            grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',arm=ARM,initial_equity=initial,
                completed_runs=0,total_runs=1,completed_sessions=done,total_sessions=total,last_date=day,
                elapsed_seconds=elapsed,estimated_remaining_seconds=elapsed*(total-done)/done,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
        with scope(folder):
            with grid.runtime_adapter(2020,ARM),study.capacity.corrected_runtime(),cycle.repair.campaign_adapter(
                    cfg.exec_config,lambda _day:study.REFERENCE) as metadata:
                result=base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
                    high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
                    sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
                    winner_progress=progress,winner_corporate_actions=tape.actions.to_dict('records'))
            grid.atomic_json(ROOT/'progress.json',dict(status='AUDITING',completed_runs=0,total_runs=1))
            summary=grid.metrics(result,initial)
            checks=cycle.audit(result,summary,metadata,tape)
        if summary['status']!='COMPLETED_EXPLORATORY' or summary['coverage_gaps']:
            raise ValueError('Incomplete replay')
        values=result.closed_trades_df
        summary['outer_admission_policy']=summary.pop('policy')
        summary.update(arm=ARM,start=str(start),end=str(study.inputs.END),audit=checks,
            actual_campaign_policy=protocol['actual_policy'],initial_equity=initial)
        # Calendar and session durations are distinct; publish native calendar
        # holding_days and calculate session counts explicitly from actual fills.
        schedule=sorted(tape.schedule);idx={d:i for i,d in enumerate(schedule)}
        durations=[idx[pd.Timestamp(t.exit_date).tz_convert('America/New_York').date()]-
            idx[pd.Timestamp(t.entry_date).tz_convert('America/New_York').date()]+1 for t in values.itertuples()]
        counts=pd.Series(durations,index=values.index,dtype=float)
        summary['average_winning_holding_sessions']=float(counts[values.pnl.gt(0)].mean()) if values.pnl.gt(0).any() else None
        summary['average_losing_holding_sessions']=float(counts[values.pnl.lt(0)].mean()) if values.pnl.lt(0).any() else None
        for name,frame in [('trades',values),('equity-5m',result.intraday_equity_curve),('breaker-5m',result.drawdown_breaker_df)]:
            frame.to_parquet(folder/(name+'.parquet'),index=False)
        result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
        result.trade_events_df.to_csv(folder/'events.csv',index=False)
        grid.atomic_json(folder/'campaign-policies.json',metadata)
        summary['files']={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()}
        base.save_new(folder/'report.json',summary)
        annual=control_audit.annual_rows(result,initial)
        comparator=protocol['control_no_pause']
        base.verify(protocol['sources'])
        base.save_new(ROOT/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',case=summary,annual=annual,
            comparison=dict(initial_equity=initial,no_pause_final_equity=comparator['final_equity'],
                cycle_pause_final_equity=summary['final_equity'],delta_usd=summary['final_equity']-comparator['final_equity'],
                no_pause_dd_pct=comparator['max_drawdown_pct'],cycle_pause_dd_pct=summary['max_drawdown_pct']),
            sources=protocol['sources'],full_live_parity=False,independent_holdout=False,future_coverage_selection_bias=True))
        grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=1,total_runs=1))


def main():
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No network in matched-capital cycle replay'))
    try:run()
    except BaseException as exc:
        if ROOT.exists():grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
