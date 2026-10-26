"""Finalize already audited accounts after an operational run.lock hash error.

Local files only. Never reruns the strategy, SQL, an LLM or a broker.
The original sealed runner and account artifacts remain unchanged.
"""
import argparse
from pathlib import Path

import pandas as pd

from scripts.research import us_winner_gpt_veto_august_2026 as study
from service.market.intraday_backfill import run_lock


def report_files(root):
    # A Windows exclusive run.lock cannot be read while held. It is operational
    # state, not a research input/output to seal. Preserve the old failure as-is.
    excluded={'run.lock','progress.json','failure.json','report.json'}
    return {f.name:study.base.digest(f) for f in Path(root).iterdir() if f.is_file() and f.name not in excluded}


def finalize(root):
    root=Path(root);p=study.base.read(root/'protocol.json')
    study.base.verify(p['sources']);study.base.verify({str(root/k):v for k,v in p['files'].items()})
    if (root/'report.json').exists():raise FileExistsError('Final report already sealed')
    cases=[];results={}
    for arm in study.ARMS:
        folder=root/arm;r=study.base.read(folder/'report.json')
        study.base.verify({str(folder/k):v for k,v in r['files'].items()})
        if r['status']!='COMPLETED_EXPLORATORY' or r['audit']['status']!='PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES':
            raise ValueError('Both completed scalar/cash/entry audits required')
        cases.append(r)
        results[arm]={name:pd.read_parquet(folder/(name+'.parquet')) for name in ('trades','equity-5m','equity-daily','events')}
    control,filtered=cases
    a,b=(results[arm] for arm in study.ARMS)
    exact=True
    for name in ('trades','equity-5m','equity-daily'):
        try:pd.testing.assert_frame_equal(a[name],b[name],check_exact=True)
        except AssertionError:exact=False
    def keys(frame):return {(r.symbol,str(r.entry_date)) for r in frame.itertuples()}
    ca,cb=keys(a['trades']),keys(b['trades'])
    removed=a['trades'][[(r.symbol,str(r.entry_date)) not in cb for r in a['trades'].itertuples()]]
    added=b['trades'][[(r.symbol,str(r.entry_date)) not in ca for r in b['trades'].itertuples()]]
    cohort=pd.read_parquet(root/'common-cohort.parquet')
    amendment=dict(reason='Operational run.lock was incorrectly included in root artifact hashes',
        recovery_source_sha256=study.base.digest(Path(__file__)),original_source_unchanged=True,
        original_source_sha256=study.base.digest(Path(study.__file__)),no_replay=True,no_SQL=True,no_API=True,
        status='RESOLVED_REPORT_FINALIZATION_ONLY',prior_failure_sha256=study.base.digest(root/'failure.json'),
        excluded_operational_files=['run.lock','progress.json','failure.json'])
    study.base.save_new(root/'finalization-amendment.json',amendment)
    report=dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=cases,exact_trade_and_equity_equality=exact,
        eligible_signals=int(cohort.selected.sum()),veto_original=int(cohort.gpt_veto.sum()),
        veto_eligible=int((cohort.selected&cohort.gpt_veto).sum()),coverage_reasons=cohort.coverage_reason.value_counts().to_dict(),
        net_capital_advantage_usd=filtered['final_equity']-control['final_equity'],
        return_advantage_points=filtered['return_pct']-control['return_pct'],
        attribution=dict(control_only_closed_trades=len(removed),filtered_only_closed_trades=len(added),
            control_only_winners=int(removed.pnl.gt(0).sum()) if len(removed) else 0,
            control_only_losers=int(removed.pnl.lt(0).sum()) if len(removed) else 0,
            control_only_pnl=float(removed.pnl.sum()) if len(removed) else 0,
            filtered_only_pnl=float(added.pnl.sum()) if len(added) else 0,not_a_causal_per_trade_loss_estimate=True),
        historical_gpt_non_PIT=True,future_coverage_selection_bias=True,full_live_parity=False,independent_holdout=False,
        open_positions_marked_not_forced=True,gpt_calls=0,SQL_writes=False,broker_orders=False,
        prior_failure_resolved_by='finalization-amendment.json',sources=p['sources'],files=report_files(root))
    study.base.save_new(root/'report.json',report)
    study.atomic_json(root/'progress.json',dict(status=report['status'],completed_runs=2,total_runs=2))
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=study.ROOT)
    args=parser.parse_args()
    with run_lock(args.output):r=finalize(args.output)
    print(study.base.json.dumps({k:v for k,v in r.items() if k not in ('sources','files','cases')}))


if __name__=='__main__':main()
