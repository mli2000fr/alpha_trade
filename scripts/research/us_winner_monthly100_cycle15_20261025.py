"""Add ONE monthly100 account to the existing cycle15 TOP20 experiment.

Wait for its six sealed reference accounts, reuse their audited valuations,
then run the same native replay with a 100-return monthly selection window.
No second shadow series, SQL, providers, LLM or real broker orders.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import logging
import os
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd

from scripts.research import us_winner_monthly_cycle15_20261025 as cycle

study = cycle.study
BASE_RUN_CASE = study.run_case
PARENT = cycle.ROOT
ROOT = Path('artifacts/research/us_winner_monthly_selector/20261025-cycle15-pause3m-monthly100-v1')
ARM, WINDOW = 'MONTHLY_100', 100
SHADOWS = ['SHADOW_'+p['name'] for p in study.PROFILES]
DOC = Path('doc/ml/winner_monthly100_cycle15_pause3m_20261025.md')
TEST = Path('tests/test_us_winner_monthly100_cycle15_20261025.py')
TEST_RECEIPT = Path('artifacts/tests/winner-monthly100-cycle15-20261025/qualification.xml')


def validate_parent(protocol):
    policy = protocol['global_liquidation']
    if (protocol.get('variant') != 'cycle15_no_hard' or protocol.get('TOP') != 20
            or policy.get('cycle_drawdown_pct') != .15
            or policy.get('hard_drawdown_pct') is not None
            or policy.get('cooldown_calendar_months') != 3
            or policy.get('total_liquidation') is not True
            or policy.get('soft_partial_liquidation') is not False
            or protocol.get('effective_gross_cap') != 1.
            or protocol.get('effective_initial_fraction') != 1.
            or protocol.get('profiles') != study.PROFILES):
        raise ValueError('References are not the exact requested TOP20 cycle15/no-hard policy')


def prepare():
    base = study.capacity.grid.base
    if (ROOT/'protocol.json').exists():
        sealed = base.read(ROOT/'protocol.json'); base.verify(sealed['sources']); return sealed
    parent = base.read(PARENT/'protocol.json'); base.verify(parent['sources']); validate_parent(parent)
    suites = ET.parse(TEST_RECEIPT).getroot().findall('.//testsuite')
    tests = sum(int(s.attrib.get('tests',0)) for s in suites)
    bad = sum(int(s.attrib.get('failures',0))+int(s.attrib.get('errors',0))+int(s.attrib.get('skipped',0)) for s in suites)
    if tests < 20 or bad:
        raise ValueError('Passing monthly100 and cycle15 qualification receipt required')
    sources = dict(parent['sources'])
    for path in [Path(__file__),DOC,TEST,TEST_RECEIPT,PARENT/'protocol.json']:
        sources[str(path)] = base.digest(path)
    protocol = deepcopy(parent)
    protocol.update(experiment='TOP20_MONTHLY100_CYCLE15_PAUSE3M_NO_HARD',sources=sources,
        created_at_utc=datetime.now(timezone.utc).isoformat(),arms=[ARM],windows=[WINDOW],total_runs=1,
        predecessor=str(PARENT),predecessor_sha256=base.digest(PARENT/'protocol.json'),
        reused_shadow_root=str(PARENT),shadow_accounts=SHADOWS,new_shadow_accounts=0,
        validation_tests=tests,dependency='Wait for six audited shadow reports; never launch duplicate references',
        monthly_score='Exactly 100 prior official-session close-to-close returns, 101 valuations, including latent positions and fees',
        changed_parameter_only='Monthly lookback 30/50 -> 100; same parent policy, capital, TOP20 and sources',
        notes=['One new MONTHLY_100 account with 4000 USD; no annual/monthly recapitalization.',
            'Six identically governed shadow accounts reused; never pooled into the evaluated capital.',
            'No duplicate reference runs; the 30/50/fixed accounts remain owned by the parent worker.',
            'Lifetime losses remain visible even though the cycle drawdown resets after each pause.'],
        evaluation_start='2020-01-02',evaluation_end='2024-12-31',initial_equity=4000.,
        production_changed=False,SQL_reads=0,SQL_writes=False,provider_calls=0,LLM_calls=0,orders=False)
    ROOT.mkdir(parents=True,exist_ok=False)
    base.save_new(ROOT/'protocol.json',protocol)
    study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='PREPARED',completed_runs=0,total_runs=1))
    return protocol


def reference_state(parent=PARENT):
    """Completed reference subset is reusable even if a later parent arm fails."""
    ready = [arm for arm in SHADOWS if (parent/'cases'/arm/'report.json').exists()]
    missing = [arm for arm in SHADOWS if arm not in ready]
    progress = study.capacity.read_json(parent/'progress.json')
    if missing and progress.get('status') in ('FAILED','PARTIAL_FAILED','INCOMPLETE_COVERAGE'):
        raise RuntimeError('Reference collection failed; no automatic restart: '+str(progress))
    if missing and str(progress.get('status','')).startswith('COMPLETED'):
        raise RuntimeError('Parent marked complete but required shadow reports are missing')
    return ready,missing,progress


def wait_for_references():
    while True:
        ready,missing,progress = reference_state()
        if not missing:
            return
        study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='WAITING_FOR_REFERENCE_ACCOUNTS',
            completed_runs=0,total_runs=1,ready_references=len(ready),total_references=len(SHADOWS),
            missing_references=missing,parent_current_arm=progress.get('arm'),
            parent_completed_sessions=progress.get('completed_sessions'),
            parent_total_sessions=progress.get('total_sessions'),
            parent_updated_at_utc=progress.get('updated_at_utc'),
            updated_at_utc=datetime.now(timezone.utc).isoformat()))
        time.sleep(30)  # Worker dependency wait, not a second data collection.


def validate_curve(series, expected):
    dates = pd.DatetimeIndex(pd.to_datetime(series.index)).normalize()
    if dates.has_duplicates or not dates.equals(expected):
        raise ValueError('Reference curve must cover every exact official shadow session')
    if not np.isfinite(series.to_numpy(float)).all() or (series <= 0).any():
        raise ValueError('Nonpositive or invalid reference valuation')


def sealed_references(protocol):
    base = study.capacity.grid.base
    base.verify(protocol['sources'])
    parent = base.read(PARENT/'protocol.json'); validate_parent(parent)
    expected = pd.DatetimeIndex([pd.Timestamp(s.session_date) for s in study.inputs.sessions()
        if study.inputs.SHADOW_START <= s.session_date <= study.inputs.END])
    curves,receipts = {},{}
    for profile,arm in zip(study.PROFILES,SHADOWS):
        folder = PARENT/'cases'/arm
        report = base.read(folder/'report.json')
        if (report['status'] != 'COMPLETED_EXPLORATORY' or report['coverage_gaps']
                or report['audit']['status'] != 'PASS_CYCLE15_FULL_SALES_PAUSES_RESETS_CASH_FEES_ENTRIES'
                or report['start'] != str(study.inputs.SHADOW_START)
                or report['end'] != str(study.inputs.END) or report['initial_equity'] != 4000.):
            raise ValueError('Reference missing full audit/policy/calendar: '+arm)
        policy = report['global_liquidation']
        if (policy['hard_threshold_pct'] is not None or policy['cycle_threshold_pct'] != .15
                or policy['cooldown_months'] != 3 or policy['force_close_pct'] != 1. or policy['halted']):
            raise ValueError('Reference loss policy differs: '+arm)
        files = {str(folder/name):sha for name,sha in report['files'].items()}
        base.verify(files)
        daily = pd.read_parquet(folder/'equity-daily.parquet').iloc[:,0]
        validate_curve(daily,expected)
        curves[profile['name']] = daily
        receipts[arm] = dict(report=str(folder/'report.json'),report_sha256=base.digest(folder/'report.json'),files=files)
    receipt = dict(parent_protocol_sha256=base.digest(PARENT/'protocol.json'),references=receipts,
        reused_accounts=6,new_shadow_accounts=0,validated_at_utc=datetime.now(timezone.utc).isoformat())
    path = ROOT/'shadow-receipts.json'
    if path.exists():
        previous = base.read(path)
        if previous['references'] != receipts or previous['parent_protocol_sha256'] != receipt['parent_protocol_sha256']:
            raise ValueError('Immutable reference accounts changed on resume')
    else:
        base.save_new(path,receipt)
    return curves


def decisions_100(curves):
    choices = study.monthly_decisions(curves,WINDOW)
    if len(choices) != 60 or choices['2020-01']['cutoff'] != '2019-12-31':
        raise ValueError('Expected all 60 causal monthly decisions 2020-2024')
    if any(row['window'] != WINDOW or pd.Timestamp(row['available_at']) >= pd.Timestamp(row['effective_open'])
            for row in choices.values()):
        raise ValueError('Wrong window or future monthly information')
    return choices


@contextmanager
def single_account_scope():
    # cycle.installed supplies the EXACT same controller/config/audit and
    # restores every original component. Do not use its run_case wrapper,
    # whose audit folder intentionally points to the parent experiment.
    original_arms = study.ARMS
    original_folder = cycle.CURRENT_FOLDER
    with cycle.installed():
        study.ROOT,study.ARMS = ROOT,[ARM]
        cycle.CURRENT_FOLDER = ROOT/'cases'/ARM
        try:
            yield
        finally:
            study.ARMS = original_arms
            cycle.CURRENT_FOLDER = original_folder


def run():
    grid,base = study.capacity.grid,study.capacity.grid.base
    protocol = prepare()
    with grid.run_lock(ROOT):
        if (ROOT/'report.json').exists():
            return
        grid.atomic_json(ROOT/'process.json',dict(pid=os.getpid(),started_at_utc=datetime.now(timezone.utc).isoformat()))
        wait_for_references()
        grid.atomic_json(ROOT/'progress.json',dict(status='VERIFYING_SIX_SEALED_REFERENCES',completed_runs=0,total_runs=1))
        curves = sealed_references(protocol)
        decisions = decisions_100(curves)
        path = ROOT/'decisions-100.json'
        if path.exists():
            if base.read(path) != decisions:
                raise ValueError('Monthly100 decisions changed on resume')
        else:
            base.save_new(path,decisions)
        grid.atomic_json(ROOT/'progress.json',dict(status='VERIFYING_FROZEN_LOCAL_INPUTS',completed_runs=0,total_runs=1))
        tape = cycle.BASE_TAPE(cycle.INPUT_ROOT)
        start = min(s.session_date for s in study.inputs.sessions(start=study.inputs.START) if s.session_date >= study.inputs.START)
        with single_account_scope():
            summary = BASE_RUN_CASE(protocol,ARM,tape,
                lambda day:decisions[day.strftime('%Y-%m')]['profile'],start)
            annual = study.annual_results(ARM)
        if summary['status'] != 'COMPLETED_EXPLORATORY' or summary['coverage_gaps']:
            raise ValueError('Monthly100 replay incomplete')
        base.verify(protocol['sources'])
        # Re-verify all reused references after the account too.
        receipt = base.read(ROOT/'shadow-receipts.json')
        for item in receipt['references'].values():
            base.verify({item['report']:item['report_sha256'],**item['files']})
        pd.DataFrame(annual).to_csv(ROOT/'annual-summary.csv',index=False)
        base.save_new(ROOT/'report.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',
            window=WINDOW,monthly100=summary,annual=annual,parent_reference_root=str(PARENT),
            reused_shadows=6,new_shadow_accounts=0,sources=protocol['sources'],
            independent_holdout=False,future_coverage_selection_bias=True,full_live_parity=False,
            files={n:base.digest(ROOT/n) for n in ['shadow-receipts.json','decisions-100.json','annual-summary.csv']}))
        grid.atomic_json(ROOT/'progress.json',dict(status='COMPLETED_AUDITED_EXPLORATORY',completed_runs=1,total_runs=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','run'],default='run')
    args = parser.parse_args()
    os.environ['SSLKEYLOGFILE'] = ''
    if os.name == 'nt':
        import psutil
        psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    logging.basicConfig(level=logging.ERROR,force=True)
    import requests
    requests.Session.request = lambda *a,**k:(_ for _ in ()).throw(RuntimeError('No HTTP in monthly100 offline replay'))
    try:
        prepare() if args.phase == 'prepare' else run()
    except BaseException as exc:
        if ROOT.exists():
            study.capacity.grid.atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,
                error=str(exc),updated_at_utc=datetime.now(timezone.utc).isoformat()))
        raise


if __name__ == '__main__':
    main()
