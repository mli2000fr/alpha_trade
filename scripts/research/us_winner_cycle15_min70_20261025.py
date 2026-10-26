"""Paired min70/$4000 replay: full liquidation at cycleDD15, three-month pause.

Reuse the audited no-pause control. A20session current-engine bridge must match
its archived curve and financial events before starting the new full account.
"""
from dataclasses import asdict,replace
from datetime import datetime,timezone
import json
import logging
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from scripts.research import us_winner_cycle15_matched_capital_20261025 as shared

cycle,study,grid,base=shared.cycle,shared.study,shared.grid,shared.base
ROOT=Path('artifacts/research/us_winner_cycle15_min70/20261025-v1')
CONTROL=Path('artifacts/research/us_winner_min70_4000/20261025-v1')
CONTROL_CASE=CONTROL/'cases/FIXED_REFERENCE_MIN70'
ARM='FIXED_SL5_MIN70_CYCLE15_PAUSE3M'
DOC=Path('doc/ml/winner_cycle15_min70_protocole_20261025.md')
TEST=Path('tests/test_us_winner_cycle15_min70_20261025.py')
NEW_DEFAULTS=dict(winner_global_drawdown_halt=False,winner_hard_drawdown_pct=None,
    winner_cycle_drawdown_pct=None,winner_drawdown_cooldown_months=0)


def normalized(cfg):return json.loads(json.dumps(asdict(cfg),default=str))


def base_configuration(parent):
    cfg=study.configuration(parent['reference_config'],study.inputs.START)
    cfg=replace(cfg,risk_config=replace(cfg.risk_config,min_position_notional=70.))
    actual=normalized(cfg)
    for name,default in NEW_DEFAULTS.items():
        if actual.pop(name)!=default:raise ValueError('Unrequested global risk in bridge')
    if actual!=parent['after']:raise ValueError('Comparator configuration drift')
    return cfg


def with_cycle(cfg):
    risk=replace(cfg.risk_config,max_portfolio_drawdown_pct=.15,force_close_on_breaker=True,
        force_close_pct=1.,rolling_peak_window_days=0)
    changed=replace(cfg,risk_config=risk,
        exec_config=replace(cfg.exec_config,force_close_on_breaker=True,force_close_pct=1.),
        winner_global_drawdown_halt=False,winner_hard_drawdown_pct=None,
        winner_cycle_drawdown_pct=.15,winner_drawdown_cooldown_months=3)
    before,after=normalized(cfg),normalized(changed)
    for key in NEW_DEFAULTS:after[key]=before[key]
    for key in ['max_portfolio_drawdown_pct','force_close_on_breaker','force_close_pct','rolling_peak_window_days']:
        after['risk_config'][key]=before['risk_config'][key]
    for key in ['force_close_on_breaker','force_close_pct']:after['exec_config'][key]=before['exec_config'][key]
    if before!=after:raise ValueError('Non-cycle field changed')
    if changed.initial_equity!=4000. or changed.risk_config.effective_min_notional!=70.:
        raise ValueError('Wrong capital or minimum')
    return changed


