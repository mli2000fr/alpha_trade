"""Versioned offline monthly replay: native soft DD15/half and hard global DD25.

Reuse the sealed predecessor input tape without SQL, provider or broker calls.
The six shadows and four study accounts all follow the same new loss policy.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import copy, deepcopy
from dataclasses import asdict, replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
import logging
import os
import shutil
import xml.etree.ElementTree as ET

import pandas as pd

from scripts.research import us_winner_monthly_selector_20261024 as study
from scripts.research import us_winner_monthly_scope_repair_20261024 as repair

ROOT=Path('artifacts/research/us_winner_monthly_selector/20261024-dd15-dd25-v2')
VARIANT='hard25'
ROOTS=dict(hard25=ROOT,cooldown20=Path('artifacts/research/us_winner_monthly_selector/20261024-dd15-cycle20-pause3m-global25-v2'))
PRIOR=Path('artifacts/research/us_winner_monthly_selector/20261024-v1')
BACKUP=Path('artifacts/research/us_winner_monthly_selector/20261024-dd15-full-v2/predecessor')
DOC=Path('doc/ml/winner_monthly_dd15_dd25_20261024.md')
TEST=Path('tests/test_us_winner_monthly_drawdown_20261024.py')
TEST_RECEIPT=Path('artifacts/test_tmp/winner-dd15-cycle20-global25-20261024.xml')
SOFT=.15
HARD=.25
FRACTION=.5
BASE_CONFIGURATION=study.configuration
BASE_AUDIT=study.audit
BASE_TAPE=study.inputs.Tape
CURRENT_FOLDER=None


def configuration(protocol,start):
    cfg=BASE_CONFIGURATION(protocol,start)
    risk=replace(cfg.risk_config,max_portfolio_drawdown_pct=SOFT,
        force_close_on_breaker=True,force_close_pct=FRACTION,rolling_peak_window_days=0)
    return replace(cfg,risk_config=risk,
        exec_config=replace(cfg.exec_config,force_close_on_breaker=True,force_close_pct=FRACTION),
        winner_global_drawdown_halt=False,winner_hard_drawdown_pct=HARD,
        winner_cycle_drawdown_pct=.20 if VARIANT=='cooldown20' else None,
        winner_drawdown_cooldown_months=3 if VARIANT=='cooldown20' else 0)


def prepare(*,seal=True):
    base=study.capacity.grid.base
    path=ROOT/'protocol.json'
    if path.exists():
        p=study.capacity.read_json(path);base.verify(p['sources'])
        if p['variant']!=VARIANT:raise ValueError('Variant/run folder mismatch')
        return p
    old=study.capacity.read_json(PRIOR/'protocol.json')
    suites=ET.parse(TEST_RECEIPT).getroot().findall('.//testsuite')
    tests=sum(int(s.attrib.get('tests',0)) for s in suites)
    failures=sum(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0)) for s in suites)
    if tests<180 or failures:raise ValueError('Passing full qualification test receipt required')
    qualified_tests=TEST_RECEIPT
    if seal:
        ROOT.mkdir(parents=True,exist_ok=True)
        qualified_tests=ROOT/'qualification-tests.xml'
        if qualified_tests.exists():
            base.verify({str(qualified_tests):base.digest(TEST_RECEIPT)})
        else:
            shutil.copy2(TEST_RECEIPT,qualified_tests)
    receipt=study.capacity.read_json(BACKUP/'receipt.json')
    if not receipt['original_sources_verified'] or base.digest(PRIOR/'protocol.json')!=receipt['prior_protocol_sha256']:
        raise ValueError('Predecessor proof changed')
    amendments={}
    permitted={'backtesting/simulator.py','backtesting/winner_intraday.py'}
    sources={}
    for name,original in old['sources'].items():
        current=base.digest(name)
        if current!=original:
            rel=Path(name).resolve().relative_to(Path.cwd().resolve())
            if rel.as_posix() not in permitted or base.digest(BACKUP/'sources'/rel)!=original:
                raise ValueError('Unexpected predecessor source change: '+name)
            amendments[name]=dict(before=original,after=current,backup=str(BACKUP/'sources'/rel))
        sources[name]=current
    paths=[Path(__file__),DOC,TEST,Path('backtesting/winner_global_liquidation.py'),
        Path('tests/test_winner_global_liquidation.py'),Path(repair.__file__),
        Path('tests/test_us_winner_monthly_scope_repair_20261024.py'),
        Path('scripts/research/us_winner_stop_for_force_close_20261024.py'),
        Path('artifacts/operations/winner-force-close-stop-20261024-v1/report.json'),
        PRIOR/'protocol.json',PRIOR/'inputs/manifest.json',BACKUP/'receipt.json',qualified_tests]
    sources.update({str(n):base.digest(n) for n in paths})
    p=deepcopy(old)
    p.update(experiment='TOP20_MONTHLY_MTM_DD15_HALF_DD25_HARD_2020_2024',variant=VARIANT,sources=sources,
        predecessor=str(PRIOR),predecessor_sha256=base.digest(PRIOR/'protocol.json'),
        predecessor_source_amendments=amendments,arms=study.ARMS,
        half_position=False,annual_reset=False,economic_rules_changed=True,
        global_liquidation=dict(soft_drawdown_pct=SOFT,soft_close_fraction=FRACTION,
            soft_selection='Worst unrealized dollar PnL; whole positions; native rounded count',
            soft_rearm='Native B4 episode recovery; no liquidation repeated every five-minute bar',
            hard_drawdown_pct=HARD,hard_close_fraction=1.,hard_rearm='NONE_UNTIL_END_OF_RUN',
            cycle_drawdown_pct=.20 if VARIANT=='cooldown20' else None,
            cooldown_calendar_months=3 if VARIANT=='cooldown20' else 0,
            cycle_rearm='First official open on/after NY liquidation date + 3 calendar months; latest prior-session signal only',
            cycle_risk_reset='B4 episode and cycle peak reset to remaining equity; global25 peak NEVER reset',
            reference='Historical high-watermark of observed portfolio equity including open holdings',
            peak_reset=False,execution='Next observed regular 5m open after known mark; standing stops/MOO first',
            gaps_can_exceed_threshold=True),
        effective_initial_fraction=1.,effective_max_positions=20,effective_gross_cap=1.,
        validation_tests=tests,test_receipt=str(qualified_tests),
        input_policy='Exact sealed predecessor snapshots; no SQL reads or writes; no download',
        data_relaxation='None in this amendment; predecessor common future coverage40 retained',
        SQL_reads=0,SQL_writes=False,provider_calls=0,broker_calls=0,
        production_changed=False,production_yaml_changed=False,no_training=True,
        notes=['Ten independent accounts; 4000 USD each, no monthly/annual capital reset.',
            'Six shadows start July 2019; two adaptive and two fixed controls start January 2020.',
            'Frozen profiles, fees, original TOP20 ranks and candidate coverage unchanged.',
            '50% means rounded count of whole worst positions, not 50% of each holding.',
            'Historical hard25 prevents unlimited continuation; it is not a guaranteed fill floor.'],
        limitations=['Exploratory previously inspected periods, not an independent holdout.',
            'Survivor universe, current non-PIT sectors and future coverage/CA selection bias.',
            '5m OHLC with deterministic fills and 8bps per leg, not historical bid/ask or actual fills.',
            'Hard-stop account stays cash until end; shadow profiles can therefore become flat.',
            'Reported legacy DD uses 5m closing curve; risk-observed DD includes opening marks too.',
            'Original corporate-action completeness limitations remain; no full-live-parity claim.'])
    cfg=configuration(p,study.inputs.START)
    p['effective_risk_config']=asdict(cfg.risk_config)
    ROOT.mkdir(parents=True,exist_ok=True)
    if seal:base.save_new(path,p)
    return p


def archived_inputs(_root):
    manifest=study.capacity.read_json(PRIOR/'inputs/manifest.json')
    study.capacity.grid.base.verify({str(PRIOR/'inputs'/n):h for n,h in manifest['files'].items()})
    return manifest


def audit(result,summary,metadata,tape):
    """Independent scalar normal exits plus journaled causal global sales."""
    info=summary['global_liquidation']
    if (not info['enabled'] or info['threshold_pct']!=SOFT or info['force_close_pct']!=FRACTION
            or info['hard_threshold_pct']!=HARD or info['pending'] is not None
            or info.get('cycle_threshold_pct')!=(.20 if VARIANT=='cooldown20' else None)
            or info.get('cooldown_months',0)!=(3 if VARIANT=='cooldown20' else 0)):
        raise ValueError('Unqualified/incomplete global drawdown policy or pending final sale')
    trades=result.closed_trades_df
    global_trades=trades[trades.exit_reason.eq('GLOBAL_DRAWDOWN')] if len(trades) else trades
    ordinary=copy(result)
    ordinary.closed_trades_df=trades[~trades.exit_reason.eq('GLOBAL_DRAWDOWN')] if len(trades) else trades
    checks=BASE_AUDIT(ordinary,summary,metadata,tape)
    study.capacity.audit_held_coverage(result,summary['coverage_gaps'],study.inputs.END)
    events=result.trade_events_df
    buys=events[events.event.eq('BUY_FILL')]
    expected={};exit_events={}
    for event in info['events']:
        stamp=pd.Timestamp(event['executed_at']);detected=pd.Timestamp(event['detected_at'])
        if stamp<detected:
            raise ValueError('Retroactive drawdown sale')
        threshold=HARD if event['reason']=='HARD_DRAWDOWN' else .20 if event['reason']=='CYCLE_DRAWDOWN' else SOFT
        if event['threshold_pct']!=threshold or event['force_close_pct']!=(FRACTION if threshold==SOFT else 1.):
            raise ValueError('Global drawdown event policy drift')
        if event['equity_at_detection']>event.get('reference_peak_at_detection',event['peak_at_detection'])*(1-threshold)+1e-7:
            raise ValueError('Premature global drawdown trigger')
        if threshold==HARD and (buys.time.map(lambda t:pd.Timestamp(t)>=detected)).any():
            raise ValueError('New buy after terminal hard stop')
        if threshold==.20:
            due=(stamp.tz_convert('America/New_York').normalize()+pd.DateOffset(months=3))
            if pd.Timestamp(event['paused_until'])!=due:
                raise ValueError('Cooldown is not three calendar months from liquidation date')
            resumes=[r for r in info['resumes'] if r['cycle']==event['cycle']+1]
            resume=pd.Timestamp(resumes[0]['resumed_at']) if resumes else None
            during=buys.time.map(lambda t:pd.Timestamp(t)>=detected and (resume is None or pd.Timestamp(t)<resume))
            if during.any():raise ValueError('Buy during cooldown')
            if resumes:
                expected_open=next(s.open_at_utc for s in study.capacity.grid.calendar().sessions(
                    due.date(),due.date()+timedelta(days=10)) if s.is_open)
                if resume!=pd.Timestamp(expected_open):raise ValueError('Resume not at first eligible official opening')
                study.near(resumes[0]['global_peak'],event['peak_at_detection'])
                study.near(resumes[0]['equity'],event['equity_after'])
        for symbol,quantity in event['quantities'].items():
            if quantity:
                expected[symbol,stamp]=expected.get((symbol,stamp),0)+quantity
                exit_events[symbol,stamp]=event
    actual={}
    for t in global_trades.itertuples():
        entry,exit_=pd.Timestamp(t.entry_date),pd.Timestamp(t.exit_date)
        day=exit_.tz_convert('America/New_York').date()
        f=tape.day(t.symbol,day)
        bar=f[f.bar_timestamp.eq(exit_)]
        if len(bar)!=1:
            raise ValueError('Global sale does not use a qualified opening print')
        event=exit_events.get((t.symbol,exit_))
        if event is None:raise ValueError('Global sale has no triggering event')
        eligible=tape.path(t.symbol,pd.Timestamp(event['detected_at']),exit_)
        if eligible.empty or eligible.bar_timestamp.min()!=exit_:
            raise ValueError('Global sale delayed beyond the first available regular opening')
        study.near(t.exit_price,bar.iloc[0].open)
        study.near(t.entry_fees,t.entry_price*t.quantity*.0008)
        study.near(t.exit_fees,t.exit_price*t.quantity*.0008)
        study.near(t.pnl,t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends)
        item=metadata[t.campaign_id];policy=item['policy']
        entry_day=entry.tz_convert('America/New_York').date()
        schedule=[s for s in study.capacity.grid.calendar().sessions(entry_day,entry_day+timedelta(days=100)) if s.is_open]
        due=pd.Timestamp(schedule[policy['horizon_sessions']].open_at_utc)
        path=tape.path(t.symbol,entry,exit_)
        # Exclude the exit bar: its high/low are not known at the market sale.
        prior=path[path.bar_timestamp.lt(exit_)]
        got=study.scalar_exit(prior,entry,t.entry_price,due,
            sl=policy['stop_loss_pct'],tp=policy['take_profit_pct'],trail=policy['trailing_stop_pct'])
        if got is not None:
            raise ValueError('A prior ordinary exit should have closed globally sold holding: '+str((t.symbol,got)))
        actual[t.symbol,exit_]=actual.get((t.symbol,exit_),0)+t.quantity
    if actual!=expected:
        raise ValueError('Global journal/trade quantity mismatch')
    if info['halted']:
        if summary['open_positions'] or summary['gross'] or summary['unsettled_cash']:
            raise ValueError('Hard stop did not leave a flat settled account')
        hard=next(e for e in info['events'] if e['reason']=='HARD_DRAWDOWN')
        # The previous bar close and the next bar open share a timestamp;
        # the closing mark at that instant precedes this opening execution.
        later=result.intraday_equity_curve[result.intraday_equity_curve.timestamp.gt(pd.Timestamp(hard['executed_at']))]
        if later.gross.ne(0).any() or later.equity.max()-later.equity.min()>1e-7:
            raise ValueError('Account not flat after terminal hard stop')
    if CURRENT_FOLDER is not None:
        result.drawdown_breaker_df.to_parquet(CURRENT_FOLDER/'breaker-5m.parquet',index=False)
    hard_events=[e for e in info['events'] if e['reason']=='HARD_DRAWDOWN']
    summary.update(global_risk_observed_dd_pct=info['max_observed_drawdown_pct'],
        global_soft_liquidations=sum(e['reason']=='SOFT_DRAWDOWN' for e in info['events']),
        cycle_liquidations=sum(e['reason']=='CYCLE_DRAWDOWN' for e in info['events']),
        resumed_cycles=len(info['resumes']),hard_drawdown_halted=info['halted'],
        hard_stop_detected_at=hard_events[0]['detected_at'] if hard_events else None,variant=VARIANT)
    return dict(checks,status='PASS_SCALAR_AND_CAUSAL_GLOBAL_DD_CASH_FEES_ENTRIES',
        normal_exit_checks=checks['exits'],global_exit_checks=len(global_trades),
        global_events=len(info['events']),hard_halted=info['halted'])


@contextmanager
def installed():
    originals=(study.ROOT,study.configuration,study.campaign_adapter,study.prepare,
        study.audit,study.inputs.prepare,study.inputs.Tape,study.run_case)
    original_case=study.run_case
    def run_case(*args,**kwargs):
        global CURRENT_FOLDER
        CURRENT_FOLDER=ROOT/'cases'/args[1]
        try:
            return original_case(*args,**kwargs)
        finally:
            CURRENT_FOLDER=None
    study.ROOT=ROOT;study.configuration=configuration;study.campaign_adapter=repair.campaign_adapter
    study.prepare=prepare;study.audit=audit;study.inputs.prepare=archived_inputs
    study.inputs.Tape=lambda _root:BASE_TAPE(PRIOR)
    study.run_case=run_case
    try:
        yield
    finally:
        (study.ROOT,study.configuration,study.campaign_adapter,study.prepare,study.audit,
            study.inputs.prepare,study.inputs.Tape,study.run_case)=originals


def smoke(sessions=20):
    """Real sealed inputs, bounded replay. Never count this as a completed arm."""
    global CURRENT_FOLDER
    p=prepare(seal=False);archived_inputs(ROOT)
    tape=BASE_TAPE(PRIOR)
    days=[s.session_date for s in study.inputs.sessions() if study.inputs.SHADOW_START<=s.session_date<=study.inputs.END]
    end=days[sessions-1]
    cfg=replace(configuration(p,days[0]),end_date=end)
    signals=tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
    signals['side']='long'
    folder=ROOT/f'smoke-{sessions}';folder.mkdir(parents=True,exist_ok=True)
    CURRENT_FOLDER=folder
    try:
        with study.capacity.grid.runtime_adapter(2019,'DD15_DD25_SMOKE'),study.capacity.corrected_runtime(),repair.campaign_adapter(cfg.exec_config,lambda _d:study.REFERENCE) as metadata:
            result=study.capacity.grid.base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
                high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
                sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
                winner_corporate_actions=tape.actions.to_dict('records'))
        summary=study.capacity.grid.metrics(result,4000.)
        # Coverage audit end is the bounded smoke end, not the final study date.
        prior_end=study.inputs.END;study.inputs.END=end
        try:
            checks=audit(result,summary,metadata,tape)
        finally:
            study.inputs.END=prior_end
        study.capacity.grid.atomic_json(folder/'report.json',dict(status='PASS_BOUNDED_REAL_INPUT_SMOKE',
            sessions=sessions,end=str(end),audit=checks,summary=summary,completed_study_arms=0))
    finally:
        CURRENT_FOLDER=None


def main():
    global VARIANT,ROOT
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','smoke','run'],default='run')
    parser.add_argument('--smoke-sessions',type=int,default=20)
    parser.add_argument('--variant',choices=list(ROOTS),default='hard25')
    args=parser.parse_args()
    VARIANT=args.variant;ROOT=ROOTS[VARIANT]
    os.environ['SSLKEYLOGFILE']=''
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    import requests
    def forbidden(*_a,**_k):
        raise RuntimeError('No provider/broker/LLM HTTP calls in offline DD study')
    requests.Session.request=forbidden
    with installed():
        if args.phase=='prepare':prepare()
        elif args.phase=='smoke':smoke(args.smoke_sessions)
        else:study.run()


if __name__=='__main__':main()
