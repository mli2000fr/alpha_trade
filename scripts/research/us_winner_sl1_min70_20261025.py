"""SL1 versus SL5 with the frozen TOP20/$4000/min70 no-pause replay."""
from contextlib import contextmanager
from dataclasses import asdict,replace
from datetime import datetime,timezone
import json
import logging
import os
from pathlib import Path
import time

ROOT=Path('artifacts/research/us_winner_sl1_min70/20261025-v1')
ARM='FIXED_SL1_H20_MIN70'
DOC=Path('doc/ml/winner_sl1_min70_protocole_20261025.md')
TEST=Path('tests/test_us_winner_sl1_min70_20261025.py')
COMPARATOR=Path('artifacts/research/us_winner_min70_4000/20261025-v1')


def archived_config_equal(cfg,payload):
    # Persisted dates/enums/tuples use JSON representations, not Python objects.
    return json.loads(json.dumps(asdict(cfg),default=str))==payload


def actual_sl1(policy):
    if policy.stop_loss_pct!=.05 or policy.take_profit_pct is not None or policy.trailing_stop_pct is not None:
        raise ValueError('Expected SL5/noTP/noTR comparator')
    changed=replace(policy,stop_loss_pct=.01)
    before,after=asdict(policy),asdict(changed)
    after['stop_loss_pct']=before['stop_loss_pct']
    if before!=after:raise ValueError('A non-stop campaign field changed')
    return changed


@contextmanager
def sl1_policy(study):
    original=study.profile_policy
    def policy(config,name):
        if name!=study.REFERENCE:raise ValueError('Only the fixed reference is allowed')
        return actual_sl1(original(config,name))
    study.profile_policy=policy
    try:yield
    finally:study.profile_policy=original


def prepare(study,audit,repair,legacy,treatment):
    base=study.capacity.grid.base
    parent=base.read(COMPARATOR/'protocol.json');base.verify(parent['sources'])
    cfg=treatment.minimum_only(study.configuration(parent['reference_config'],study.inputs.START))
    if not archived_config_equal(cfg,parent['after']):raise ValueError('Not the exact min70 control configuration')
    changed_policy=actual_sl1(study.profile_policy(cfg.exec_config,study.REFERENCE))
    if asdict(study.profile_policy(cfg.exec_config,study.REFERENCE))!=parent['actual_campaign_policy']:
        raise ValueError('SL5 comparator policy drift')
    sources=dict(parent['sources'])
    for path in [COMPARATOR/'protocol.json',Path(__file__),DOC,TEST]:sources[str(path)]=base.digest(path)
    protocol=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        reference_config=parent['reference_config'],effective_config=asdict(cfg),
        comparator_root=str(COMPARATOR),actual_campaign_policy=asdict(changed_policy),
        comparator_campaign_policy=parent['actual_campaign_policy'],
        changed_from_min70_control=['actual_campaign_policy.stop_loss_pct'],
        initial_equity=4000.,currency='USD',minimum_notional=70.,TOP=20,
        start='2020-01-02',end='2024-12-31',gross_cap=1.,full_position=True,
        fee_per_leg=.0008,no_reinforcement=True,no_new_pause_or_global_liquidation=True,
        historical_SL3_admission_and_quantity_ceiling_preserved=True,
        no_upsize_beyond_original_admission=True,original_native_risk_B4_preserved=True,
        no_annual_reset=True,SQL_reads=0,SQL_writes=0,provider_calls=0,LLM_calls=0,
        orders=False,production_changed=False,full_live_parity=False,independent_holdout=False,
        future_coverage_selection_bias=True,current_sectors_non_PIT=True,
        loaded_core=parent['loaded_core'])
    base.verify(sources);ROOT.mkdir(parents=True,exist_ok=False)
    base.save_new(ROOT/'protocol.json',protocol)
    study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol,cfg


