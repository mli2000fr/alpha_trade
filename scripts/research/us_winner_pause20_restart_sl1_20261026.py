"""DD15/pause20, then20sessions of SL1 entries, followed by ordinary SL5.

Policies are frozen per actual fill. Existing SL1 lots are NEVER widened toSL5.
All other archived portfolio, fee, risk, expiry and admission rules stay fixed.
"""
from contextlib import contextmanager
from dataclasses import asdict,replace
from datetime import datetime,timedelta,timezone
import logging
import os
from pathlib import Path
import time

import numpy as np
import pandas as pd

from scripts.research import us_winner_cycle15_pause20_min70_20261026 as pause

runner,cycle,study,grid,base=pause.runner,pause.cycle,pause.study,pause.grid,pause.base
ROOT=Path('artifacts/research/us_winner_pause20_restart_sl1/20261026-v1')
PARENT=pause.ROOT
ARM='PAUSE20_RESTART_SL1_20SESSIONS_THEN_SL5'
DOC=Path('doc/ml/winner_pause20_restart_sl1_protocole_20261026.md')
TEST=Path('tests/test_us_winner_pause20_restart_sl1_20261026.py')
NORMAL='NORMAL_SL5';DEFENSIVE='RESTART_SL1'
ACTIVE=None


def window_sessions(resume,calendar):
    day=pd.Timestamp(resume).tz_convert('America/New_York').date()
    sessions=[s for s in calendar.sessions(day,day+timedelta(days=100)) if s.is_open]
    if len(sessions)<21 or pd.Timestamp(sessions[0].open_at_utc)!=pd.Timestamp(resume):
        raise ValueError('Restart must be an official session open')
    return sessions[:20],sessions[20]


def phase_for_day(day,resumes,calendar):
    if isinstance(day,str):day=pd.Timestamp(day).date()
    known=[r for r in resumes if pd.Timestamp(r['resumed_at']).tz_convert('America/New_York').date()<=day]
    if not known:return NORMAL
    latest=max(known,key=lambda r:pd.Timestamp(r['resumed_at']))
    sessions,_=window_sessions(latest['resumed_at'],calendar)
    return DEFENSIVE if sessions[0].session_date<=day<=sessions[-1].session_date else NORMAL


class RestartController(pause.SessionCycle):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        global ACTIVE
        if ACTIVE is not None:raise ValueError('Multiple active replay controllers')
        ACTIVE=self;self.restart_windows=[]

    def resume(self,stamp,book):
        resumed=super().resume(stamp,book)
        if resumed:
            sessions,normal=window_sessions(stamp,grid.calendar())
            self.restart_windows.append(dict(cycle=self.cycle,resumed_at=pd.Timestamp(stamp).isoformat(),
                defensive_first_session=str(sessions[0].session_date),defensive_last_session=str(sessions[-1].session_date),
                normal_again_at=pd.Timestamp(normal.open_at_utc).isoformat(),defensive_sessions=20,
                sl_during_restart=.01,sl_after_restart=.05,existing_lots_keep_initial_stop=True))
        return resumed

    def summary(self):
        return dict(super().summary(),restart_sl1_sessions=20,restart_windows=self.restart_windows,
            protection_transition='New actual entries only; no loosening of funded SL1 positions')


@contextmanager
def hybrid_scope(folder):
    import backtesting.winner_global_liquidation as module
    global ACTIVE
    old_active=ACTIVE
    with pause.session_scope(folder):
        controller=module.GlobalLiquidation;catalog=study.CATALOG
        profiles={NORMAL:dict(name=NORMAL,stop_loss_pct=.05,take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=20),
            DEFENSIVE:dict(name=DEFENSIVE,stop_loss_pct=.01,take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=20)}
        module.GlobalLiquidation=RestartController;study.CATALOG={**catalog,**profiles};ACTIVE=None
        try:yield
        finally:module.GlobalLiquidation,study.CATALOG,ACTIVE=controller,catalog,old_active


def select_phase(day):
    if ACTIVE is None:raise ValueError('No initialized drawdown/restart controller')
    return phase_for_day(day,ACTIVE.resumes,grid.calendar())


