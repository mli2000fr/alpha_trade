"""Change only the DD15/min70 cooldown from3months to20complete NYSE sessions."""
from contextlib import contextmanager
from copy import copy
from dataclasses import replace
from datetime import datetime,timedelta,timezone
import logging
import os
from pathlib import Path

import pandas as pd

from scripts.research import us_winner_cycle15_min70_20261025 as runner

cycle,study,grid,base=runner.cycle,runner.study,runner.grid,runner.base
ROOT=Path('artifacts/research/us_winner_cycle15_pause20_min70/20261026-v1')
PARENT=runner.ROOT
ARM='FIXED_SL5_MIN70_CYCLE15_PAUSE20SESSIONS'
DOC=Path('doc/ml/winner_cycle15_pause20_min70_protocole_20261026.md')
TEST=Path('tests/test_us_winner_cycle15_pause20_min70_20261026.py')
REARM='CYCLE_SESSION_COOLDOWN_NO_GLOBAL_HARD_CAP'
ORIGINAL_SCOPE=runner.shared.scope
ORIGINAL_WITH_CYCLE=runner.with_cycle


def pause_schedule(stamp,calendar,count=20):
    if type(count) is not int or count!=20:raise ValueError('Exactly20sessions required')
    day=pd.Timestamp(stamp).tz_convert('America/New_York').date()
    future=[s for s in calendar.sessions(day+timedelta(days=1),day+timedelta(days=100)) if s.is_open]
    if len(future)<count+1:raise ValueError('Incomplete official pause calendar')
    return future[:count],future[count]


class SessionCycle(cycle.CycleOnlyLiquidation):
    def __init__(self,cfg,risk,execution):
        if cfg.winner_drawdown_cooldown_months!=0:raise ValueError('No calendar-month transport allowed')
        # Existing constructor validates the original full-sale/cycle15 contract.
        # Its month count is constructor compatibility ONLY; effective state and
        # serialized configuration are0months/20sessions, never a hidden3m pause.
        super().__init__(replace(cfg,winner_drawdown_cooldown_months=3),risk,execution)
        self.cooldown_months=0;self.cooldown_sessions=20

    def execute(self,stamp,store,repo,book,execution):
        before=len(self.events)
        super().execute(stamp,store,repo,book,execution)
        if len(self.events)>before and self.events[-1]['reason']=='CYCLE_DRAWDOWN':
            paused,resume=pause_schedule(stamp,grid.calendar())
            self.paused_until=resume.open_at_utc
            self.events[-1].update(paused_until=self.paused_until.isoformat(),pause_sessions=20,
                pause_first_session=str(paused[0].session_date),pause_last_session=str(paused[-1].session_date),
                liquidation_day_excluded=True)

    def summary(self):
        return dict(super().summary(),cooldown_months=0,cooldown_sessions=20,rearm=REARM,
            pause_definition='20complete subsequent official sessions; resume at21st subsequent open')


def with_sessions(cfg):
    changed=ORIGINAL_WITH_CYCLE(cfg)
    return replace(changed,winner_drawdown_cooldown_months=0)


