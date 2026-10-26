"""Paired frozen TOP20 replay: $4,000, minimum notional $70 instead of $155.

The archived no-pause engine is loaded BEFORE importing replay modules.
No current presets, SQL, HTTP, training, broker or production mutations.
"""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import time

ROOT = Path('artifacts/research/us_winner_min70_4000/20261025-v1')
ARM = 'FIXED_REFERENCE_MIN70'
DOC = Path('doc/ml/winner_min70_4000_protocole_20261025.md')
TEST = Path('tests/test_us_winner_min70_4000_20261025.py')


def minimum_only(cfg, minimum=70.):
    if cfg.initial_equity != 4000. or cfg.risk_config.effective_min_notional != 155.:
        raise ValueError('Expected frozen $4000/min155 comparator configuration')
    if cfg.risk_config.enforce_min_notional is not None or minimum != 70.:
        raise ValueError('Unexpected override or treatment')
    changed = replace(cfg, risk_config=replace(cfg.risk_config, min_position_notional=minimum))
    before, after = asdict(cfg), asdict(changed)
    after['risk_config']['min_position_notional'] = before['risk_config']['min_position_notional']
    if before != after or changed.risk_config.effective_min_notional != minimum:
        raise ValueError('A field other than minimum notional changed')
    return changed


def prepare(study, audit, repair, legacy):
    grid, base = study.capacity.grid, study.capacity.grid.base
    parent = base.read(audit.PARENT/'protocol.json')
    amendment = audit.PARENT/'scope-repair-20261024-v1/amendment.json'
    base.verify(parent['sources']); base.verify(base.read(amendment)['sources'])
    comparator = audit.PARENT/'cases/FIXED_REFERENCE'
    control = base.read(comparator/'report.json')
    study.near(control['final_equity'], 5178.779578340831)
    if control['audit']['status'] != 'PASS_SCALAR_CASH_FEES_ENTRIES_FROZEN_POLICIES':
        raise ValueError('Audited no-pause comparator required')
    cfg = minimum_only(study.configuration(parent, study.inputs.START))
    sources = dict(parent['sources'])
    sources.update(base.read(amendment)['sources'])
    sources.update({str(comparator/n): h for n,h in control['files'].items()})
    for path in [audit.PARENT/'protocol.json', amendment, comparator/'report.json',
                 Path(__file__), DOC, TEST, Path(audit.__file__), Path(repair.__file__),
                 Path(legacy.__file__), audit.PARENT/'inputs/manifest.json']:
        sources[str(path)] = base.digest(path)
    base.verify(sources)
    protocol = dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources=sources, reference_config=parent, control=control,
        changed_fields=['risk_config.min_position_notional'],
        before=asdict(study.configuration(parent,study.inputs.START)), after=asdict(cfg),
        actual_campaign_policy=asdict(study.profile_policy(cfg.exec_config,study.REFERENCE)),
        initial_equity=4000., currency='USD', minimum_notional=70.,
        start='2020-01-02', end='2024-12-31', TOP=20, gross_cap=1.,
        full_position=True, reinforcement=False, fee_per_leg=.0008,
        monthly_selection=False, new_cycle_liquidation=False, new_three_month_pause=False,
        original_native_B4_preserved=True, outer_admission_SL3_resize_SL5_preserved=True,
        no_annual_reset=True, full_live_parity=False, independent_holdout=False,
        future_coverage_selection_bias=True, current_sectors_non_PIT=True,
        SQL_reads=0, SQL_writes=0, provider_calls=0, LLM_calls=0, orders=False,
        production_changed=False, current_presets_not_loaded=True,
        loaded_core={m:dict(path=str(p),sha256=h) for m,(_,p,h) in legacy.legacy_paths().items()})
    ROOT.mkdir(parents=True,exist_ok=False)
    base.save_new(ROOT/'protocol.json',protocol)
    grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol


