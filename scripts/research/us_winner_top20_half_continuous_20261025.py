"""One-variable HALF vs sealed FULL TOP20 continuous reference, local data only.

Load the same archived engine in a fresh process. Only campaign initial fraction
changes; preserve the FULL outer SL3 admission used by the multi-profile parent.
This prevents accidentally applying HALF twice. No SQL/API/order/production edit.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict, replace
from datetime import datetime, timezone
import logging
from pathlib import Path
import os

PARENT = Path('artifacts/research/us_winner_monthly_selector/20261024-v1')
ROOT = Path('artifacts/research/us_winner_top20_half_continuous/20261025-v1')
REFERENCE = 'SHADOW_SL5_TROFF_H20_TPOFF'
ARM = 'HALF_SL5_TROFF_H20_TPOFF'
DOC = Path('doc/ml/winner_top20_demi_position_continue_20261025.md')
TEST = Path('tests/test_us_winner_top20_half_continuous_20261025.py')


def half_staging_config(config):
    """Alter only the campaign staging fraction, not admission or risk budgets."""
    return replace(config, winner_pyramiding=replace(config.winner_pyramiding,
        initial_position_fraction=.5))


@contextmanager
def half_adapter(repair, config, selector):
    # The engine supplies its own outer cfg on every stage call: changing only
    # the adapter's constructor argument would NOT change actual plans.
    native = repair.study.native
    with repair.campaign_adapter(config, selector) as metadata:
        stage = native.stage_targets

        def stage_half(store, targets, cfg, *args, **kwargs):
            return stage(store, targets, half_staging_config(cfg), *args, **kwargs)

        native.stage_targets = stage_half
        try:
            yield metadata
        finally:
            native.stage_targets = stage


def prepare(root, study, repair, legacy):
    base = study.capacity.grid.base
    parent = base.read(PARENT/'protocol.json')
    base.verify(parent['sources'])
    amendment = base.read(PARENT/'scope-repair-20261024-v1/amendment.json')
    base.verify(amendment['sources'])
    folder = PARENT/'cases'/REFERENCE
    control = base.read(folder/'report.json')
    if (control['audit']['status'] != 'PASS_SCALAR_CASH_FEES_ENTRIES_FROZEN_POLICIES'
            or control['start'] != '2019-07-01' or control['end'] != '2024-12-31'
            or control['initial_equity'] != 4000. or control['coverage_gaps']):
        raise ValueError('Expected exact audited continuous FULL reference')
    base.verify({str(folder/k): v for k, v in control['files'].items()})
    policies = base.read(folder/'campaign-policies.json')
    for item in policies.values():
        policy = item['policy']
        if any(policy[k] != v for k, v in dict(initial_position_fraction=1.,
                stop_loss_pct=.05, take_profit_pct=None, trailing_stop_pct=None,
                horizon_sessions=20, reinforcement_enabled=False).items()):
            raise ValueError('Mixed baseline campaign policies')
    cfg = study.configuration(parent, study.inputs.SHADOW_START)
    if cfg.risk_config.max_positions != 20 or cfg.risk_config.max_gross_exposure != 1.:
        raise ValueError('Expected reference risk limits')
    if cfg.exec_config.winner_pyramiding.initial_position_fraction != 1.:
        raise ValueError('Outer admission must remain exactly the FULL reference')
    effective = study.profile_policy(half_staging_config(cfg.exec_config), study.REFERENCE)
    if effective.initial_position_fraction != .5 or effective.stop_loss_pct != .05:
        raise ValueError('Incorrect actual HALF policy')
    sources = dict(parent['sources'])
    for path in [Path(__file__), TEST, DOC, Path(repair.__file__), Path(legacy.__file__),
            PARENT/'protocol.json', PARENT/'inputs/manifest.json',
            PARENT/'scope-repair-20261024-v1/amendment.json', folder/'report.json']:
        sources[str(path)] = base.digest(path)
    sources.update({str(folder/k): v for k, v in control['files'].items()})
    cores = {name: dict(loaded_file=str(archived), sha256=sha)
             for name, (_, archived, sha) in legacy.legacy_paths().items()}
    protocol = dict(reference_config=parent['reference_config'], sources=sources,
        created_at_utc=datetime.now(timezone.utc).isoformat(), experiment='TOP20_CONTINUOUS_HALF_VS_FULL',
        initial_equity=4000., start='2019-07-01', end='2024-12-31', TOP=20,
        annual_reset=False, effective_gross_cap=1., actual_winner_policy=asdict(effective),
        outer_admission_policy=asdict(cfg.exec_config.winner_pyramiding),
        only_economic_change='Actual campaign initial_position_fraction 1.0 -> 0.5; no reinforcement.',
        admission_unchanged='Same original SL3/FULL outer sizing; resize to SL5 then HALF once at staging.',
        reference=str(folder), baseline_reused_audited=True, baseline_report_sha256=base.digest(folder/'report.json'),
        frozen_input_root=str(PARENT/'inputs'), loaded_core=cores,
        same_full_risk_config=asdict(cfg.risk_config), same_execution_config=asdict(cfg.exec_config),
        monthly_selection=False, global_liquidation_added=False, forced_terminal_sale=False,
        retained='20 positions,10 entries/180days,two5m confirmations,20-session entry wait,8bps/leg,native risk.',
        SQL_reads=False, SQL_writes=False, provider_calls=0, LLM_calls=0, orders=False,
        future_coverage_selection_bias=True, current_sectors_non_PIT=True,
        independent_holdout=False, full_live_parity=False, production_changed=False)
    if (root/'protocol.json').exists():
        sealed = base.read(root/'protocol.json')
        base.verify(sealed['sources'])
        if sealed['loaded_core'] != cores or sealed['baseline_report_sha256'] != protocol['baseline_report_sha256']:
            raise ValueError('Sealed comparator changed')
        return sealed
    root.mkdir(parents=True, exist_ok=False)
    base.save_new(root/'protocol.json', protocol)
    study.capacity.grid.atomic_json(root/'progress.json', dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol


def run(root, study, repair, legacy):
    base = study.capacity.grid.base
    grid = study.capacity.grid
    protocol = prepare(root, study, repair, legacy)
    with grid.run_lock(root):
        if (root/'report.json').exists():
            raise FileExistsError('Completed comparison must not be overwritten')
        grid.atomic_json(root/'process.json', dict(pid=os.getpid(), started_at_utc=datetime.now(timezone.utc).isoformat(),
            archived_core=protocol['loaded_core']))
        grid.atomic_json(root/'progress.json', dict(status='VERIFYING_FROZEN_LOCAL_INPUTS',completed_runs=0,total_runs=1))
        tape = study.inputs.Tape(PARENT)  # Exact parent files, read-only; verifies all19k hashes.
        if not tape.cohort.groupby('date')['rank'].apply(lambda r: sorted(r) == list(range(1,21))).all():
            raise ValueError('Original TOP20 changed')
        original_root, original_arms = study.ROOT, study.ARMS
        original_adapter = study.campaign_adapter
        original_runtime_adapter = grid.runtime_adapter
        refusals = []

        @contextmanager
        def record_refusals(*args, **kwargs):
            with original_runtime_adapter(*args, **kwargs) as rows:
                yield rows
                refusals.extend(rows)

        study.ROOT, study.ARMS = root, [ARM]
        study.campaign_adapter = lambda config, selector: half_adapter(repair, config, selector)
        grid.runtime_adapter = record_refusals
        try:
            half = study.run_case(protocol, ARM, tape, lambda _d: study.REFERENCE, study.inputs.SHADOW_START)
            if half['status'] != 'COMPLETED_EXPLORATORY' or half['coverage_gaps']:
                raise ValueError('Incomplete HALF replay')
            metadata = base.read(root/'cases'/ARM/'campaign-policies.json')
            if not metadata or any(m['policy'] != protocol['actual_winner_policy'] for m in metadata.values()):
                raise ValueError('Actual HALF campaign policy differs from frozen protocol')
            # Audit that every filled campaign applies HALF once to its SL5-resized approval.
            import pandas as pd
            from common.winner_pyramiding import initial_quantities, WinnerPyramidingConfig
            from execution_engine.models import ExecutionTarget
            cfg = study.configuration(protocol, study.inputs.SHADOW_START)
            by_entry = {(m['symbol'], pd.Timestamp(m['first_fill_at'])): m
                        for m in metadata.values() if m.get('first_fill_at')}
            events = pd.read_csv(root/'cases'/ARM/'events.csv')
            checks = []
            for b in events[events.event.eq('BUY_FILL')].itertuples():
                m = by_entry[b.symbol, pd.Timestamp(b.time)]
                policy = WinnerPyramidingConfig(**m['policy'])
                target = study.resize_target(ExecutionTarget(**m['admission_target']), cfg.exec_config, policy)
                full, initial = initial_quantities(target.target_shares, target.entry_price,
                    target.risk_budget_dollars, policy)
                if initial != int(full*.5) or b.quantity > initial or b.quantity < 1:
                    raise ValueError('HALF sizing mismatch')
                checks.append(dict(symbol=b.symbol, time=b.time, full_quantity=full,
                    initial_quantity=initial, filled_quantity=b.quantity))
            grid.atomic_json(root/'half-sizing-audit.json', dict(status='PASS_HALF_APPLIED_ONCE',checks=checks,
                whole_share_refusals=refusals))
            annual = study.annual_results(ARM)
        finally:
            study.ROOT, study.ARMS, study.campaign_adapter = original_root, original_arms, original_adapter
            grid.runtime_adapter = original_runtime_adapter
        control = base.read(PARENT/'cases'/REFERENCE/'report.json')
        base.verify(protocol['sources'])
        comparison = dict(status='COMPLETED_AUDITED_EXPLORATORY',
            full={k:v for k,v in control.items() if k != 'files'},
            half={k:v for k,v in half.items() if k != 'files'}, half_annual=annual,
            half_actual_policy=protocol['actual_winner_policy'],
            return_difference_points=half['return_pct']-control['return_pct'],
            drawdown_magnitude_reduction_points=abs(control['max_drawdown_pct'])-abs(half['max_drawdown_pct']),
            baseline_reused_audited=True, no_linear_scaling_assumed=True,
            future_coverage_selection_bias=True, independent_holdout=False, full_live_parity=False,
            sources=protocol['sources'], files={name:base.digest(root/name) for name in ['half-sizing-audit.json']})
        base.save_new(root/'report.json', comparison)
        grid.atomic_json(root/'progress.json',dict(status=comparison['status'],completed_runs=1,total_runs=1))
        print(base.json.dumps({k:v for k,v in comparison.items() if k in
            ['status','return_difference_points','drawdown_magnitude_reduction_points']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['prepare','run'], default='run')
    parser.add_argument('--output', type=Path, default=ROOT)
    args = parser.parse_args()
    # Must happen before importing any consumer of simulator/winner_intraday.
    from scripts.research import us_winner_legacy_resume_20261024 as legacy
    legacy.install_legacy()
    from scripts.research import us_winner_monthly_scope_repair_20261024 as repair
    study = repair.study
    import requests
    requests.Session.request = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('No HTTP in local comparison'))
    os.environ['SSLKEYLOGFILE'] = ''
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR, force=True)
    try:
        prepare(args.output, study, repair, legacy) if args.phase == 'prepare' else run(args.output, study, repair, legacy)
    except BaseException as exc:
        if args.output.exists():
            study.capacity.grid.atomic_json(args.output/'failure.json', dict(status='FAILED',
                error_type=type(exc).__name__,error=str(exc),at_utc=datetime.now(timezone.utc).isoformat()))
            study.capacity.grid.atomic_json(args.output/'progress.json', dict(status='FAILED',error=str(exc)))
        raise


if __name__ == '__main__':
    main()