def session_audit(result,summary,metadata,tape):
    info=summary['global_liquidation']
    if (not info['enabled'] or info['threshold_pct']!=.15 or info['force_close_pct']!=1.
            or info['hard_threshold_pct'] is not None or info['cycle_threshold_pct']!=.15
            or info['cooldown_months']!=0 or info['cooldown_sessions']!=20 or info['historical_peak_halt']
            or info['halted'] or info['pending'] is not None or info['rearm']!=REARM):
        raise ValueError('Invalid20session liquidation contract')
    trades=result.closed_trades_df;global_trades=trades[trades.exit_reason.eq('GLOBAL_DRAWDOWN')]
    ordinary=copy(result);ordinary.closed_trades_df=trades[~trades.exit_reason.eq('GLOBAL_DRAWDOWN')]
    checks=runner.shared.explicit_normal_audit(ordinary,summary,metadata,tape)
    study.capacity.audit_held_coverage(result,summary['coverage_gaps'],study.inputs.END)
    events=result.trade_events_df;buys=events[events.event.eq('BUY_FILL')]
    curve=result.intraday_equity_curve;stamps=pd.to_datetime(curve.timestamp,utc=True)
    expected={};triggering={};used_resumes=set();previous_resume=None
    for index,event in enumerate(info['events'],start=1):
        detected,executed=pd.Timestamp(event['detected_at']),pd.Timestamp(event['executed_at'])
        if (event['reason']!='CYCLE_DRAWDOWN' or event['cycle']!=index or event['threshold_pct']!=.15
                or event['force_close_pct']!=1. or executed<detected):raise ValueError('Invalid trigger/order')
        if previous_resume is not None and detected<previous_resume:raise ValueError('Trigger inside pause')
        if event['equity_at_detection']>event['reference_peak_at_detection']*.85+1e-7:
            raise ValueError('Premature DD15 trigger')
        earlier=curve[stamps.le(detected)&(stamps.ge(previous_resume) if previous_resume is not None else True)]
        seed=summary['initial_equity'] if previous_resume is None else next(
            r['equity'] for r in info['resumes'] if r['cycle']==event['cycle'])
        if event['reference_peak_at_detection']+1e-7<max([seed,*earlier.equity.tolist()]):
            raise ValueError('Cycle peak omits observed closes')
        # Independently enumerate official dates; not a call to pause_schedule.
        day=executed.tz_convert('America/New_York').date()
        following=[s for s in grid.calendar().sessions(day,day+timedelta(days=100))
            if s.is_open and s.session_date>day]
        due=pd.Timestamp(following[20].open_at_utc)
        if (pd.Timestamp(event['paused_until'])!=due or event.get('pause_sessions')!=20
                or not event.get('liquidation_day_excluded')
                or event['pause_first_session']!=str(following[0].session_date)
                or event['pause_last_session']!=str(following[19].session_date)):
            raise ValueError('Not exactly20complete subsequent NYSE sessions')
        resumes=[r for r in info['resumes'] if r['cycle']==event['cycle']+1]
        if len(resumes)>1:raise ValueError('Duplicate resume')
        resume=pd.Timestamp(resumes[0]['resumed_at']) if resumes else None
        times=pd.to_datetime(buys.time,utc=True)
        if (times.ge(detected)&(times.lt(resume) if resume is not None else True)).any():
            raise ValueError('Buy during liquidation/pause')
        if resume is not None:
            if resume!=due:raise ValueError('Resume not at21st subsequent official open')
            study.near(resumes[0]['equity'],event['equity_after'])
            br=result.drawdown_breaker_df
            opening=br[pd.to_datetime(br.timestamp,utc=True).eq(resume)]
            if len(opening)!=1:raise ValueError('Missing B4 resume observation')
            study.near(opening.iloc[0]['peak'],resumes[0]['equity'])
            if opening.iloc[0]['cycle']!=resumes[0]['cycle'] or opening.iloc[0]['cycle_stopped']:
                raise ValueError('B4 not reset at remaining equity')
            used_resumes.add(resumes[0]['cycle'])
        elif due.tz_convert('America/New_York').date()<=study.inputs.END:
            raise ValueError('Missing eligible resume')
        for symbol,quantity in event['quantities'].items():
            if quantity:
                expected[symbol,executed]=expected.get((symbol,executed),0)+quantity
                triggering[symbol,executed]=event
        paused=curve[stamps.gt(executed)&(stamps.lt(resume) if resume is not None else True)]
        if paused.gross.ne(0).any() or (len(paused) and paused.equity.max()-paused.equity.min()>1e-7):
            raise ValueError('Pause not flat or hidden deposit')
        previous_resume=resume
    if used_resumes!={r['cycle'] for r in info['resumes']}:raise ValueError('Resume without liquidation')
    actual={}
    for trade in global_trades.itertuples():
        stamp,entry=pd.Timestamp(trade.exit_date),pd.Timestamp(trade.entry_date)
        event=triggering.get((trade.symbol,stamp))
        if event is None:raise ValueError('Global exit has no event')
        f=tape.day(trade.symbol,stamp.tz_convert('America/New_York').date())
        opening=f[f.bar_timestamp.eq(stamp)]
        if len(opening)!=1:raise ValueError('Global sale has no observed opening')
        observed=tape.path(trade.symbol,pd.Timestamp(event['detected_at']),stamp)
        if observed.empty or observed.bar_timestamp.min()!=stamp:raise ValueError('Delayed global exit')
        study.near(trade.exit_price,opening.iloc[0].open)
        study.near(trade.entry_fees,trade.quantity*trade.entry_price*.0008)
        study.near(trade.exit_fees,trade.quantity*trade.exit_price*.0008)
        study.near(trade.pnl,trade.quantity*(trade.exit_price-trade.entry_price)-trade.entry_fees-trade.exit_fees+trade.dividends)
        policy=metadata[trade.campaign_id]['policy'];day=entry.tz_convert('America/New_York').date()
        sessions=[s for s in grid.calendar().sessions(day,day+timedelta(days=100)) if s.is_open]
        path=tape.path(trade.symbol,entry,stamp)
        normal=study.scalar_exit(path[path.bar_timestamp.lt(stamp)],entry,trade.entry_price,
            pd.Timestamp(sessions[policy['horizon_sessions']].open_at_utc),sl=policy['stop_loss_pct'],
            tp=policy['take_profit_pct'],trail=policy['trailing_stop_pct'])
        if normal is not None:raise ValueError('Normal exit predates global exit')
        actual[trade.symbol,stamp]=actual.get((trade.symbol,stamp),0)+trade.quantity
    if actual!=expected:raise ValueError('Global exit quantities mismatch')
    if info['cycle_stopped'] and (summary['open_positions'] or summary['gross'] or summary['unsettled_cash']):
        raise ValueError('Final paused account still exposed')
    per_session=curve.assign(session=stamps.dt.tz_convert('America/New_York').dt.date).groupby('session').gross.max()
    summary.update(global_risk_observed_dd_pct=info['max_observed_drawdown_pct'],global_soft_liquidations=0,
        cycle_liquidations=len(info['events']),resumed_cycles=len(info['resumes']),hard_drawdown_halted=False,
        hard_stop_detected_at=None,variant='cycle15_pause20_sessions_no_hard',
        final_cycle_peak=info['cycle_peak'],final_cycle_drawdown_pct=100*(summary['final_equity']/info['cycle_peak']-1),
        sessions_with_exposure=int(per_session.gt(0).sum()),sessions_cash_only=int(per_session.eq(0).sum()),
        observed_sessions=len(per_session))
    return dict(checks,status='PASS_CYCLE15_PAUSE20_OFFICIAL_SESSIONS_CASH_FEES_ENTRIES',
        global_exit_checks=len(global_trades),normal_exit_checks=checks['exits'],
        cycle_liquidations=len(info['events']),resumes=len(info['resumes']),hard_cap_absent=True)


