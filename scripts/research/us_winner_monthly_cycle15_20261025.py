"""Offline TOP20 monthly replay: liquidate at cycle DD15, pause 3m, no hard cap.

Isolated controller adapter; never edit the sealed original engines or studies.
Six new shadows and four accounts use exactly the same amended risk policy.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import logging
import math
import os
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pandas as pd

from backtesting.winner_global_liquidation import GlobalLiquidation as OriginalLiquidation
from scripts.research import us_winner_monthly_drawdown_20261024 as previous

study, repair = previous.study, previous.repair
ROOT = Path('artifacts/research/us_winner_monthly_selector/20261025-cycle15-pause3m-no-global-cap-v1')
PARENT = previous.ROOTS['cooldown20']
INPUT_ROOT = previous.PRIOR
DOC = Path('doc/ml/winner_monthly_cycle15_pause3m_20261025.md')
TEST = Path('tests/test_us_winner_monthly_cycle15_20261025.py')
TEST_RECEIPT = Path('artifacts/tests/winner-cycle15-20261025/qualification.xml')
THRESHOLD, MONTHS = .15, 3
BASE_CONFIGURATION = study.configuration
BASE_AUDIT = study.audit
BASE_TAPE = study.inputs.Tape
CURRENT_FOLDER = None


class CycleOnlyLiquidation(OriginalLiquidation):
    """Reuse causal sales/cancellation, without soft-half or historical halt."""
    def __init__(self, cfg, risk, execution):
        if (cfg.winner_global_drawdown_halt or cfg.winner_hard_drawdown_pct is not None
                or cfg.winner_cycle_drawdown_pct != THRESHOLD
                or cfg.winner_drawdown_cooldown_months != MONTHS
                or risk.max_portfolio_drawdown_pct != THRESHOLD
                or not risk.force_close_on_breaker or risk.force_close_pct != 1.
                or not execution.force_close_on_breaker or execution.force_close_pct != 1.):
            raise ValueError('Explicit cycle15/full liquidation/three months/no hard cap required')
        # Original constructor does not permit a cycle without a hard cap. Seed
        # its ordinary state with BOTH optional policies absent, then configure
        # the explicitly validated research-only cycle. No synthetic .999 cap.
        plain = replace(cfg,winner_cycle_drawdown_pct=None,winner_drawdown_cooldown_months=0)
        super().__init__(plain,risk,execution)
        self.cycle_threshold, self.cooldown_months = THRESHOLD, MONTHS

    def observe(self, stamp, equity, book, evaluated):
        # Original cycle branch is causal and precedes soft B4. Suppress ONLY
        # its partial-soft branch: the new rule is total liquidation on the
        # observed cycle peak, never an extra native-episode partial sale.
        observed = dict(evaluated,circuit_breaker=SimpleNamespace(just_tripped=lambda:False))
        result = super().observe(stamp,equity,book,observed)
        if self.pending is not None:
            self.pending['cycle_drawdown_at_detection_pct'] = 100*(
                self.pending['equity_at_detection']/self.pending['reference_peak_at_detection']-1)
            self.pending['lifetime_drawdown_at_detection_pct'] = self.pending['drawdown_at_detection_pct']
        return result

    def resume(self, stamp, book):
        if (self.halted or not self.cycle_stopped or self.pending is not None
                or self.paused_until is None or stamp < self.paused_until):
            return False
        if book.positions():
            raise ValueError('Cannot resume before full liquidation')
        equity = book.equity()
        if not math.isfinite(equity) or equity <= 0:
            raise ValueError('Positive remaining equity required; never recapitalize')
        self.cycle += 1
        self.cycle_peak, self.cycle_stopped = equity, False
        self.resumes.append(dict(cycle=self.cycle,resumed_at=stamp.isoformat(),equity=equity,
            global_peak=self.peak,previous_paused_until=self.paused_until.isoformat()))
        self.paused_until = None
        book.events.append(dict(time=stamp,event='GLOBAL_DD_RESUME',cycle=self.cycle,equity=equity))
        return True

    def summary(self):
        return dict(super().summary(),rearm='CYCLE_CALENDAR_COOLDOWN_NO_GLOBAL_HARD_CAP',
            historical_peak_diagnostic_only=True,reset_deposits=0,
            risk_reset='Native cycle B4 state is re-seeded by the replay at actual remaining equity')


def configuration(protocol, start):
    cfg = BASE_CONFIGURATION(protocol,start)
    risk = replace(cfg.risk_config,max_portfolio_drawdown_pct=THRESHOLD,
        force_close_on_breaker=True,force_close_pct=1.,rolling_peak_window_days=0)
    return replace(cfg,risk_config=risk,
        exec_config=replace(cfg.exec_config,force_close_on_breaker=True,force_close_pct=1.),
        winner_global_drawdown_halt=False,winner_hard_drawdown_pct=None,
        winner_cycle_drawdown_pct=THRESHOLD,winner_drawdown_cooldown_months=MONTHS)


def prepare():
    base = study.capacity.grid.base
    if (ROOT/'protocol.json').exists():
        protocol = base.read(ROOT/'protocol.json'); base.verify(protocol['sources']); return protocol
    parent = base.read(PARENT/'protocol.json'); base.verify(parent['sources'])
    finished = base.read(PARENT/'report.json')
    if finished['status'] != 'COMPLETED_AUDITED_EXPLORATORY':
        raise ValueError('Expected completed predecessor')
    suites = ET.parse(TEST_RECEIPT).getroot().findall('.//testsuite')
    count = sum(int(s.attrib.get('tests',0)) for s in suites)
    errors = sum(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0))+int(s.attrib.get('skipped',0)) for s in suites)
    if count < 60 or errors:
        raise ValueError('Passing full cycle policy/engine/audit test receipt required')
    sources = dict(parent['sources'])
    for path in [Path(__file__),DOC,TEST,TEST_RECEIPT,PARENT/'protocol.json',PARENT/'report.json']:
        sources[str(path)] = base.digest(path)
    protocol = deepcopy(parent)
    protocol.update(experiment='TOP20_MONTHLY_CYCLE_DD15_PAUSE3M_NO_HARD_CAP',
        created_at_utc=datetime.now(timezone.utc).isoformat(),variant='cycle15_no_hard',sources=sources,
        predecessor=str(PARENT),predecessor_sha256=base.digest(PARENT/'protocol.json'),
        arms=list(study.ARMS),validation_tests=count,
        global_liquidation=dict(cycle_drawdown_pct=THRESHOLD,total_liquidation=True,
            soft_partial_liquidation=False,hard_drawdown_pct=None,cooldown_calendar_months=MONTHS,
            reference='Observed cycle equity peak, including open positions; reset at actual remaining cash on resume',
            global_peak='Tracked for lifetime drawdown reporting only; never blocks recovery',
            resume='First official opening on/after NY actual liquidation date plus three calendar months',
            signals='Cancel pre-pause plans; re-admit only latest previous-session signal and new subsequent signals',
            risk_reset='Native B4 cycle episode and cycle peak re-seeded on resume; concentration history retained',
            recapitalization=False,partial_reset_of_money=False,gaps_can_exceed_threshold=True),
        same_input_root=str(INPUT_ROOT),effective_gross_cap=1.,effective_initial_fraction=1.,
        effective_risk_config=asdict(configuration(parent,study.inputs.START).risk_config),
        effective_execution_config=asdict(configuration(parent,study.inputs.START).exec_config),
        reference_config=parent['reference_config'],
        SQL_reads=0,SQL_writes=False,provider_calls=0,broker_calls=0,LLM_calls=0,orders=False,
        production_changed=False,production_yaml_changed=False,original_engine_sources_modified=False,
        no_training=True,independent_holdout=False,full_live_parity=False,
        notes=['Ten independent accounts with 4000 USD each; no monthly or annual capital reset.',
            'Six shadows July2019-Dec2024, monthly30/monthly50 and two fixed controls Jan2020-Dec2024.',
            'All ten accounts use this same new cycle policy; recompute shadows before monthly choices.',
            'Repeated 15% cycle losses can compound to lifetime losses well beyond 25%.'],
        limitations=['Exploratory previously inspected periods, not independent holdout.',
            'Survivor universe, current non-PIT sectors and future J..J+40 coverage selection bias.',
            'Deterministic OHLC 5m fills and 8bps per leg, not certified historical quotes/fills.',
            'Lifetime DD and cycle DD must both be reported; reset never erases economic losses.',
            'Cycle control sees opening and completed-close marks, not intrabar future extrema.'])
    ROOT.mkdir(parents=True,exist_ok=False)
    base.save_new(ROOT/'protocol.json',protocol)
    study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=10))
    return protocol


def audit(result, summary, metadata, tape):
    """Independent normal exits plus causal full sales, pauses and reset dates."""
    info = summary['global_liquidation']
    if (not info['enabled'] or info['threshold_pct'] != THRESHOLD or info['force_close_pct'] != 1.
            or info['hard_threshold_pct'] is not None or info['cycle_threshold_pct'] != THRESHOLD
            or info['cooldown_months'] != MONTHS or info['historical_peak_halt'] or info['halted']
            or info['pending'] is not None or info['rearm'] != 'CYCLE_CALENDAR_COOLDOWN_NO_GLOBAL_HARD_CAP'):
        raise ValueError('Wrong or incomplete cycle-only liquidation contract')
    events = result.trade_events_df
    buys = events[events.event.eq('BUY_FILL')]
    trades = result.closed_trades_df
    global_trades = trades[trades.exit_reason.eq('GLOBAL_DRAWDOWN')] if len(trades) else trades
    ordinary = copy(result)
    ordinary.closed_trades_df = trades[~trades.exit_reason.eq('GLOBAL_DRAWDOWN')] if len(trades) else trades
    checks = BASE_AUDIT(ordinary,summary,metadata,tape)
    study.capacity.audit_held_coverage(result,summary['coverage_gaps'],study.inputs.END)
    expected, triggering = {}, {}
    used_resumes = set()
    last_cycle, prior_resume = 0, None
    for event in info['events']:
        detected, stamp = pd.Timestamp(event['detected_at']),pd.Timestamp(event['executed_at'])
        if (event['reason'] != 'CYCLE_DRAWDOWN' or event['threshold_pct'] != THRESHOLD
                or event['force_close_pct'] != 1. or stamp < detected or event['cycle'] != last_cycle+1):
            raise ValueError('Wrong trigger, duplicate cycle or retroactive liquidation')
        if prior_resume is not None and detected < prior_resume:
            raise ValueError('Trigger precedes cycle resumption')
        reference = event['reference_peak_at_detection']
        if event['equity_at_detection'] > reference*(1-THRESHOLD)+1e-7:
            raise ValueError('Premature cycle liquidation')
        curve = result.intraday_equity_curve
        earlier = curve[pd.to_datetime(curve.timestamp,utc=True).le(detected)]
        if prior_resume is not None:
            earlier = earlier[pd.to_datetime(earlier.timestamp,utc=True).ge(prior_resume)]
        cycle_seed = summary['initial_equity'] if prior_resume is None else next(
            r['equity'] for r in info['resumes'] if r['cycle'] == event['cycle'])
        observed_close_peak = max([cycle_seed,*earlier.equity.tolist()])
        # Opening marks may exceed closing marks; never require equality to a
        # close-only peak and thereby invent missing intrabar information.
        if reference+1e-7 < observed_close_peak:
            raise ValueError('Cycle peak omits an already observed equity close')
        due = stamp.tz_convert('America/New_York').normalize()+pd.DateOffset(months=MONTHS)
        if pd.Timestamp(event['paused_until']) != due:
            raise ValueError('Pause is not three calendar months from execution')
        resumes = [r for r in info['resumes'] if r['cycle'] == event['cycle']+1]
        if len(resumes) > 1:
            raise ValueError('Duplicate resume')
        resume = pd.Timestamp(resumes[0]['resumed_at']) if resumes else None
        during = pd.to_datetime(buys.time,utc=True).map(lambda t:t >= detected and (resume is None or t < resume))
        if during.any():
            raise ValueError('New buy during liquidation/pause')
        first = next(s.open_at_utc for s in study.capacity.grid.calendar().sessions(due.date(),due.date()+timedelta(days=12)) if s.is_open)
        if resumes:
            if resume != pd.Timestamp(first):
                raise ValueError('Resume not at first eligible official open')
            study.near(resumes[0]['equity'],event['equity_after'])
            breaker = result.drawdown_breaker_df
            opening_state = breaker[pd.to_datetime(breaker.timestamp,utc=True).eq(resume)]
            if len(opening_state) != 1:
                raise ValueError('Missing native risk state at cycle resume')
            study.near(opening_state.iloc[0]['peak'],resumes[0]['equity'])
            if (opening_state.iloc[0]['cycle'] != resumes[0]['cycle']
                    or opening_state.iloc[0]['cycle_stopped']):
                raise ValueError('Native risk cycle was not rearmed')
            used_resumes.add(resumes[0]['cycle'])
        elif pd.Timestamp(first).tz_convert('America/New_York').date() <= study.inputs.END:
            raise ValueError('Eligible resume is missing')
        for symbol,quantity in event['quantities'].items():
            if quantity:
                expected[symbol,stamp] = expected.get((symbol,stamp),0)+quantity
                triggering[symbol,stamp] = event
        last_cycle,prior_resume = event['cycle'],resume
    if used_resumes != {r['cycle'] for r in info['resumes']}:
        raise ValueError('Resume has no prior liquidation')
    actual = {}
    for trade in global_trades.itertuples():
        stamp, entry = pd.Timestamp(trade.exit_date),pd.Timestamp(trade.entry_date)
        event = triggering.get((trade.symbol,stamp))
        if event is None:
            raise ValueError('Global sale has no event')
        frame = tape.day(trade.symbol,stamp.tz_convert('America/New_York').date())
        opening = frame[frame.bar_timestamp.eq(stamp)]
        if len(opening) != 1:
            raise ValueError('Global sale lacks opening print')
        first_available = tape.path(trade.symbol,pd.Timestamp(event['detected_at']),stamp)
        if first_available.empty or first_available.bar_timestamp.min() != stamp:
            raise ValueError('Global sale delayed beyond next observable opening')
        study.near(trade.exit_price,opening.iloc[0].open)
        study.near(trade.entry_fees,trade.quantity*trade.entry_price*.0008)
        study.near(trade.exit_fees,trade.quantity*trade.exit_price*.0008)
        study.near(trade.pnl,trade.quantity*(trade.exit_price-trade.entry_price)-trade.entry_fees-trade.exit_fees+trade.dividends)
        policy = metadata[trade.campaign_id]['policy']
        day = entry.tz_convert('America/New_York').date()
        schedule = [s for s in study.capacity.grid.calendar().sessions(day,day+timedelta(days=100)) if s.is_open]
        due = pd.Timestamp(schedule[policy['horizon_sessions']].open_at_utc)
        path = tape.path(trade.symbol,entry,stamp)
        normal = study.scalar_exit(path[path.bar_timestamp.lt(stamp)],entry,trade.entry_price,due,
            sl=policy['stop_loss_pct'],tp=policy['take_profit_pct'],trail=policy['trailing_stop_pct'])
        if normal is not None:
            raise ValueError('Normal exit predates global sale')
        actual[trade.symbol,stamp] = actual.get((trade.symbol,stamp),0)+trade.quantity
    if actual != expected:
        raise ValueError('Global sales/journal quantity mismatch')
    # Pause must be truly flat, not merely have no further buys. The closing
    # valuation at the SAME timestamp can precede the opening sale: exclude it.
    curve = result.intraday_equity_curve
    stamps = pd.to_datetime(curve.timestamp,utc=True)
    for event in info['events']:
        resume = next((pd.Timestamp(r['resumed_at']) for r in info['resumes'] if r['cycle'] == event['cycle']+1),None)
        paused = curve[stamps.gt(pd.Timestamp(event['executed_at'])) & (stamps.lt(resume) if resume is not None else True)]
        if paused.gross.ne(0).any() or (len(paused) and paused.equity.max()-paused.equity.min() > 1e-7):
            raise ValueError('Pause contains exposure, equity drift or hidden capital injection')
    if info['cycle_stopped'] and (summary['open_positions'] or summary['gross'] or summary['unsettled_cash']):
        raise ValueError('Final paused account is not fully flat')
    if CURRENT_FOLDER is not None:
        result.drawdown_breaker_df.to_parquet(CURRENT_FOLDER/'breaker-5m.parquet',index=False)
    summary.update(global_risk_observed_dd_pct=info['max_observed_drawdown_pct'],global_soft_liquidations=0,
        cycle_liquidations=len(info['events']),resumed_cycles=len(info['resumes']),hard_drawdown_halted=False,
        hard_stop_detected_at=None,variant='cycle15_no_hard',final_cycle_peak=info['cycle_peak'],
        final_cycle_drawdown_pct=100*(summary['final_equity']/info['cycle_peak']-1))
    per_session = curve.assign(session=stamps.dt.tz_convert('America/New_York').dt.date).groupby('session').gross.max()
    summary.update(sessions_with_exposure=int(per_session.gt(0).sum()),
        sessions_cash_only=int(per_session.eq(0).sum()),observed_sessions=len(per_session))
    return dict(checks,status='PASS_CYCLE15_FULL_SALES_PAUSES_RESETS_CASH_FEES_ENTRIES',
        global_exit_checks=len(global_trades),normal_exit_checks=checks['exits'],
        cycle_liquidations=len(info['events']),resumes=len(info['resumes']),hard_cap_absent=True)


@contextmanager
def installed():
    import backtesting.winner_global_liquidation as module
    old_controller = module.GlobalLiquidation
    names = (study.ROOT,study.configuration,study.campaign_adapter,study.prepare,study.audit,
             study.inputs.prepare,study.inputs.Tape,study.run_case)
    original_case = study.run_case

    def case(*args,**kwargs):
        global CURRENT_FOLDER
        CURRENT_FOLDER = ROOT/'cases'/args[1]
        try:
            return original_case(*args,**kwargs)
        finally:
            CURRENT_FOLDER = None

    module.GlobalLiquidation = CycleOnlyLiquidation
    study.ROOT,study.configuration,study.campaign_adapter = ROOT,configuration,repair.campaign_adapter
    study.prepare,study.audit = prepare,audit
    study.inputs.prepare = previous.archived_inputs
    study.inputs.Tape = lambda _root:BASE_TAPE(INPUT_ROOT)
    study.run_case = case
    try:
        yield
    finally:
        module.GlobalLiquidation = old_controller
        (study.ROOT,study.configuration,study.campaign_adapter,study.prepare,study.audit,
         study.inputs.prepare,study.inputs.Tape,study.run_case) = names


def smoke(session_count):
    global CURRENT_FOLDER
    protocol = prepare()
    tape = BASE_TAPE(INPUT_ROOT)
    sessions = [s for s in study.inputs.sessions() if study.inputs.SHADOW_START <= s.session_date <= study.inputs.END]
    end = sessions[session_count-1].session_date
    cfg = replace(configuration(protocol,study.inputs.SHADOW_START),end_date=end)
    signals = tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
    signals['side'] = 'long'
    folder = ROOT/f'smoke-{session_count}'
    folder.mkdir(parents=True,exist_ok=False)
    old_end = study.inputs.END
    with installed():
        try:
            CURRENT_FOLDER = folder
            study.inputs.END = end
            with study.capacity.grid.runtime_adapter(2019,'CYCLE15_SMOKE'),study.capacity.corrected_runtime(),repair.campaign_adapter(
                    cfg.exec_config,lambda _d:study.REFERENCE) as metadata:
                result = study.capacity.grid.base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
                    high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
                    sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
                    winner_corporate_actions=tape.actions.to_dict('records'))
            summary = study.capacity.grid.metrics(result,4000.)
            checks = audit(result,summary,metadata,tape)
            study.capacity.grid.base.save_new(folder/'report.json',dict(status='PASS_BOUNDED_REAL_INPUT_SMOKE',
                sessions=session_count,end=str(end),summary=summary,audit=checks,completed_study_arms=0))
        finally:
            study.inputs.END,CURRENT_FOLDER = old_end,None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','smoke','run'],default='run')
    parser.add_argument('--smoke-sessions',type=int,default=20)
    args = parser.parse_args()
    os.environ['SSLKEYLOGFILE'] = ''
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    import requests
    requests.Session.request = lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No HTTP in offline cycle15 study'))
    if args.phase == 'prepare':
        prepare()
    elif args.phase == 'smoke':
        smoke(args.smoke_sessions)
    else:
        with installed():
            study.run()


if __name__ == '__main__':
    main()