def prepare():
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    parent=base.read(CONTROL/'protocol.json')
    shared.verify_old_control(parent)
    report=base.read(CONTROL/'report.json');base.verify(report['files'])
    if report['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Audited control required')
    study.near(report['case']['final_equity'],13641.658042600167)
    current=base.read(cycle.ROOT/'protocol.json');base.verify(current['sources'])
    before=base_configuration(parent);after=with_cycle(before)
    if asdict(study.profile_policy(before.exec_config,study.REFERENCE))!=parent['actual_campaign_policy']:
        raise ValueError('SL5/H20 policy drift')
    sources=dict(current['sources'])
    paths=legacy.legacy_paths()
    # Keep BOTH current and archived engine identities explicit, no verifier
    # monkeypatch that could silently substitute a wrong loaded engine.
    sources.update({str(legacy.effective_source(n,paths)):h for n,h in parent['sources'].items()})
    sources.update(report['files'])
    for p in [Path(__file__),DOC,TEST,Path(shared.__file__),Path(shared.control_audit.__file__),
            CONTROL/'protocol.json',CONTROL/'report.json',cycle.ROOT/'protocol.json']:
        sources[str(p)]=base.digest(p)
    base.verify(sources)
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        no_pause_control=report['case'],control_protocol=parent,
        before=normalized(before),after=normalized(after),actual_campaign_policy=parent['actual_campaign_policy'],
        initial_equity=4000.,currency='USD',minimum_notional=70.,TOP=20,start='2020-01-02',end='2024-12-31',
        full_position=True,no_reinforcement=True,gross_cap=1.,fee_per_leg=.0008,
        cycle_drawdown=.15,pause_calendar_months=3,global_historical_cap=None,
        no_annual_reset=True,no_recapitalization=True,monthly_selection=False,
        bridge='20first real sessions; exact curve/financial-event parity; not a full history engine-parity certification',
        engine_change='Current global-liquidation engine; disabled-path20session bridge required against legacy control',
        sources_effective_archived_and_current_separate=True,full_live_parity=False,independent_holdout=False,
        future_coverage_selection_bias=True,current_sectors_non_PIT=True,
        SQL_reads=0,SQL_writes=0,provider_calls=0,LLM_calls=0,training=False,orders=False,production_changed=False)
    ROOT.mkdir(parents=True,exist_ok=False);base.save_new(ROOT/'protocol.json',protocol)
    grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol


def run_engine(cfg,tape,arm,progress):
    signals=tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
    prior=max(d for d in tape.schedule if d<cfg.start_date)
    signals=signals[signals.trade_date.ge(pd.Timestamp(prior))];signals['side']='long'
    with grid.runtime_adapter(2020,arm),study.capacity.corrected_runtime(),cycle.repair.campaign_adapter(
            cfg.exec_config,lambda _d:study.REFERENCE) as metadata:
        result=base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
            high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
            sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
            winner_progress=progress,winner_corporate_actions=tape.actions.to_dict('records'))
    return result,metadata


def bridge(parent,tape):
    cfg=base_configuration(parent)
    days=sorted(d for d in tape.schedule if cfg.start_date<=d<=cfg.end_date);end=days[19]
    cfg=replace(cfg,end_date=end)
    def progress(done,total,day):
        grid.atomic_json(ROOT/'progress.json',dict(status='CONTROL_ENGINE_BRIDGE',completed_runs=0,total_runs=1,
            completed_sessions=done,total_sessions=total,last_date=str(day)))
    result,metadata=run_engine(cfg,tape,'MIN70_DISABLED_POLICY_BRIDGE',progress)
    summary=grid.metrics(result,4000.)
    if summary['global_liquidation']['enabled']:raise ValueError('Bridge unexpectedly liquidates')
    checks=shared.control_audit.audit_case(study,result,summary,metadata,tape,4000.,end)
    expected=pd.read_parquet(CONTROL_CASE/'equity-5m.parquet')
    expected=expected[pd.to_datetime(expected.timestamp,utc=True).le(pd.Timestamp(tape.schedule[end].close_at_utc))]
    got=result.intraday_equity_curve
    if not pd.to_datetime(got.timestamp,utc=True).reset_index(drop=True).equals(
            pd.to_datetime(expected.timestamp,utc=True).reset_index(drop=True)):
        raise ValueError('Bridge timestamps mismatch')
    np.testing.assert_allclose(got[['equity','gross']],expected[['equity','gross']],rtol=0,atol=1e-7)
    old=pd.read_csv(CONTROL_CASE/'events.csv',low_memory=False)
    old=old[old.event.notna()&pd.to_datetime(old.time,utc=True).le(pd.Timestamp(tape.schedule[end].close_at_utc))]
    new=result.trade_events_df[result.trade_events_df.event.notna()]
    if len(old)!=len(new):raise ValueError('Bridge financial events count mismatch')
    for (_,a),(_,b) in zip(old.iterrows(),new.iterrows()):
        if pd.Timestamp(a.time)!=pd.Timestamp(b.time) or a.event!=b.event:
            raise ValueError('Bridge chronology mismatch')
        if (None if pd.isna(a.symbol) else a.symbol)!=(None if pd.isna(b.symbol) else b.symbol):
            raise ValueError('Bridge symbol mismatch')
        for key in ['quantity','price','costs']:
            if pd.isna(a[key]) and pd.isna(b[key]):continue
            study.near(a[key],b[key])
    folder=ROOT/'control-bridge20';folder.mkdir()
    got.to_parquet(folder/'equity-5m.parquet',index=False)
    base.save_new(folder/'report.json',dict(status='PASS_BOUNDED_CONTROL_BRIDGE',sessions=20,end=str(end),
        exact_legacy_curve_parity=True,financial_events=len(new),audit=checks,
        whole_history_parity_claimed=False,files={'equity-5m.parquet':base.digest(folder/'equity-5m.parquet')}))
    tape.month.cache_clear()