def prepare():
    prior=base.read(PARENT/'protocol.json');finished=base.read(PARENT/'report.json')
    base.verify(prior['sources']);base.verify(finished['files'])
    if finished['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Completed3month comparator required')
    original=ORIGINAL_WITH_CYCLE(runner.base_configuration(prior['control_protocol']))
    cfg=replace(original,winner_drawdown_cooldown_months=0)
    before,after=runner.normalized(original),runner.normalized(cfg)
    after['winner_drawdown_cooldown_months']=before['winner_drawdown_cooldown_months']
    if before!=after:raise ValueError('Non-pause configuration changed')
    sources=dict(prior['sources']);sources.update(finished['files'])
    for p in [PARENT/'protocol.json',PARENT/'report.json',PARENT/'control-bridge20/report.json',
            PARENT/'control-bridge20/equity-5m.parquet',Path(__file__),DOC,TEST,Path(runner.__file__)]:
        sources[str(p)]=base.digest(p)
    base.verify(sources)
    protocol=dict(prior,created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        after=runner.normalized(cfg),three_month_config=runner.normalized(original),pause_calendar_months=0,pause_official_sessions=20,
        pause_definition='Exclude liquidation date, skip next20complete NYSEsessions, resume21st subsequent open',
        changed_from_3month_control=['cooldown:3calendar_months ->20complete_subsequent_official_sessions'],
        three_month_control=finished['case'],engine_change='Same current engine; only research controller pause unit changes',
        bridge='Prior bounded20session disabled-engine bridge reused with unchanged sources, not rerun',
        no_new_production_fields=True)
    ROOT.mkdir(parents=True,exist_ok=False);base.save_new(ROOT/'protocol.json',protocol)
    grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol


