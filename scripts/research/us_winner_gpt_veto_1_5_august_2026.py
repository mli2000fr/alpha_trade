"""One local August2026 Winner account: veto VALID GPT scores 1..5.

Reuse all three audited comparators. Exact archived GPT/data/risk/protections;
no new GPT, SQL, provider or production action. Never filter realized trades.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import shutil

import pandas as pd

from scripts.research import us_winner_gpt_veto_1_4_august_2026 as previous

original,base,grid = previous.original,previous.base,previous.grid
PARENT = original.ROOT
ROOT = PARENT.parent/'20261025-score1-5-v1'
ARM = 'WINNER_GPT_VETO_1_5'
DOC = Path('doc/ml/winner_veto_gpt_1_5_aout_2026.md')
TEST = Path('tests/test_us_winner_gpt_veto_1_5_august_2026.py')
COMPARATORS = [
    (PARENT/'WINNER_ONLY','WINNER_ONLY'),
    (PARENT/'WINNER_GPT_VETO_1_3','WINNER_GPT_VETO_1_3'),
    (previous.ROOT/previous.ARM,previous.ARM),
]


def apply_cutoff(signals):
    result = signals.copy()
    result['gpt_veto'] = (result.gpt_status.eq('VALID') & result.gpt_score.between(1,5)).fillna(False)
    return result


def prepare(root):
    if (root/'protocol.json').exists():
        protocol = base.read(root/'protocol.json');base.verify(protocol['sources']);return protocol
    parent = base.read(PARENT/'protocol.json');base.verify(parent['sources'])
    prior_protocol = base.read(previous.ROOT/'protocol.json');base.verify(prior_protocol['sources'])
    sources = {**parent['sources'],**prior_protocol['sources']}
    for folder,arm in COMPARATORS:
        report = base.read(folder/'report.json')
        if report['audit']['status'] != 'PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES' or report['arm'] != arm:
            raise ValueError('Comparator audit missing')
        files = {str(folder/name):sha for name,sha in report['files'].items()}
        base.verify(files);sources.update(files)
        sources[str(folder/'report.json')] = base.digest(folder/'report.json')
    manifest = base.read(PARENT/'inputs/snapshot.json')
    base.verify({str(PARENT/'inputs'/name):sha for name,sha in manifest['files'].items()})
    archived = original.freeze_veto(pd.read_parquet(original.GPT/'candidates.parquet'),base.read(original.GPT/'scores.json'))
    signals = apply_cutoff(archived)
    before = pd.read_parquet(PARENT/'frozen-signals.parquet')
    pd.testing.assert_frame_equal(signals.drop(columns='gpt_veto'),before.drop(columns='gpt_veto'))
    for path in [Path(__file__),DOC,TEST,PARENT/'protocol.json',PARENT/'report.json',
            previous.ROOT/'protocol.json',previous.ROOT/'report.json',PARENT/'inputs/snapshot.json',PARENT/'common-cohort.parquet']:
        sources[str(path)] = base.digest(path)
    root.mkdir(parents=True,exist_ok=False)
    shutil.copytree(PARENT/'inputs',root/'inputs')
    signals.to_parquet(root/'frozen-signals.parquet',index=False)
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),reference_config=parent['reference_config'],
        parent=str(PARENT),new_accounts=[ARM],reused_accounts=[arm for _,arm in COMPARATORS],
        inclusive_veto_scores=[1,2,3,4,5],initial_equity=4000.,
        start=str(original.START),end=str(original.END),signal_period=parent['signal_period'],
        winner_policy=parent['winner_policy'],global_risk=parent['global_risk'],terminal=parent['terminal'],
        rule='VALID integer GPT scores 1..5 veto new signal plan staging only; invalid/unknown kept.',
        existing_plans='Do not cancel earlier valid plans, force existing long exits, rerank or replace by TOP21.',
        same_original_oracle_top=20,same_strict_cohort=True,effective_gross_cap=1.,fee_bps_per_leg=8,
        historical_gpt_non_PIT=True,future_coverage_selection_bias=True,independent_holdout=False,full_live_parity=False,
        gpt_calls=0,provider_calls=0,SQL_reads=0,SQL_writes=False,orders=False,production_changed=False,
        sources=sources,files={'frozen-signals.parquet':base.digest(root/'frozen-signals.parquet')})
    base.save_new(root/'protocol.json',protocol)
    grid.atomic_json(root/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol


def trade_differences(control,filtered):
    keys = lambda f:{(r.symbol,str(r.entry_date)) for r in f.itertuples()}
    ck,fk = keys(control),keys(filtered)
    removed = control[[(r.symbol,str(r.entry_date)) not in fk for r in control.itertuples()]]
    added = filtered[[(r.symbol,str(r.entry_date)) not in ck for r in filtered.itertuples()]]
    return dict(control_only_closed_trades=len(removed),filtered_only_closed_trades=len(added),
        control_only_winners=int(removed.pnl.gt(0).sum()),control_only_losers=int(removed.pnl.lt(0).sum()),
        control_only_pnl=float(removed.pnl.sum()),filtered_only_winners=int(added.pnl.gt(0).sum()),
        filtered_only_losers=int(added.pnl.lt(0).sum()),filtered_only_pnl=float(added.pnl.sum()),
        not_a_causal_per_trade_loss_estimate=True)


def run(root):
    protocol = prepare(root)
    with previous.run_lock(root):
        if (root/'report.json').exists():
            raise FileExistsError('Completed comparison is immutable')
        cohort,groups,raw,actions,sectors,pivots,calendar = original.load_inputs(root)
        old_cohort = pd.read_parquet(PARENT/'common-cohort.parquet')
        pd.testing.assert_frame_equal(cohort.drop(columns='gpt_veto'),old_cohort.drop(columns='gpt_veto'))
        selected = previous.filtered_signals(cohort)
        folder = root/ARM;folder.mkdir(exist_ok=False)
        def bars(day,symbols):
            parts = [groups[s,day] for s in symbols if (s,day) in groups]
            return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
        def progress(done,total,day):
            grid.atomic_json(root/'progress.json',dict(status='RUNNING',arm=ARM,completed_runs=0,total_runs=1,
                completed_sessions=done,total_sessions=total,last_date=day,updated_at_utc=datetime.now(timezone.utc).isoformat()))
        cfg = replace(base.engine_config(protocol['reference_config'],2026),
            start_date=original.START,end_date=original.END,cost_round_trip_bps=16.)
        expected = dict(stop_loss_pct=.07,take_profit_pct=None,trailing_stop_pct=None,horizon_sessions=20,
            initial_position_fraction=.5,reinforcement_enabled=False)
        if any(getattr(cfg.exec_config.winner_pyramiding,k) != v for k,v in expected.items()):
            raise ValueError('Actual policy differs from original August experiment')
        with grid.runtime_adapter(2026,ARM) as refusals:
            result = base.BacktestEngine(cfg).run(open_df=pivots['open'],close=pivots['close'],
                high=pivots['high'],low=pivots['low'],volume=pivots['volume'],signals_df=selected,
                sector_map=sectors,intraday_source=bars,winner_research_assumptions=True,
                winner_progress=progress,winner_corporate_actions=actions.to_dict('records'))
            grid.atomic_json(folder/'whole-share-refusals.json',refusals)
        summary = previous.metrics(result,4000.)
        if summary['status'] != 'COMPLETED_EXPLORATORY':
            raise ValueError('Incomplete coverage: '+str(summary.get('coverage_gaps')))
        allowed = cohort.copy();allowed['selected'] = selected.selected.to_numpy()
        audit = grid.audit_result(result,summary,
            {k:expected[k] for k in ['stop_loss_pct','take_profit_pct','trailing_stop_pct','horizon_sessions']},
            allowed,raw,calendar)
        for name,frame in {'trades.parquet':result.closed_trades_df,'events.parquet':result.trade_events_df,
                'equity-5m.parquet':result.intraday_equity_curve,'equity-daily.parquet':result.equity_curve.to_frame(),
                'breaker.parquet':result.drawdown_breaker_df}.items():
            frame.to_parquet(folder/name,index=name == 'equity-daily.parquet')
        summary.update(arm=ARM,audit=audit,
            **{k:audit[k] for k in ['average_winning_holding_sessions','average_losing_holding_sessions']},
            files={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()})
        base.save_new(folder/'report.json',summary)
        reports = [base.read(path/'report.json') for path,_ in COMPARATORS]+[summary]
        pd.DataFrame([{k:v for k,v in r.items() if not isinstance(v,(dict,list))} for r in reports]).to_csv(root/'comparison.csv',index=False)
        vetoed = cohort[cohort.selected & cohort.gpt_veto]
        vetoed.to_parquet(root/'veto-eligible.parquet',index=False)
        allowed.loc[cohort.selected].to_parquet(root/'eligible-after-filter.parquet',index=False)
        attribution = {arm:trade_differences(pd.read_parquet(path/'trades.parquet'),result.closed_trades_df)
            for path,arm in COMPARATORS}
        control,_,old_four,_ = reports
        report = dict(status='COMPLETED_AUDITED_EXPLORATORY',cases=reports,
            eligible_signals=int(cohort.selected.sum()),veto_original=int(cohort.gpt_veto.sum()),
            veto_eligible=len(vetoed),admissible_after_veto=int(selected.selected.sum()),
            retained_unknown_or_invalid=int((cohort.selected & (~cohort.gpt_status.eq('VALID') | cohort.gpt_score.isna())).sum()),
            veto_unique_symbols=int(vetoed.symbol.nunique()),
            net_capital_advantage_usd=summary['final_equity']-control['final_equity'],
            return_advantage_points=summary['return_pct']-control['return_pct'],
            change_vs_veto1_4_usd=summary['final_equity']-old_four['final_equity'],
            change_vs_veto1_4_points=summary['return_pct']-old_four['return_pct'],attribution=attribution,
            baseline_reused_audited=True,historical_gpt_non_PIT=True,future_coverage_selection_bias=True,
            independent_holdout=False,full_live_parity=False,open_positions_marked_not_forced=True,
            gpt_calls=0,provider_calls=0,SQL_reads=0,SQL_writes=False,orders=False,production_changed=False,
            sources=protocol['sources'],files={p.name:base.digest(p) for p in root.iterdir()
                if p.is_file() and p.name not in ['run.lock','progress.json','failure.json','report.json','stdout.log','stderr.log']})
        base.verify(protocol['sources'])
        base.save_new(root/'report.json',report)
        grid.atomic_json(root/'progress.json',dict(status=report['status'],completed_runs=1,total_runs=1))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT)
    args = parser.parse_args()
    os.environ['SSLKEYLOGFILE'] = ''
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    import requests
    requests.Session.request = lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No network in local GPT1..5 veto replay'))
    try:
        result = run(args.output)
        print(base.json.dumps({k:v for k,v in result.items() if k not in ['sources','files','cases','attribution']}))
    except BaseException as exc:
        if args.output.exists():
            grid.atomic_json(args.output/'failure.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
            grid.atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__ == '__main__':
    main()
