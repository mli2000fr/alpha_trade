"""1x grid with actual production B4/Checker components, no live mutation.

Current production protection settings applied retrospectively, NOT historical
config provenance or the complete historical PortfolioBuilder/broker pipeline.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import logging
import math
from pathlib import Path
import shutil
import time

import numpy as np
import pandas as pd

from backtesting.production_risk_replay import ProductionRiskController,force_close_selection
from backtesting.adaptive_breaker import B4_MONEY_ABS_TOL_USD,B4_MONEY_ULPS
from risk_management.constraints import PortfolioState
from risk_management.position_sizer import PositionSizer
from risk_management.risk_checker import RiskCheckerImpl
from scripts.research import us_intraday_protection_grid as base
from scripts.research.us_intraday_protection_grid_1x import OneXGridLedger
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

REFERENCE=Path('artifacts/research/us_intraday_protection_grid/20261021-1x-v1')
LEGACY_RISK=Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v1')
DEFAULT_OUTPUT=Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2')
REGRESSION_CASES={
    '2025-SHORT-SL5-TR15-H20-TP20','2025-SHORT-SL5-TR20-H10-TP10',
    '2025-SHORT-SL5-TROFF-H10-TP10','2025-SHORT-SL5-TROFF-H10-TP20'}
PROFILE=REGIMES=ACTIVE_OUTPUT=None
LOG=logging.getLogger(__name__)


class ProductionRiskGridLedger(OneXGridLedger):
    def __init__(self,calendar,**kwargs):
        super().__init__(calendar,**kwargs)
        if PROFILE is None or ACTIVE_OUTPUT is None:raise ValueError('Frozen research context required')
        self.guard=ProductionRiskController(PROFILE['guard_fields'])
        self.guard_events=[];self.allocation=1.;self.risk_day=None
        self.guard_output=ACTIVE_OUTPUT

    def begin_bar(self,timestamp,opening_marks,**kwargs):
        super().begin_bar(timestamp,opening_marks,**kwargs)
        if self.now!=self.calendar.at[self.day,'market_open']:return
        # Standing broker-style protections first, then global risk, then orders.
        self.resolve_open()
        context=REGIMES.get(self.day)
        if context is None or context['source_date']>=self.day:raise ValueError('Missing/uncausal SPY context')
        event=self.guard.evaluate(self.day,self.equity(),context['regime'])
        self.risk_day=self.day
        self.allocation=event['allocation_scale']
        held=[dict(symbol=s,quantity=p.quantity,side=p.side,entry_price=p.entry_price,
            entry_timestamp=self.live_meta[s]['entry_timestamp'],mark=self.prices[s]) for s,p in self.state.positions.items()]
        event.update(time=self.now,bar_number=self.bar_number,cash_before=self.state.settled_cash,
            held_before=held,regime_source_date=context['source_date'],forced_symbols=[])
        if event['just_tripped'] and PROFILE['force_close_enabled']:
            event['forced_symbols']=force_close_selection(held,PROFILE['force_close_fraction'])
            for s in event['forced_symbols']:
                self.close(s,self.prices[s],'PRODUCTION_BREAKER_FORCE',phase='OPEN')
        event['equity_after_forced']=self.equity()
        self.guard_events.append(event)

    def enter(self,symbol,side,price_info,**kwargs):
        if self.risk_day!=self.day:raise ValueError('Production guard not evaluated')
        eq=self.equity()
        cfg=self.risk.with_overrides(account_equity=eq,fixed_stop_pct=self.sl)
        price=self.prices[symbol]
        fee=self.engine._cost_model.per_leg_cost_pct
        full=min(math.floor(PositionSizer(cfg).compute(price_info).proposed_shares),
            math.floor(eq*cfg.max_position_weight/price),math.floor(self.buying_power()/(price*(1+fee))))
        fraction=kwargs.get('quantity_fraction',.5)*self.allocation
        planned=math.floor(full*fraction)
        state=PortfolioState()
        for s,p in self.state.positions.items():
            state.add_position(notional=p.quantity*self.prices[s],sector=p.sector,side=p.side,symbol=s)
        checker=RiskCheckerImpl(cfg,state=state,pnl=self.guard.pnl,circuit_breaker=self.guard.breaker)
        approved=int(checker.check_position_size(symbol,planned,price,side=side,
            adv_usd=price_info.adv_usd,selection_rank=kwargs.get('selection_rank')))
        if approved<=0:
            self.audit.append(dict(time=self.now,symbol=symbol,side=side,status='BLOCKED',
                reasons=['PRODUCTION_RISK:'+checker.get_last_decision_reason()],allocation_scale=self.allocation,
                full_quantity=full,scaled_proposal=planned,production_approved=approved))
            return False
        kwargs['quantity_fraction']=float(np.nextafter(approved/full,np.inf))
        opened=super().enter(symbol,side,price_info,**kwargs)
        self.audit[-1].update(allocation_scale=self.allocation,scaled_proposal=planned,production_approved=approved)
        if opened and self.state.positions[symbol].quantity!=approved:
            raise ValueError('Native booked quantity differs from production approval')
        return opened

    def finish_day(self):
        equity=super().finish_day()
        self.guard.finish(self.day,equity)
        self.guard_events[-1]['closing_equity']=equity
        if self.day==self.days[-1]:atomic_json(self.guard_output/'production-risk-events.json',self.guard_events)
        return equity


def prepare(root):
    root=Path(root)
    if root.resolve() in (REFERENCE.resolve(),LEGACY_RISK.resolve(),base.PARENT.resolve(),base.FIDELITY.resolve()):raise ValueError('Preserve sealed runs; use new risk-v2 output')
    if (root/'prepared.json').exists():
        verify_hashes(Path('.'),base.READ(root/'protocol.json')['sources'])
        verify_hashes(root,base.READ(root/'prepared.json')['files']);return
    if root.exists() and any(p.name!='run.lock' for p in root.iterdir()):raise ValueError('Fresh output required')
    old=base.READ(REFERENCE/'protocol.json');verify_hashes(Path('.'),old['sources'])
    review=base.READ(REFERENCE/'final-review.json');verify_hashes(REFERENCE,review['files'])
    if review['status']!='PASS_COMPLETED_1X_GRID_REVIEW':raise ValueError('1x reference not completed/audited')
    ready=base.READ(REFERENCE/'prepared.json');verify_hashes(REFERENCE,ready['files'])
    # Repair ONLY numeric decisions; do not silently reload/tune current YAML.
    legacy_protocol=base.READ(LEGACY_RISK/'protocol.json')
    legacy_ready=base.READ(LEGACY_RISK/'prepared.json')
    verify_hashes(LEGACY_RISK,legacy_ready['files'])
    archived=base.READ(LEGACY_RISK/'source-snapshot-manifest.json')
    if digest(LEGACY_RISK/'protocol.json')!=archived['original_protocol_sha256'] or digest(LEGACY_RISK/'report.json')!=archived['original_report_sha256']:
        raise ValueError('Pre-repair provenance changed')
    for row in archived['files']:
        if legacy_protocol['sources'][row['original_source']]!=row['sha256'] or digest(LEGACY_RISK/row['snapshot'])!=row['sha256']:
            raise ValueError('Original code snapshot mismatch')
    profile=base.READ(LEGACY_RISK/'production-risk.json')
    if profile['guard_fields']['policy']!='b4':raise ValueError('Original B4 risk profile required')
    names=[Path(__file__),Path('backtesting/production_risk_replay.py'),
        Path('scripts/research/us_intraday_protection_grid_risk_audit.py'),Path('tests/test_production_risk_replay.py'),
        Path('risk_management/circuit_breaker.py'),Path('risk_management/risk_checker.py'),
        Path('backtesting/adaptive_breaker.py'),Path('backtesting/regime_trailing.py'),
        Path('execution_engine/executor.py'),Path('risk_management/portfolio_builder.py'),
        Path('common/capital_presets.py'),Path('tests/test_b4_numeric_stability.py')]
    names += [REFERENCE/n for n in ['protocol.json','prepared.json','report.json','final-review.json']]
    names += [LEGACY_RISK/n for n in ['protocol.json','prepared.json','report.json','source-snapshot-manifest.json']]
    names += [LEGACY_RISK/row['snapshot'] for row in archived['files']]
    sources=dict(old['sources']);sources.update({str(n):digest(n) for n in names})
    protocol=dict(old)
    protocol.update(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,paired_reference=str(REFERENCE),
        production_risk=profile,variant='PRODUCTION_COMPONENTS_B4_REPLAY_NOT_FULL_LIVE',
        supersedes_partial_run=str(LEGACY_RISK),
        numeric_fix=dict(scope='B4/B4a monetary decisions only, no cash/fill/PnL rounding or audit relaxation',
            absolute_tolerance_usd=B4_MONEY_ABS_TOL_USD,ulp_multiplier=B4_MONEY_ULPS,
            unchanged='Same original frozen risk profile, regimes and base tapes. RerunALL576, never merge old572with repaired4.'),
        protected_layer='Actual production CircuitBreaker + RiskCheckerImpl, same native PositionSizer/ConstraintChecker. Allocation actually scales booked whole-share quantities;50%worst-position-count exits use observed opens and native costs/borrow.',
        evaluation='Once per NYSE session, observed regular OPEN after standing gap/TP/expiry guards; before entries. SPY regime computed only from previous NYSE close with complete200session history. Daily window counts sessions, not5m calls. No same-day future price/regime.',
        changed='Portfolio protection overlay only. Base1x target4%SL-risk/50%full thenHALF and research sector assumptions retained intentionally. Not all production preset sizing/sector/correlation/quotes/ML/data gates.',
        production_findings=['B4 is_active() is False:3%daily loss is a status, not an automatic hard halt. Log it without inventing extra rule.',
            'Examined Executor passage logs allocation_scale without sizing from it; this replay explicitly connects returned scale to quantities. It is not a claim of unchanged end-to-end live behavior.',
            'State persists across real sessions in replay. Daily assessments cannot promise a hard20%DD cap or intraday control. No live executor or state persistence changed.'],
        full_live_parity=False)
    root.mkdir(parents=True,exist_ok=True);atomic_json(root/'protocol.json',protocol)
    for name in legacy_ready['files']:shutil.copyfile(LEGACY_RISK/name,root/name)
    verify_hashes(root,legacy_ready['files'])
    atomic_json(root/'prepared.json',dict(files=legacy_ready['files'],base_inputs_identical_to=str(REFERENCE),
        all_inputs_identical_to=str(LEGACY_RISK),sessions=legacy_ready['sessions'],missing_regime=legacy_ready['missing_regime']))


def worker_init(root):
    global PROFILE,REGIMES
    logging.basicConfig(level=logging.ERROR,force=True)
    root=Path(root)
    PROFILE=base.READ(root/'production-risk.json')
    REGIMES={r.date:dict(source_date=r.source_date,regime=None if pd.isna(r.regime) else str(r.regime))
        for r in pd.read_parquet(root/'risk-regimes.parquet').itertuples()}
    base.CACHE=base.load_tapes(root);base.GridLedger=ProductionRiskGridLedger
    from scripts.research import us_intraday_protection_grid_audit as original_audit
    from scripts.research.us_intraday_protection_grid_risk_audit import audit_case
    original_audit.audit_case=audit_case


def worker_case(root,c):
    global ACTIVE_OUTPUT
    ACTIVE_OUTPUT=Path(root)/'cases'/base.case_key(c)
    return base.run_case(root,c)


def comparison(root,reports):
    old={r['case']:r for r in base.READ(REFERENCE/'report.json')['cases']}
    keys=['return_pct','max_drawdown_pct','final_capital_usd','win_rate_pct','trades',
        'avg_win_usd','avg_loss_usd','avg_winner_holding_sessions','avg_loser_holding_sessions',
        'mean_capital_used_usd','mean_capital_used_pct_equity']
    rows=[]
    for r in reports:
        if r['status']!='COMPLETED_EXPLORATORY':continue
        row={k:r[k] for k in ['case','year','side','sl','trailing','horizon','tp']}
        for k in keys:
            row[k+'_risk']=r[k];row[k+'_baseline']=old[r['case']][k]
        row.update(risk_trips=r['audit']['risk_trips'],forced_exits=r['audit']['forced_exits'],
            degraded_sessions=r['audit']['degraded_sessions'],daily_loss_observations=r['audit']['daily_loss_observations'])
        rows.append(row)
    pd.DataFrame(rows).to_csv(root/'comparison-risk-vs-baseline.csv',index=False)


def run(root,workers=2,smoke=False,regression_failures=False):
    from scripts.research.oracle_path_confirmation import exclusive_run
    root=Path(root)
    with exclusive_run(root):
        prepare(root);planned=base.cases()
        if smoke:planned=[c for c in planned if c['sl']==.07 and c['trailing']==.15 and c['horizon']==20 and c['tp'] is None]
        if regression_failures:planned=[c for c in planned if base.case_key(c) in REGRESSION_CASES]
        reports=[];started=time.monotonic()
        atomic_json(root/'progress.json',dict(status='RUNNING',completed=0,failed=0,total=len(planned),variant='1X_PRODUCTION_RISK'))
        with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(root),)) as pool:
            for f in as_completed([pool.submit(worker_case,str(root),c) for c in planned]):
                r=f.result();reports.append(r);ok=[x for x in reports if x['status']=='COMPLETED_EXPLORATORY']
                elapsed=time.monotonic()-started
                atomic_json(root/'progress.json',dict(status='RUNNING',completed=len(ok),failed=len(reports)-len(ok),
                    attempted=len(reports),total=len(planned),last=r['case'],last_status=r['status'],
                    elapsed_seconds=elapsed,remaining_seconds_estimate=elapsed/len(reports)*(len(planned)-len(reports))))
                pd.DataFrame([{k:v for k,v in x.items() if k not in ('files','audit','traceback')} for x in reports]).to_csv(root/'annual-summary.partial.csv',index=False)
                LOG.info('%d/%d %s %s',len(reports),len(planned),r['case'],r['status'])
        verify_hashes(Path('.'),base.READ(root/'protocol.json')['sources']);verify_hashes(root,base.READ(root/'prepared.json')['files'])
        ok=[x for x in reports if x['status']=='COMPLETED_EXPLORATORY']
        for r in ok:
            verify_hashes(root/'cases'/r['case'],r['files'])
            if r['audit']['status']!='PASS_PRODUCTION_RISK_CASH_EXITS':raise ValueError('Risk audit required')
        pd.DataFrame([{k:v for k,v in r.items() if k not in ('files','audit')} for r in ok]).to_csv(root/'annual-summary.csv',index=False)
        comparison(root,reports)
        status='COMPLETED_EXPLORATORY' if len(ok)==576 else 'PARTIAL_FAILED' if len(ok)<len(reports) else 'SMOKE_COMPLETED'
        report=dict(status=status,completed=len(ok),failed=len(reports)-len(ok),total=len(planned),max_entry_leverage=1.,
            full_live_parity=False,variant='PRODUCTION_COMPONENTS_B4_REPLAY',cases=reports,elapsed_seconds=time.monotonic()-started)
        atomic_json(root/'report.json',report);atomic_json(root/'progress.json',{k:v for k,v in report.items() if k!='cases'})
        if status=='COMPLETED_EXPLORATORY':
            atomic_json(root/'final-review.json',dict(status='PASS_COMPLETED_RISK_GRID_REVIEW',annual_cases=576,
                full_live_parity=False,all_case_files_verified=True,all_case_risk_cash_exit_audits_pass=True,
                independent_human_review=False,files={n:digest(root/n) for n in
                    ['protocol.json','prepared.json','report.json','annual-summary.csv','comparison-risk-vs-baseline.csv']}))
        return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--phase',choices=['prepare','run'],default='run');p.add_argument('--workers',type=int,default=2)
    mode=p.add_mutually_exclusive_group()
    mode.add_argument('--smoke',action='store_true');mode.add_argument('--regression-failures',action='store_true')
    a=p.parse_args()
    if not 1<=a.workers<=4:raise ValueError('Use1..4local workers')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if a.phase=='prepare':prepare(a.output)
    else:run(a.output,a.workers,a.smoke,a.regression_failures)


if __name__=='__main__':main()