def audit(result,summary,metadata,tape):
    checks=pause.session_audit(result,summary,metadata,tape)
    info=summary['global_liquidation']
    windows=info.get('restart_windows',[])
    if info.get('restart_sl1_sessions')!=20 or len(windows)!=len(info['resumes']):
        raise ValueError('Restart20 policy missing')
    for resume,window in zip(info['resumes'],windows):
        start=pd.Timestamp(resume['resumed_at']);day=start.tz_convert('America/New_York').date()
        sessions=[s for s in grid.calendar().sessions(day,day+timedelta(days=100)) if s.is_open]
        if (window['cycle']!=resume['cycle'] or pd.Timestamp(window['resumed_at'])!=start
                or window['defensive_first_session']!=str(sessions[0].session_date)
                or window['defensive_last_session']!=str(sessions[19].session_date)
                or pd.Timestamp(window['normal_again_at'])!=pd.Timestamp(sessions[20].open_at_utc)
                or window['sl_during_restart']!=.01 or window['sl_after_restart']!=.05):
            raise ValueError('Wrong20session restart window')
    counts={NORMAL:0,DEFENSIVE:0};filled=set()
    for item in metadata.values():
        if not item.get('first_fill_at'):continue
        stamp=pd.Timestamp(item['first_fill_at']);day=stamp.tz_convert('America/New_York').date()
        past=[r for r in info['resumes'] if pd.Timestamp(r['resumed_at'])<=stamp]
        defensive=False
        if past:
            latest=max(past,key=lambda r:pd.Timestamp(r['resumed_at']))
            begin=pd.Timestamp(latest['resumed_at']).tz_convert('America/New_York').date()
            days=[s.session_date for s in grid.calendar().sessions(begin,begin+timedelta(days=100)) if s.is_open]
            defensive=day in days[:20]
        expected=DEFENSIVE if defensive else NORMAL
        if item['profile']!=expected or item['policy']['stop_loss_pct']!=(.01 if defensive else .05):
            raise ValueError('Actual fill uses wrong phase/stop')
        policy=item['policy']
        if policy['take_profit_pct'] is not None or policy['trailing_stop_pct'] is not None or policy['horizon_sessions']!=20:
            raise ValueError('Non-stop exit policy drift')
        counts[expected]+=1;filled.add((item['symbol'],stamp))
    buys=result.trade_events_df[result.trade_events_df.event.eq('BUY_FILL')]
    if filled!={(r.symbol,pd.Timestamp(r.time)) for r in buys.itertuples()}:raise ValueError('Fill phase coverage mismatch')
    summary.update(entry_phase_counts=counts,restart_windows=windows,variant='cycle15_pause20_then_sl1_20_then_sl5')
    return dict(checks,status='PASS_CYCLE15_PAUSE20_RESTART_SL1_20_FROZEN_LOT_POLICIES',
        phase_checked_buys=sum(counts.values()),phase_counts=counts)


def prepare():
    prior=base.read(PARENT/'protocol.json');base.verify(prior['sources'])
    cfg=pause.with_sessions(runner.base_configuration(prior['control_protocol']))
    if runner.normalized(cfg)!=prior['after']:raise ValueError('Non-phase configuration changed')
    normal=asdict(study.profile_policy(cfg.exec_config,study.REFERENCE));defensive=dict(normal,stop_loss_pct=.01)
    if normal['stop_loss_pct']!=.05:raise ValueError('Expected SL5 outside restart window')
    sources=dict(prior['sources'])
    for path in [PARENT/'protocol.json',Path(__file__),DOC,TEST,Path(pause.__file__)]:sources[str(path)]=base.digest(path)
    base.verify(sources)
    protocol=dict(prior,created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        changed_from_pause20_control=['Actual entry policy SL1 during20officialsessions from each actual resume, SL5 otherwise'],
        effective_config=runner.normalized(cfg),normal_policy=normal,defensive_policy=defensive,
        restart_sl1_sessions=20,position_policy_frozen_at_actual_fill=True,
        pending_unattempted_plans_requalified_without_expiry_extension=True,
        no_pause20_control_outcomes_needed=True,control_pause20_root=str(PARENT))
    ROOT.mkdir(parents=True,exist_ok=False);base.save_new(ROOT/'protocol.json',protocol)
    grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol,cfg


