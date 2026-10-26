"""Local archived Winner experiment: change only the inclusive GPT veto to 1..4.

Reuse the sealed, audited Winner-only account. No SQL, network, model or order.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import shutil

import pandas as pd

from scripts.research import us_winner_gpt_veto_august_2026 as original
from scripts.research.us_winner_gpt_veto_august_2026 import base, grid
from backtesting.winner_campaign_replay import atomic_json, metrics
from service.market.intraday_backfill import run_lock

PARENT = original.ROOT
ROOT = PARENT.parent / '20261025-score1-4-v1'
ARM = 'WINNER_GPT_VETO_1_4'


def apply_cutoff(signals):
    """Keep invalid/unknown opinions and all original rows/ranks."""
    out = signals.copy()
    out['gpt_veto'] = (out.gpt_status.eq('VALID') & out.gpt_score.between(1, 4)).fillna(False)
    return out


def filtered_signals(cohort):
    out = cohort[['date', 'symbol', 'oracle_rank']].rename(
        columns={'date': 'trade_date', 'oracle_rank': 'rank'}).copy()
    out['selected'] = (cohort.selected & ~cohort.gpt_veto).to_numpy()
    out['side'] = 'long'
    return out


def prepare(root):
    parent = base.read(PARENT / 'protocol.json')
    report = base.read(PARENT / 'report.json')
    if report['status'] != 'COMPLETED_AUDITED_EXPLORATORY':
        raise ValueError('Audited original experiment required')
    base.verify(parent['sources'])
    control_dir = PARENT / 'WINNER_ONLY'
    control = base.read(control_dir / 'report.json')
    if control['audit']['status'] != 'PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES':
        raise ValueError('Control not audited')
    base.verify({str(control_dir / k): v for k, v in control['files'].items()})
    manifest = base.read(PARENT / 'inputs/snapshot.json')
    base.verify({str(PARENT / 'inputs' / k): v for k, v in manifest['files'].items()})
    # Reconstruct from the exact archived validated responses, not rounded UI scores.
    signals = apply_cutoff(original.freeze_veto(
        pd.read_parquet(original.GPT / 'candidates.parquet'), base.read(original.GPT / 'scores.json')))
    prior = pd.read_parquet(PARENT / 'frozen-signals.parquet')
    pd.testing.assert_frame_equal(signals.drop(columns='gpt_veto'), prior.drop(columns='gpt_veto'))
    root.mkdir(parents=True, exist_ok=False)
    shutil.copytree(PARENT / 'inputs', root / 'inputs')
    signals.to_parquet(root / 'frozen-signals.parquet', index=False)
    sources = dict(parent['sources'])
    for file in [Path(__file__), Path('tests/test_us_winner_gpt_veto_1_4_august_2026.py'),
                 PARENT / 'protocol.json', PARENT / 'report.json', PARENT / 'common-cohort.parquet',
                 control_dir / 'report.json', PARENT / 'inputs/snapshot.json']:
        sources[str(file)] = base.digest(file)
    sources.update({str(control_dir / k): v for k, v in control['files'].items()})
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        reference_config=parent['reference_config'], parent=str(PARENT),
        baseline_reused_audited=True, baseline=str(control_dir), arms=['WINNER_ONLY', ARM],
        inclusive_veto_scores=[1, 2, 3, 4], initial_equity=4000,
        start=str(original.START), end=str(original.END), signal_period=parent['signal_period'],
        rule='Only VALID integer scores 1..4 veto new plan staging. No replacement/reranking.',
        existing_plans='No cancellation of earlier plans; no sale of existing longs.',
        effective_gross_cap=1., fee_bps_per_leg=8, winner_policy=parent['winner_policy'],
        global_risk=parent['global_risk'], terminal=parent['terminal'],
        historical_gpt_non_PIT=True, future_coverage_selection_bias=True,
        full_live_parity=False, independent_holdout=False,
        gpt_calls=0, provider_calls=0, SQL_reads=False, SQL_writes=False, broker_orders=False,
        sources=sources, files={'frozen-signals.parquet': base.digest(root / 'frozen-signals.parquet')})
    base.save_new(root / 'protocol.json', protocol)
    atomic_json(root / 'progress.json', dict(status='PREPARED', completed_runs=0, total_runs=1))
    return protocol


def run(root):
    p = prepare(root)
    with run_lock(root):
        cohort, groups, raw, actions, sectors, pivots, calendar = original.load_inputs(root)
        parent_cohort = pd.read_parquet(PARENT / 'common-cohort.parquet')
        pd.testing.assert_frame_equal(cohort.drop(columns='gpt_veto'), parent_cohort.drop(columns='gpt_veto'))
        selected = filtered_signals(cohort)
        folder = root / ARM
        folder.mkdir(exist_ok=False)

        def bars(day, symbols):
            parts = [groups[s, day] for s in symbols if (s, day) in groups]
            return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

        def progress(done, total, day):
            atomic_json(root / 'progress.json', dict(status='RUNNING', arm=ARM,
                completed_runs=0, total_runs=1, completed_sessions=done, total_sessions=total, last_date=day))

        cfg = replace(base.engine_config(p['reference_config'], 2026),
            start_date=original.START, end_date=original.END, cost_round_trip_bps=16.)
        with grid.runtime_adapter(2026, ARM) as refusals:
            result = base.BacktestEngine(cfg).run(open_df=pivots['open'], close=pivots['close'],
                high=pivots['high'], low=pivots['low'], volume=pivots['volume'], signals_df=selected,
                sector_map=sectors, intraday_source=bars, winner_research_assumptions=True,
                winner_progress=progress, winner_corporate_actions=actions.to_dict('records'))
            atomic_json(folder / 'whole-share-refusals.json', refusals)
        summary = metrics(result, 4000.)
        if summary['status'] != 'COMPLETED_EXPLORATORY':
            raise ValueError('Incomplete replay coverage: ' + str(summary.get('coverage_gaps')))
        allowed = cohort.copy()
        allowed['selected'] = selected.selected.to_numpy()
        audit = grid.audit_result(result, summary, dict(stop_loss_pct=.07, take_profit_pct=None,
            trailing_stop_pct=None, horizon_sessions=20), allowed, raw, calendar)
        outputs = {'trades.parquet': result.closed_trades_df, 'events.parquet': result.trade_events_df,
            'equity-5m.parquet': result.intraday_equity_curve,
            'equity-daily.parquet': result.equity_curve.to_frame(), 'breaker.parquet': result.drawdown_breaker_df}
        for name, frame in outputs.items():
            frame.to_parquet(folder / name, index=name == 'equity-daily.parquet')
        summary.update(arm=ARM, audit=audit,
            **{k: audit[k] for k in ('average_winning_holding_sessions', 'average_losing_holding_sessions')},
            files={f.name: base.digest(f) for f in folder.iterdir() if f.is_file()})
        base.save_new(folder / 'report.json', summary)
        control = base.read(PARENT / 'WINNER_ONLY/report.json')
        prior = base.read(PARENT / 'WINNER_GPT_VETO_1_3/report.json')
        reports = [control, prior, summary]
        pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, (dict, list))}
                      for r in reports]).to_csv(root / 'comparison.csv', index=False)
        control_trades = pd.read_parquet(PARENT / 'WINNER_ONLY/trades.parquet')
        new_trades = result.closed_trades_df
        keys = lambda f: {(r.symbol, str(r.entry_date)) for r in f.itertuples()}
        ck, fk = keys(control_trades), keys(new_trades)
        removed = control_trades[[(r.symbol, str(r.entry_date)) not in fk for r in control_trades.itertuples()]]
        added = new_trades[[(r.symbol, str(r.entry_date)) not in ck for r in new_trades.itertuples()]]
        cohort.loc[cohort.selected & cohort.gpt_veto].to_parquet(root / 'veto-eligible.parquet', index=False)
        report = dict(status='COMPLETED_AUDITED_EXPLORATORY', cases=reports,
            eligible_signals=int(cohort.selected.sum()), veto_original=int(cohort.gpt_veto.sum()),
            veto_eligible=int((cohort.selected & cohort.gpt_veto).sum()),
            net_capital_advantage_usd=summary['final_equity'] - control['final_equity'],
            return_advantage_points=summary['return_pct'] - control['return_pct'],
            attribution=dict(control_only_closed_trades=len(removed), filtered_only_closed_trades=len(added),
                control_only_winners=int(removed.pnl.gt(0).sum()), control_only_losers=int(removed.pnl.lt(0).sum()),
                control_only_pnl=float(removed.pnl.sum()), filtered_only_pnl=float(added.pnl.sum()),
                not_a_causal_per_trade_loss_estimate=True),
            baseline_reused_audited=True, historical_gpt_non_PIT=True, future_coverage_selection_bias=True,
            full_live_parity=False, independent_holdout=False, open_positions_marked_not_forced=True,
            gpt_calls=0, SQL_reads=False, SQL_writes=False, broker_orders=False,
            sources=p['sources'], files={f.name: base.digest(f) for f in root.iterdir()
                if f.is_file() and f.name not in {'run.lock', 'progress.json', 'failure.json', 'report.json'}})
        base.verify(p['sources'])
        base.save_new(root / 'report.json', report)
        atomic_json(root / 'progress.json', dict(status=report['status'], completed_runs=1, total_runs=1))
        return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT)
    args = parser.parse_args()
    import requests
    requests.Session.request = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('Network forbidden'))
    try:
        report = run(args.output)
        print(base.json.dumps({k: v for k, v in report.items() if k not in {'sources', 'files', 'cases'}}))
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output / 'failure.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)[:500]))
        raise


if __name__ == '__main__':
    main()