def reuse_bridge(_parent,_tape):
    proof=base.read(PARENT/'control-bridge20/report.json')
    if proof['status']!='PASS_BOUNDED_CONTROL_BRIDGE':raise ValueError('Unqualified bridge')
    base.verify({str(PARENT/'control-bridge20'/n):h for n,h in proof['files'].items()})
    base.save_new(ROOT/'control-bridge-reused.json',dict(source=str(PARENT/'control-bridge20/report.json'),
        sha256=base.digest(PARENT/'control-bridge20/report.json'),bounded_sessions=20,whole_history_parity_claimed=False))


@contextmanager
def session_scope(folder):
    import backtesting.winner_global_liquidation as module
    with ORIGINAL_SCOPE(folder):
        original=module.GlobalLiquidation;module.GlobalLiquidation=SessionCycle
        try:yield
        finally:module.GlobalLiquidation=original


@contextmanager
def installed():
    old=(runner.ROOT,runner.ARM,runner.prepare,runner.with_cycle,runner.bridge,runner.shared.scope,cycle.audit)
    old_with_cycle=runner.with_cycle
    def cfg(base_cfg):return replace(old_with_cycle(base_cfg),winner_drawdown_cooldown_months=0)
    runner.ROOT,runner.ARM,runner.prepare,runner.with_cycle,runner.bridge=ROOT,ARM,prepare,cfg,reuse_bridge
    runner.shared.scope,cycle.audit=session_scope,session_audit
    try:yield
    finally:(runner.ROOT,runner.ARM,runner.prepare,runner.with_cycle,runner.bridge,runner.shared.scope,cycle.audit)=old


def consolidate():
    result=base.read(ROOT/'report.json');base.verify(result['sources']);base.verify(result['files'])
    prior=base.read(PARENT/'report.json');base.verify(prior['sources']);base.verify(prior['files'])
    cases=dict(NO_PAUSE=prior['comparator'],PAUSE_3_MONTHS=prior['case'],PAUSE_20_SESSIONS=result['case'])
    keys=['final_equity','return_pct','max_drawdown_pct','win_pct','closed_lot_trades','average_winning_pnl',
        'average_losing_pnl','average_gross_capital','average_gross_equity_ratio','costs']
    summary=[dict(variant=name,**{k:v[k] for k in keys}) for name,v in cases.items()]
    annual=[dict(variant=name,**r) for name,v in cases.items() for r in v['annual']]
    pd.DataFrame(summary).to_csv(ROOT/'comparison.csv',index=False)
    pd.DataFrame(annual).to_csv(ROOT/'annual-comparison.csv',index=False)
    base.save_new(ROOT/'comparison.json',dict(status='COMPLETED_AUDITED_EXPLORATORY_COMPARISON',
        cases=cases,summary=summary,annual=annual,independent_holdout=False,full_live_parity=False))


def main():
    os.environ.update(SSLKEYLOGFILE='',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1')
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('HTTP forbidden in pause20replay'))
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    try:
        with installed():runner.run()
        consolidate()
    except BaseException as exc:
        if ROOT.exists():grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':main()