def consolidate(case,protocol):
    cases=dict(NO_PAUSE=protocol['no_pause_control'],PAUSE_3_MONTHS=protocol['three_month_control'])
    ready=(PARENT/'report.json').exists()
    if ready:
        other=base.read(PARENT/'report.json')
        if other['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Incomplete pause20 comparator')
        base.verify(other['sources']);base.verify(other['files']);cases['PAUSE20_SL5']=other['case']
        mine=case['global_liquidation']['resumes'];theirs=other['case']['global_liquidation']['resumes']
        if mine:
            if not theirs or pd.Timestamp(mine[0]['resumed_at'])!=pd.Timestamp(theirs[0]['resumed_at']):
                raise ValueError('First resumption differs before SL1 can affect decisions')
            cutoff=pd.Timestamp(mine[0]['resumed_at'])
            a=pd.read_parquet(ROOT/'cases'/ARM/'equity-5m.parquet')
            b=pd.read_parquet(PARENT/'cases'/pause.ARM/'equity-5m.parquet')
            a=a[pd.to_datetime(a.timestamp,utc=True).lt(cutoff)].reset_index(drop=True)
            b=b[pd.to_datetime(b.timestamp,utc=True).lt(cutoff)].reset_index(drop=True)
            if not pd.to_datetime(a.timestamp,utc=True).equals(pd.to_datetime(b.timestamp,utc=True)):
                raise ValueError('Pre-restart chronology changed')
            np.testing.assert_allclose(a[['equity','gross']],b[['equity','gross']],rtol=0,atol=1e-7)
    cases['PAUSE20_RESTART_SL1_20_THEN_SL5']=case
    keys=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_winning_pnl',
        'average_losing_pnl','average_gross_capital','average_gross_equity_ratio','costs']
    rows=[dict(variant=name,**{k:v[k] for k in keys}) for name,v in cases.items()]
    annual=[dict(variant=name,**r) for name,v in cases.items() for r in v['annual']]
    pd.DataFrame(rows).to_csv(ROOT/'comparison.csv',index=False)
    pd.DataFrame(annual).to_csv(ROOT/'annual-comparison.csv',index=False)
    base.save_new(ROOT/'comparison.json',dict(status='READY' if ready else 'WAITING_PAUSE20_CONTROL',
        cases=cases,summary=rows,annual=annual,pre_first_restart_curve_parity=ready and bool(case['global_liquidation']['resumes']),
        independent_holdout=False,full_live_parity=False))


def run():
    protocol,cfg=prepare();started=time.monotonic()
    with grid.run_lock(ROOT):
        grid.atomic_json(ROOT/'process.json',dict(pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat()))
        grid.atomic_json(ROOT/'progress.json',dict(status='VERIFYING_FROZEN_INPUTS',completed_runs=0,total_runs=1))
        tape=cycle.BASE_TAPE(cycle.INPUT_ROOT)
        folder=ROOT/'cases'/ARM;folder.mkdir(parents=True)
        signals=tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
        prior=max(d for d in tape.schedule if d<cfg.start_date)
        signals=signals[signals.trade_date.ge(pd.Timestamp(prior))];signals['side']='long'
        def progress(done,total,day):
            elapsed=time.monotonic()-started
            grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',completed_runs=0,total_runs=1,
                completed_sessions=done,total_sessions=total,last_date=str(day),elapsed_seconds=elapsed,
                estimated_remaining_seconds=elapsed*(total-done)/done,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
        with hybrid_scope(folder):
            with grid.runtime_adapter(2020,ARM),study.capacity.corrected_runtime(),cycle.repair.campaign_adapter(
                    cfg.exec_config,select_phase) as metadata:
                result=base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
                    high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
                    sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
                    winner_progress=progress,winner_corporate_actions=tape.actions.to_dict('records'))
            grid.atomic_json(ROOT/'progress.json',dict(status='AUDITING',completed_runs=0,total_runs=1))
            summary=grid.metrics(result,4000.);checks=audit(result,summary,metadata,tape)
        if summary['status']!='COMPLETED_EXPLORATORY' or summary['coverage_gaps']:raise ValueError('Incomplete replay')
        summary['outer_admission_policy']=summary.pop('policy')
        summary.update(arm=ARM,start=protocol['start'],end=protocol['end'],currency='USD',minimum_notional=70.,
            initial_equity=4000.,audit=checks,annual=runner.shared.control_audit.annual_rows(result,4000.))
        for name,frame in [('trades',result.closed_trades_df),('equity-5m',result.intraday_equity_curve),
                ('breaker-5m',result.drawdown_breaker_df)]:frame.to_parquet(folder/(name+'.parquet'),index=False)
        result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
        result.trade_events_df.to_csv(folder/'events.csv',index=False)
        grid.atomic_json(folder/'campaign-policies.json',metadata)
        summary['files']={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()}
        base.verify(protocol['sources']);base.save_new(folder/'report.json',summary)
        base.save_new(ROOT/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',case=summary,sources=protocol['sources'],
            files={str(folder/n):h for n,h in summary['files'].items()},full_live_parity=False,
            independent_holdout=False,future_coverage_selection_bias=True))
        consolidate(summary,protocol)
        grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=1,total_runs=1))


def main():
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('HTTP forbidden in restartSL1 replay'))
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    try:run()
    except BaseException as exc:
        if ROOT.exists():grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
