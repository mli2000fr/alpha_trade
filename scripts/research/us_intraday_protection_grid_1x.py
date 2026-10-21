"""Paired1x replay of the sealed2x grid. No modifications to that experiment.

Only entry buying power/gross admission cap change. Targets/signals/exits,
fees/loan/maintenance/annual reset/data remain frozen. SHORT still borrows stock.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil
import time

import pandas as pd

from execution_engine.config import LeverageConfig
from scripts.research import us_intraday_protection_grid as base
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

TWO_X = Path('artifacts/research/us_intraday_protection_grid/20261021-v1')
DEFAULT_OUTPUT = Path('artifacts/research/us_intraday_protection_grid/20261021-1x-v1')
LOG = logging.getLogger(__name__)


def risk_config():
    # Preserve full target50%, planned risk4%, then HALF, exactly as in2x.
    return replace(base.risk_config(), max_gross_exposure=1.)


def execution_config():
    return replace(base.execution_config(), simulated_margin_buying_power_multiplier=1.,
        leverage=LeverageConfig(enabled=False, mode='disabled', max_leverage=1.,
            dry_run_simulated_leverage=1., min_equity_usd=2000., audit_log=False))


class OneXGridLedger(base.GridLedger):
    def __init__(self, calendar, **kwargs):
        super().__init__(calendar, **kwargs)
        self.risk=risk_config()
        self.engine.config.risk_config=self.risk
        self.engine.config.exec_config=execution_config()

    def enter(self, symbol, side, price_info, **kwargs):
        before=dict(equity=self.equity(),gross=self.gross(),buying_power=self.buying_power())
        opened=super().enter(symbol,side,price_info,**kwargs)
        if opened:
            if self.gross()>self.equity()+1e-7:
                raise ValueError('1x admission exposure exceeded')
            if side=='buy' and self.state.settled_cash < -1e-7:
                raise ValueError('LONG1x entry used borrowed cash')
            self.audit[-1].update(max_entry_leverage=1.,pre_entry=before,
                post_entry_equity=self.equity(),post_entry_gross=self.gross())
        return opened


def prepare(root):
    root=Path(root)
    if root.resolve()==TWO_X.resolve():raise ValueError('Never overwrite the2x experiment')
    if (root/'prepared.json').exists():
        verify_hashes(Path('.'),base.READ(root/'protocol.json')['sources'])
        verify_hashes(root,base.READ(root/'prepared.json')['files'])
        return
    if root.exists() and any(p.name!='run.lock' for p in root.iterdir()):
        raise ValueError('Fresh output required')
    old=base.READ(TWO_X/'protocol.json')
    verify_hashes(Path('.'),old['sources'])
    ready=base.READ(TWO_X/'prepared.json')
    verify_hashes(TWO_X,ready['files'])
    review=base.READ(TWO_X/'final-review.json')
    if review['status']!='PASS_COMPLETED_GRID_REVIEW' or review['annual_cases']!=576:
        raise ValueError('Completed2x reference not qualified')
    verify_hashes(TWO_X,review['files'])
    sources=dict(old['sources'])
    for p in [Path(__file__),Path('tests/test_us_intraday_protection_grid_1x.py'),
              TWO_X/'protocol.json',TWO_X/'prepared.json',TWO_X/'report.json',TWO_X/'final-review.json']:
        sources[str(p)]=digest(p)
    protocol=dict(old)
    protocol.update(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        paired_reference=str(TWO_X),max_entry_leverage=1.,risk=asdict(risk_config()),
        execution=asdict(execution_config()),
        entry=old['entry'].replace('HALF of leveraged full target','Same HALF target as2x'),
        sizing='UNCHANGED full target<=50%equity/4%plannedSL risk thenHALF<=25%equity. Only total gross admission/buying power cap changes2x->1x. Native cash/fee budget may reduce quantity or reject. NOT automatic half-size per entry.',
        comparison_change=['risk.max_gross_exposure:2->1','execution margin multiplier:2->1',
            'execution leverage disabled/max1'],
        unchanged='Same4k independent annual accounts,213cohort,signals/firstattempts,prices,ATR/ADV,SL/trailing/H/TP,fees,borrow,minimum equity,maintenance,trackers,marks/MTM,financing convention6.5%ACT360 if debit. No forced rebalance solely for1x mark drift.',
        without_leverage='At new fills gross<=equity incl fees. LONG cash cannot be borrowed. SHORT still requires borrowed shares with identical assumed availability/costs; adverse marks may raise gross/equity above1 after admission. It is not a cash-account SHORT strategy.',
        limitations=[s.replace('2x/financing conventions aligned','1x vs sealed2x budget comparison') for s in old['limitations']],
        full_live_parity=False)
    root.mkdir(parents=True,exist_ok=True)
    atomic_json(root/'protocol.json',protocol)
    for name,sha in ready['files'].items():
        shutil.copyfile(TWO_X/name,root/name)
        if digest(root/name)!=sha:raise ValueError('Paired input changed')
    atomic_json(root/'prepared.json',dict(files=ready['files'],inputs_identical_to=str(TWO_X)))


def worker_init(root):
    # Process-local research adapter substitution; the sealed base files and
    # production modules are never edited or configured by this runner.
    logging.basicConfig(level=logging.ERROR,force=True)
    base.GridLedger=OneXGridLedger
    base.CACHE=base.load_tapes(root)


def paired_comparison(root,reports):
    previous={r['case']:r for r in base.READ(TWO_X/'report.json')['cases']}
    columns=['final_capital_usd','return_pct','max_drawdown_pct','win_rate_pct',
        'avg_win_usd','avg_loss_usd','avg_winner_holding_sessions','avg_loser_holding_sessions',
        'mean_capital_used_usd','mean_capital_used_pct_equity','max_observed_leverage','financing_usd']
    rows=[]
    for r in reports:
        if r['status']!='COMPLETED_EXPLORATORY':continue
        p=previous[r['case']]
        row={k:r[k] for k in ['case','year','side','sl','trailing','horizon','tp']}
        for col in columns:
            row[col+'_1x']=r[col];row[col+'_2x']=p[col]
            row[col+'_delta_1x_minus_2x']=r[col]-p[col] if r[col] is not None and p[col] is not None else None
        rows.append(row)
    pd.DataFrame(rows).to_csv(root/'comparison-1x-vs-2x.csv',index=False)


def run(root,workers=2,smoke=False):
    from scripts.research.oracle_path_confirmation import exclusive_run
    root=Path(root)
    with exclusive_run(root):
        prepare(root)
        planned=base.cases()
        if smoke:planned=[c for c in planned if c['sl']==.07 and c['trailing']==.15 and c['horizon']==20 and c['tp'] is None]
        reports=[];start=time.monotonic()
        atomic_json(root/'progress.json',dict(status='RUNNING',completed=0,failed=0,total=len(planned),max_entry_leverage=1.))
        with ProcessPoolExecutor(max_workers=workers,initializer=worker_init,initargs=(str(root),)) as pool:
            fs=[pool.submit(base.run_case,str(root),c) for c in planned]
            for f in as_completed(fs):
                r=f.result();reports.append(r)
                ok=[x for x in reports if x['status']=='COMPLETED_EXPLORATORY']
                elapsed=time.monotonic()-start
                atomic_json(root/'progress.json',dict(status='RUNNING',completed=len(ok),failed=len(reports)-len(ok),
                    total=len(planned),attempted=len(reports),last=r['case'],last_status=r['status'],max_entry_leverage=1.,
                    elapsed_seconds=elapsed,remaining_seconds_estimate=elapsed/len(reports)*(len(planned)-len(reports)),
                    updated_at_utc=datetime.now(timezone.utc).isoformat()))
                pd.DataFrame([{k:v for k,v in x.items() if k not in ('files','audit','traceback')} for x in reports]).to_csv(root/'annual-summary.partial.csv',index=False)
                LOG.info('%d/%d %s %s',len(reports),len(planned),r['case'],r['status'])
        verify_hashes(Path('.'),base.READ(root/'protocol.json')['sources'])
        verify_hashes(root,base.READ(root/'prepared.json')['files'])
        ok=[r for r in reports if r['status']=='COMPLETED_EXPLORATORY']
        status='COMPLETED_EXPLORATORY' if len(ok)==576 else 'PARTIAL_FAILED' if len(ok)<len(reports) else 'SMOKE_COMPLETED'
        pd.DataFrame([{k:v for k,v in r.items() if k not in ('files','audit')} for r in ok]).to_csv(root/'annual-summary.csv',index=False)
        paired_comparison(root,reports)
        for r in ok:
            verify_hashes(root/'cases'/r['case'],r['files'])
            if r['audit']['status']!='PASS_SCALAR_EXITS_AND_CASH':raise ValueError('Case audit failed')
            decisions=base.READ(root/'cases'/r['case']/'decisions.json')
            for d in decisions:
                if d['status']=='NATIVE_OPENED':
                    if d.get('max_entry_leverage')!=1. or d['post_entry_gross']>d['post_entry_equity']+1e-7:
                        raise ValueError('Entry proof missing or exceeds1x')
        report=dict(status=status,completed=len(ok),failed=len(reports)-len(ok),total=len(planned),
            max_entry_leverage=1.,cases=reports,full_live_parity=False,elapsed_seconds=time.monotonic()-start)
        atomic_json(root/'report.json',report)
        atomic_json(root/'progress.json',{k:v for k,v in report.items() if k!='cases'})
        if status=='COMPLETED_EXPLORATORY':
            atomic_json(root/'final-review.json',dict(status='PASS_COMPLETED_1X_GRID_REVIEW',annual_cases=576,
                inputs_identical_to=str(TWO_X),sources_verified=True,all_case_files_verified=True,
                all_case_cash_exit_audits_pass=True,all_opened_entries_verified_1x=True,
                reviewed_at_utc=datetime.now(timezone.utc).isoformat(),
                max_entry_leverage=1.,independent_human_review=False,
                max_reconstruction_error_usd=max(r['audit']['max_absolute_reconstruction_error_usd'] for r in ok),
                files={n:digest(root/n) for n in ['protocol.json','prepared.json','report.json','annual-summary.csv','comparison-1x-vs-2x.csv']}))
        return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=DEFAULT_OUTPUT)
    p.add_argument('--phase',choices=['prepare','run'],default='run')
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--smoke',action='store_true')
    a=p.parse_args()
    if not 1<=a.workers<=4:raise ValueError('Use1..4local workers')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    if a.phase=='prepare':prepare(a.output)
    else:run(a.output,a.workers,a.smoke)


if __name__=='__main__':main()