def run():
    protocol=prepare();started=time.monotonic()
    with grid.run_lock(ROOT):
        grid.atomic_json(ROOT/'process.json',dict(pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat()))
        grid.atomic_json(ROOT/'progress.json',dict(status='VERIFYING_FROZEN_INPUTS',completed_runs=0,total_runs=1))
        tape=cycle.BASE_TAPE(cycle.INPUT_ROOT)
        bridge(protocol['control_protocol'],tape)
        cfg=with_cycle(base_configuration(protocol['control_protocol']))
        if normalized(cfg)!=protocol['after']:raise ValueError('Effective configuration drift')
        folder=ROOT/'cases'/ARM;folder.mkdir(parents=True)
        def progress(done,total,day):
            elapsed=time.monotonic()-started
            grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',completed_runs=0,total_runs=1,
                completed_sessions=done,total_sessions=total,last_date=str(day),elapsed_seconds=elapsed,
                estimated_remaining_seconds=elapsed*(total-done)/done,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
        with shared.scope(folder):
            result,metadata=run_engine(cfg,tape,ARM,progress)
            grid.atomic_json(ROOT/'progress.json',dict(status='AUDITING',completed_runs=0,total_runs=1))
            summary=grid.metrics(result,4000.);checks=cycle.audit(result,summary,metadata,tape)
        if summary['status']!='COMPLETED_EXPLORATORY' or summary['coverage_gaps']:raise ValueError('Incomplete study')
        summary['outer_admission_policy']=summary.pop('policy')
        summary.update(arm=ARM,start=protocol['start'],end=protocol['end'],currency='USD',minimum_notional=70.,
            initial_equity=4000.,actual_campaign_policy=protocol['actual_campaign_policy'],audit=checks,
            annual=shared.control_audit.annual_rows(result,4000.))
        if any(m['policy']!=protocol['actual_campaign_policy'] for m in metadata.values()):
            raise ValueError('Campaign policy changed')
        for name,frame in [('trades',result.closed_trades_df),('equity-5m',result.intraday_equity_curve),
                ('breaker-5m',result.drawdown_breaker_df)]:frame.to_parquet(folder/(name+'.parquet'),index=False)
        result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
        result.trade_events_df.to_csv(folder/'events.csv',index=False)
        grid.atomic_json(folder/'campaign-policies.json',metadata)
        summary['files']={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()}
        base.verify(protocol['sources']);base.save_new(folder/'report.json',summary)
        pd.DataFrame(summary['annual']).to_csv(ROOT/'annual-summary.csv',index=False)
        keys=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_gross_capital',
            'average_gross_equity_ratio','average_winning_pnl','average_losing_pnl','costs']
        baseline=protocol['no_pause_control']
        compare={k:dict(no_pause=baseline[k],cycle15_pause=summary[k],delta=summary[k]-baseline[k]) for k in keys}
        base.save_new(ROOT/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',case=summary,
            comparator=baseline,comparison=compare,sources=protocol['sources'],
            files={str(folder/n):h for n,h in summary['files'].items()},
            independent_holdout=False,full_live_parity=False,future_coverage_selection_bias=True))
        grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=1,total_runs=1))


def main():
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No network in min70 cycle study'))
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    try:run()
    except BaseException as exc:
        if ROOT.exists():grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