def run(study,audit,repair,legacy):
    import pandas as pd
    grid,base = study.capacity.grid,study.capacity.grid.base
    protocol = prepare(study,audit,repair,legacy)
    with grid.run_lock(ROOT):
        grid.atomic_json(ROOT/'process.json',dict(pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat()))
        grid.atomic_json(ROOT/'progress.json',dict(status='VERIFYING_FROZEN_LOCAL_INPUTS',completed_runs=0,total_runs=1))
        tape = study.inputs.Tape(audit.PARENT)
        if not tape.cohort.groupby('date')['rank'].apply(lambda r:sorted(r)==list(range(1,21))).all():
            raise ValueError('Not the frozen TOP20')
        cfg = minimum_only(study.configuration(protocol['reference_config'],study.inputs.START))
        if asdict(cfg) != protocol['after']:raise ValueError('Effective config drift')
        signals = tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
        prior = max(d for d in tape.schedule if d<cfg.start_date)
        signals = signals[signals.trade_date.ge(pd.Timestamp(prior))];signals['side']='long'
        folder=ROOT/'cases'/ARM;folder.mkdir(parents=True)
        hooks=audit.ObservationHooks(study.native)
        started=time.monotonic()
        def progress(done,total,day):
            elapsed=time.monotonic()-started
            grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',completed_runs=0,total_runs=1,
                completed_sessions=done,total_sessions=total,last_date=str(day),
                elapsed_seconds=elapsed,estimated_remaining_seconds=elapsed*(total-done)/done,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
        with grid.runtime_adapter(2020,ARM),study.capacity.corrected_runtime(),repair.campaign_adapter(
                cfg.exec_config,lambda _d:study.REFERENCE) as metadata,hooks.installed():
            result=base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
                high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
                sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
                winner_progress=progress,winner_corporate_actions=tape.actions.to_dict('records'))
        grid.atomic_json(ROOT/'progress.json',dict(status='AUDITING',completed_runs=0,total_runs=1))
        summary=grid.metrics(result,4000.)
        checks=audit.audit_case(study,result,summary,metadata,tape,4000.,cfg.end_date)
        if any(m['policy']!=protocol['actual_campaign_policy'] for m in metadata.values()):
            raise ValueError('Campaign policy drift')
        if not hooks.risk_rows or any(r['min_notional']!=70. for r in hooks.risk_rows):
            raise ValueError('Minimum not applied to native execution risk')
        summary['outer_admission_policy']=summary.pop('policy')
        summary.update(arm=ARM,initial_equity=4000.,currency='USD',minimum_notional=70.,
            start=protocol['start'],end=protocol['end'],audit=checks,
            actual_campaign_policy=protocol['actual_campaign_policy'],annual=audit.annual_rows(result,4000.),
            future_coverage_selection_bias=True,independent_holdout=False,full_live_parity=False)
        result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
        result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
        result.closed_trades_df.to_parquet(folder/'trades.parquet',index=False)
        result.trade_events_df.to_csv(folder/'events.csv',index=False)
        result.drawdown_breaker_df.to_parquet(folder/'breaker-5m.parquet',index=False)
        pd.DataFrame(hooks.risk_rows).to_parquet(folder/'risk-decisions.parquet',index=False)
        grid.atomic_json(folder/'guard-daily.json',list(hooks.guard_days.values()))
        grid.atomic_json(folder/'campaign-policies.json',metadata)
        summary['files']={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()}
        base.verify(protocol['sources'])
        base.save_new(folder/'report.json',summary)
        pd.DataFrame(summary['annual']).to_csv(ROOT/'annual-summary.csv',index=False)
        keys=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','win_pct',
              'gross_winning_pnl','gross_losing_pnl','average_winning_pnl','average_losing_pnl',
              'average_gross_capital','average_gross_equity_ratio','costs']
        comparison={k:dict(min155=protocol['control'][k],min70=summary[k],
                          delta=summary[k]-protocol['control'][k]) for k in keys}
        base.save_new(ROOT/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',case=summary,
            comparator=protocol['control'],comparison=comparison,sources=protocol['sources'],
            files={str(folder/n):h for n,h in summary['files'].items()},full_live_parity=False))
        grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=1,total_runs=1))


def main():
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy()
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from scripts.research import us_winner_start_state_audit_20261025 as audit
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('HTTP forbidden in frozen min70 replay'))
    os.environ['SSLKEYLOGFILE']=''
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    try:run(repair.study,audit,repair,legacy)
    except BaseException as exc:
        if ROOT.exists():
            repair.study.capacity.grid.atomic_json(ROOT/'failure.json',dict(status='FAILED',
                error_type=type(exc).__name__,error=str(exc),at_utc=datetime.now(timezone.utc).isoformat()))
            repair.study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__=='__main__':main()