def run(study,audit,repair,legacy,treatment):
    import pandas as pd
    grid,base=study.capacity.grid,study.capacity.grid.base
    protocol,cfg=prepare(study,audit,repair,legacy,treatment)
    with grid.run_lock(ROOT):
        grid.atomic_json(ROOT/'process.json',dict(pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat()))
        grid.atomic_json(ROOT/'progress.json',dict(status='VERIFYING_FROZEN_LOCAL_INPUTS',completed_runs=0,total_runs=1))
        tape=study.inputs.Tape(audit.PARENT)
        if not tape.cohort.groupby('date')['rank'].apply(lambda r:sorted(r)==list(range(1,21))).all():
            raise ValueError('Not the archived TOP20')
        signals=tape.cohort[['date','symbol','rank','selected']].rename(columns={'date':'trade_date'}).copy()
        prior=max(d for d in tape.schedule if d<cfg.start_date)
        signals=signals[signals.trade_date.ge(pd.Timestamp(prior))];signals['side']='long'
        folder=ROOT/'cases'/ARM;folder.mkdir(parents=True)
        hooks=audit.ObservationHooks(study.native);started=time.monotonic()
        def progress(done,total,day):
            elapsed=time.monotonic()-started
            grid.atomic_json(ROOT/'progress.json',dict(status='RUNNING',completed_runs=0,total_runs=1,
                completed_sessions=done,total_sessions=total,last_date=str(day),elapsed_seconds=elapsed,
                estimated_remaining_seconds=elapsed*(total-done)/done,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
        with sl1_policy(study),grid.runtime_adapter(2020,ARM),study.capacity.corrected_runtime(),repair.campaign_adapter(
                cfg.exec_config,lambda _d:study.REFERENCE) as metadata,hooks.installed():
            result=base.BacktestEngine(cfg).run(open_df=tape.pivots['open'],close=tape.pivots['close'],
                high=tape.pivots['high'],low=tape.pivots['low'],volume=tape.pivots['volume'],signals_df=signals,
                sector_map=tape.sectors,intraday_source=tape,winner_research_assumptions=True,
                winner_progress=progress,winner_corporate_actions=tape.actions.to_dict('records'))
        grid.atomic_json(ROOT/'progress.json',dict(status='AUDITING',completed_runs=0,total_runs=1))
        summary=grid.metrics(result,4000.)
        checks=audit.audit_case(study,result,summary,metadata,tape,4000.,cfg.end_date)
        if any(m['policy']!=protocol['actual_campaign_policy'] for m in metadata.values()):
            raise ValueError('Actual SL1 policy drift')
        if not hooks.risk_rows or any(r['min_notional']!=70. for r in hooks.risk_rows):
            raise ValueError('Execution risk minimum drift')
        summary['outer_admission_policy']=summary.pop('policy')
        summary.update(arm=ARM,start=protocol['start'],end=protocol['end'],currency='USD',minimum_notional=70.,
            audit=checks,actual_campaign_policy=protocol['actual_campaign_policy'],
            annual=audit.annual_rows(result,4000.),full_live_parity=False,independent_holdout=False,
            future_coverage_selection_bias=True)
        result.equity_curve.to_frame().to_parquet(folder/'equity-daily.parquet')
        result.intraday_equity_curve.to_parquet(folder/'equity-5m.parquet',index=False)
        result.closed_trades_df.to_parquet(folder/'trades.parquet',index=False)
        result.trade_events_df.to_csv(folder/'events.csv',index=False)
        result.drawdown_breaker_df.to_parquet(folder/'breaker-5m.parquet',index=False)
        pd.DataFrame(hooks.risk_rows).to_parquet(folder/'risk-decisions.parquet',index=False)
        grid.atomic_json(folder/'campaign-policies.json',metadata)
        grid.atomic_json(folder/'guard-daily.json',list(hooks.guard_days.values()))
        summary['files']={p.name:base.digest(p) for p in folder.iterdir() if p.is_file()}
        base.verify(protocol['sources']);base.save_new(folder/'report.json',summary)
        pd.DataFrame(summary['annual']).to_csv(ROOT/'annual-summary.csv',index=False)
        comparator=None
        if (COMPARATOR/'report.json').exists():
            comparator=base.read(COMPARATOR/'report.json')
            if comparator['status']!='COMPLETED_AUDITED_EXPLORATORY':raise ValueError('Comparator not audited')
            base.verify(comparator['sources']);base.verify(comparator['files'])
        base.save_new(ROOT/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',case=summary,
            comparator=comparator['case'] if comparator else None,
            comparison_status='READY' if comparator else 'WAITING_SL5_MIN70',
            comparator_root=str(COMPARATOR),sources=protocol['sources'],
            files={str(folder/n):h for n,h in summary['files'].items()},full_live_parity=False))
        grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=1,total_runs=1))


def main():
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy()
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    from scripts.research import us_winner_start_state_audit_20261025 as audit
    from scripts.research import us_winner_min70_4000_20261025 as treatment
    import requests
    requests.Session.request=lambda *a,**k:(_ for _ in ()).throw(RuntimeError('HTTP forbidden in SL1 replay'))
    os.environ['SSLKEYLOGFILE']=''
    if os.name=='nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    try:run(repair.study,audit,repair,legacy,treatment)
    except BaseException as exc:
        if ROOT.exists():
            repair.study.capacity.grid.atomic_json(ROOT/'failure.json',dict(status='FAILED',error_type=type(exc).__name__,
                error=str(exc),at_utc=datetime.now(timezone.utc).isoformat()))
            repair.study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error=str(exc)))
        raise


if __name__=='__main__':main()
