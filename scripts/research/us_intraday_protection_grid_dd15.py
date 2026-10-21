"""Threshold-only paired replay: configured B4 DD15 vs sealed corrected DD20.

Offline research. Reuse the exact sealed engine, cohort and audited data.
Never mutate the DD20 runner, results, trading settings, models or database.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import logging
from pathlib import Path
import shutil

import pandas as pd

from backtesting.production_risk_replay import GUARD_FIELDS
from common.config_loader import load_config
from risk_management.config import load_risk_config
from scripts.research import us_intraday_protection_grid_risk as risk
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


REFERENCE = Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-v2')
DEFAULT_OUTPUT = Path('artifacts/research/us_intraday_protection_grid/20261021-1x-risk-dd15-v1')
DD_FIELD = 'max_portfolio_drawdown_pct'
THRESHOLD = .15
ORIGINAL_COMPARISON = risk.comparison


def threshold_profile(previous, configured_fields, force_enabled, force_fraction):
    """One independent variable, not a silent refresh of all current settings."""
    if set(configured_fields) != set(GUARD_FIELDS):
        raise ValueError('Complete effective guard configuration required')
    if previous['guard_fields'][DD_FIELD] != .20 or configured_fields[DD_FIELD] != THRESHOLD:
        raise ValueError('This experiment requires sealedDD20 and configuredDD15')
    if previous['guard_fields']['policy'] != 'b4':
        raise ValueError('Sealed B4 reference required')
    changed = {k for k in GUARD_FIELDS if configured_fields[k] != previous['guard_fields'][k]}
    if changed != {DD_FIELD}:
        raise ValueError(f'Only the drawdown threshold may change, found:{sorted(changed)}')
    if (force_enabled != previous['force_close_enabled']
            or force_fraction != previous['force_close_fraction']):
        raise ValueError('Forced-close settings must remain identical to DD20')
    result = deepcopy(previous)
    result['guard_fields'][DD_FIELD] = THRESHOLD
    result['canonical_risk_configuration'][DD_FIELD] = THRESHOLD
    result['note'] = ('Threshold-only study: original canonical profile preserved except DD20->DD15, '
        'confirmed against current effective preset. Not historical broker/config provenance.')
    return result


def prepare(root):
    root = Path(root)
    protected = [REFERENCE, risk.REFERENCE, risk.LEGACY_RISK, risk.base.PARENT, risk.base.FIDELITY]
    if any(root.resolve() == p.resolve() or p.resolve() in root.resolve().parents for p in protected):
        raise ValueError('Never write inside sealed research references')
    if (root/'prepared.json').exists():
        verify_hashes(Path('.'), risk.base.READ(root/'protocol.json')['sources'])
        verify_hashes(root, risk.base.READ(root/'prepared.json')['files'])
        if risk.base.READ(root/'production-risk.json')['guard_fields'][DD_FIELD] != THRESHOLD:
            raise ValueError('Wrong frozen threshold on resume')
        return
    if root.exists() and any(p.name != 'run.lock' for p in root.iterdir()):
        raise ValueError('Fresh output required')

    old = risk.base.READ(REFERENCE/'protocol.json')
    verify_hashes(Path('.'), old['sources'])
    review = risk.base.READ(REFERENCE/'final-review.json')
    if review['status'] != 'PASS_COMPLETED_RISK_GRID_REVIEW' or review['annual_cases'] != 576:
        raise ValueError('Completed corrected DD20 reference required')
    verify_hashes(REFERENCE, review['files'])
    report = risk.base.READ(REFERENCE/'report.json')
    if report['completed'] != 576 or report['failed'] or len(report['cases']) != 576:
        raise ValueError('Complete DD20 cases required')
    if {r['case'] for r in report['cases']} != {risk.base.case_key(c) for c in risk.base.cases()}:
        raise ValueError('Reference cases must exactly match the whole grid')
    for row in report['cases']:
        if row['audit']['status'] != 'PASS_PRODUCTION_RISK_CASH_EXITS':
            raise ValueError('Reference case risk audit required')
        verify_hashes(REFERENCE/'cases'/row['case'], row['files'])
    ready = risk.base.READ(REFERENCE/'prepared.json')
    verify_hashes(REFERENCE, ready['files'])

    # Capture and verify the settings bytes used to resolve the effective preset.
    config_files = [Path('config.yaml'), Path('config/capital_presets.yaml')]
    config_hashes = {str(p): digest(p) for p in config_files}
    cfg = load_risk_config(equity=4000., preset_key='capital_2001_5000')
    section = load_config()['risk_management']
    verify_hashes(Path('.'), config_hashes)
    profile = threshold_profile(risk.base.READ(REFERENCE/'production-risk.json'),
        {f: getattr(cfg, f) for f in GUARD_FIELDS},
        section['prod_force_close_on_breaker'], section['prod_force_close_pct'])

    sources = dict(old['sources'])
    names = [Path(__file__), Path('tests/test_us_intraday_protection_grid_dd15.py')]
    names += [REFERENCE/n for n in ['protocol.json', 'prepared.json', 'report.json', 'final-review.json']]
    sources.update({str(p): digest(p) for p in names})
    sources.update(config_hashes)
    protocol = deepcopy(old)
    protocol.pop('supersedes_partial_run', None)
    protocol.pop('numeric_fix', None)  # same repaired numeric engine, not another repair
    protocol.update(created_at_utc=datetime.now(timezone.utc).isoformat(), sources=sources,
        production_risk=profile, paired_risk_reference=str(REFERENCE),
        variant='PRODUCTION_COMPONENTS_B4_DD15_VS_DD20_NOT_FULL_LIVE',
        hypothesis='Earlier DD15 intervention vs DD20, not a guaranteed15% maximum drawdown.',
        comparison_change=['production_risk.guard_fields.max_portfolio_drawdown_pct:0.20->0.15'],
        unchanged=('All sealed DD20 data, cohort, prior regimes, sizing/entry/exit policies, leverage1x, '
            'fees/borrow/financing/force-close/recovery/streak and repaired B4 numeric code identical. '
            'All576cases rerun; no mixed results or new model selection.'),
        configuration_origin=dict(preset_key='capital_2001_5000', equity=4000.,
            effective_max_portfolio_drawdown_pct=THRESHOLD, fingerprint=cfg.fingerprint,
            files=config_hashes, other_guard_fields_identical_to_dd20=True),
        production_findings=[s.replace('hard20%DD', 'hard15%DD') for s in old['production_findings']],
        full_live_parity=False)
    root.mkdir(parents=True, exist_ok=True)
    atomic_json(root/'protocol.json', protocol)
    for name, expected in ready['files'].items():
        if name != 'production-risk.json':
            shutil.copyfile(REFERENCE/name, root/name)
            if digest(root/name) != expected:
                raise ValueError('Threshold experiment changed a frozen data input')
    atomic_json(root/'production-risk.json', profile)
    hashes = dict(ready['files']); hashes['production-risk.json'] = digest(root/'production-risk.json')
    atomic_json(root/'prepared.json', dict(files=hashes, paired_dd20_reference=str(REFERENCE),
        data_files_identical_to_reference=[n for n in hashes if n != 'production-risk.json'],
        only_profile_change=DD_FIELD, sessions=ready['sessions'], missing_regime=ready['missing_regime']))


def comparison(root, reports):
    ORIGINAL_COMPARISON(root, reports)  # keep the same no-B4 baseline too
    previous = {r['case']: r for r in risk.base.READ(REFERENCE/'report.json')['cases']}
    columns = ['return_pct', 'max_drawdown_pct', 'final_capital_usd', 'net_pnl_usd',
        'win_rate_pct', 'trades', 'winners', 'losers', 'avg_win_usd', 'avg_loss_usd',
        'avg_winner_holding_sessions', 'avg_loser_holding_sessions',
        'mean_capital_used_usd', 'mean_capital_used_pct_equity', 'open_positions', 'unrealized_pnl_usd']
    rows = []
    for r in reports:
        if r['status'] != 'COMPLETED_EXPLORATORY':
            continue
        p = previous[r['case']]
        row = {k: r[k] for k in ['case', 'year', 'side', 'sl', 'trailing', 'horizon', 'tp']}
        for key in columns:
            row[key+'_dd15'] = r[key]; row[key+'_dd20'] = p[key]
            row[key+'_delta_dd15_minus_dd20'] = r[key]-p[key]
        for key in ['risk_trips', 'forced_exits', 'degraded_sessions', 'daily_loss_observations']:
            row[key+'_dd15'] = r['audit'][key]; row[key+'_dd20'] = p['audit'][key]
        rows.append(row)
    pd.DataFrame(rows).to_csv(Path(root)/'comparison-dd15-vs-dd20.csv', index=False)


def run(root, workers=2, smoke=False):
    # Parent-process orchestration only. Workers import the unchanged DD20
    # ledger and read the DD15 profile from this run's sealed files.
    previous_prepare, previous_comparison = risk.prepare, risk.comparison
    risk.prepare, risk.comparison = prepare, comparison
    try:
        report = risk.run(root, workers=workers, smoke=smoke)
    finally:
        risk.prepare, risk.comparison = previous_prepare, previous_comparison
    root = Path(root)
    verify_hashes(Path('.'), risk.base.READ(root/'protocol.json')['sources'])
    if report['status'] == 'COMPLETED_EXPLORATORY':
        compared = pd.read_csv(root/'comparison-dd15-vs-dd20.csv')
        if len(compared) != 576 or compared['case'].duplicated().any():
            raise ValueError('Whole paired DD15/DD20 comparison required')
        atomic_json(root/'threshold-review.json', dict(status='PASS_DD15_VS_DD20_GRID_REVIEW',
            annual_cases=576, drawdown_threshold=THRESHOLD, reference_threshold=.20,
            full_live_parity=False, independent_human_review=False,
            files={n: digest(root/n) for n in ['protocol.json', 'prepared.json', 'production-risk.json',
                'report.json', 'final-review.json', 'annual-summary.csv',
                'comparison-risk-vs-baseline.csv', 'comparison-dd15-vs-dd20.csv']}))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--phase', choices=['prepare', 'run'], default='run')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--smoke', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.workers <= 4:
        raise ValueError('Use1..4local workers')
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if args.phase == 'prepare':
        prepare(args.output)
    else:
        run(args.output, args.workers, args.smoke)


if __name__ == '__main__':
    main()
