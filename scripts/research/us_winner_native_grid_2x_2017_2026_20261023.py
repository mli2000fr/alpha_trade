"""Paired 2x-cap grid, process-local adapter; sealed 1x sources stay untouched."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import argparse
import logging
import shutil
import time

import numpy as np
import pandas as pd

from scripts.research import us_winner_native_grid_2017_2026_20261023 as grid

REFERENCE = grid.ROOT
ROOT = Path('artifacts/research/us_winner_native_grid_2017_2026/20261023-2x-v1')
DOC = Path('doc/ml/winner_grille_native_2x_2017_2026_protocole_20261023.md')
ORIGINAL_PREPARE, ORIGINAL_SNAPSHOT = grid.prepare, grid.snapshot
ORIGINAL_CONFIG, ORIGINAL_WORKER = grid.configuration, grid.worker
ORIGINAL_METRICS, ORIGINAL_LOAD = grid.metrics, grid.load_year
ORIGINAL_AGGREGATE = grid.aggregate


def configuration_2x(protocol, year, profile, smoke=False):
    cfg = ORIGINAL_CONFIG(protocol, year, profile, smoke=smoke)
    # No doubling of per-trade risk, position/sector caps or quantities.
    lev = replace(cfg.exec_config.leverage, enabled=True, mode='regt_swing',
                  max_leverage=2., dry_run_simulated_leverage=2.)
    execution = replace(cfg.exec_config, account_type='margin', leverage=lev,
                        simulated_margin_buying_power_multiplier=2.)
    return replace(cfg, risk_config=replace(cfg.risk_config, max_gross_exposure=2.), exec_config=execution)


def prepare_2x(root):
    reference = grid.base.read(REFERENCE/'protocol.json')
    grid.base.verify(reference['sources'])
    original_save = grid.base.save_new
    def seal(path, value):
        if Path(path).name == 'protocol.json':
            if value['profiles'] != reference['profiles'] or value['years'] != reference['years']:
                raise ValueError('Paired reference grid differs')
            if value['reference_config'] != reference['reference_config']:
                raise ValueError('Frozen risk/sizing reference differs')
            value['reference_config'] = deepcopy(value['reference_config'])
            value['reference_config']['risk']['max_gross_exposure'] = 2.
            value['reference_config']['effective_gross_cap'] = 2.
            value.update(effective_gross_cap=2., reference_grid=str(REFERENCE),
                leverage_amendment='Max gross exposure 1->2, native margin buying power capped2. '
                    'Risk per trade, sizing, HALF, max positions/sector and B4 unchanged; no forced2x.',
                actual_utilization_reported=True, extra_provider_calls=0, extra_SQL_reads=0,
                input_policy='Byte-identical sealed annual snapshots reused from reference; wait if not available.')
            extra=[Path(__file__),DOC,Path('tests/test_us_winner_native_grid_2x_2017_2026_20261023.py'),
                   REFERENCE/'protocol.json']
            value['sources'].update({str(x):grid.base.digest(x) for x in extra})
        return original_save(path, value)
    grid.base.save_new = seal
    try:
        p = ORIGINAL_PREPARE(root)
        if p['effective_gross_cap'] != 2. or p.get('reference_grid') != str(REFERENCE):
            raise ValueError('Not the frozen 2x protocol')
        return p
    finally:
        grid.base.save_new = original_save


def reference_failure(year):
    progress = grid.base.read(REFERENCE/'progress.json')
    for error in progress.get('errors', []):
        if error.get('year') == year:
            return str(error)
    if progress.get('status') in ('FAILED','PARTIAL_FAILED','COMPLETED_AUDITED_EXPLORATORY'):
        return 'Reference terminal before the required snapshot was sealed'
    return None


def snapshot_from_reference(root, year):
    folder = Path(root)/'inputs'/str(year)
    if (folder/'snapshot.json').exists():
        m = grid.base.read(folder/'snapshot.json')
        grid.base.verify({str(folder/n):v for n,v in m['files'].items()})
        return
    source = REFERENCE/'inputs'/str(year)
    while not (source/'snapshot.json').exists():
        failure = reference_failure(year)
        if failure:raise RuntimeError('Paired input unavailable: '+failure)
        grid.atomic_json(Path(root)/'progress.json',dict(status='WAITING_REFERENCE_SNAPSHOT',year=year,
            reference_grid=str(REFERENCE),total_runs=3000,
            completed_runs=len(list((Path(root)/'cases').glob('*/report.json')))))
        time.sleep(5)
    manifest = grid.base.read(source/'snapshot.json')
    grid.base.verify({str(source/n):sha for n,sha in manifest['files'].items()})
    folder.mkdir(parents=True,exist_ok=True)
    for name, sha in manifest['files'].items():
        if Path(name).name != name:raise ValueError('Unsafe snapshot member path')
        target=folder/name
        if target.exists():grid.base.verify({str(target):sha})
        else:
            shutil.copyfile(source/name,target)
            grid.base.verify({str(target):sha})
    # The manifest is copied only after every sealed member is verified.
    shutil.copyfile(source/'snapshot.json',folder/'snapshot.json')
    grid.base.save_new(folder/'paired-copy-audit.json',dict(status='PASS_BYTE_IDENTICAL_REFERENCE_INPUTS',
        source=str(source),source_snapshot_sha256=grid.base.digest(source/'snapshot.json'),
        files=manifest['files'],extra_SQL_reads=0,extra_provider_calls=0,
        copied_at_utc=datetime.now(timezone.utc).isoformat()))


def load_paired_year(root, year):
    result=ORIGINAL_LOAD(root,year)
    reference=REFERENCE/'inputs'/str(year)/'qualified-signals.parquet'
    while not reference.exists():
        failure=reference_failure(year)
        if failure:raise RuntimeError('Reference cohort missing: '+failure)
        time.sleep(2)
    pd.testing.assert_frame_equal(pd.read_parquet(reference), result[0], check_exact=True)
    target=Path(root)/'inputs'/str(year)/'paired-cohort-audit.json'
    if not target.exists():
        grid.base.save_new(target,dict(status='PASS_EXACT_SAME_COHORT_AND_RANKS',
            reference_sha256=grid.base.digest(reference),
            paired_sha256=grid.base.digest(Path(root)/'inputs'/str(year)/'qualified-signals.parquet')))
    return result


def exposure_metrics(curve):
    ratio=curve.gross/curve.equity
    if not np.isfinite(ratio).all() or curve.equity.le(0).any():
        raise ValueError('Equity/exposure ratio cannot be qualified')
    borrowed=(curve.gross-curve.equity).clip(lower=0)
    return dict(maximum_gross_equity_ratio=float(ratio.max()),
        fraction_bars_above_1x=float(ratio.gt(1.+1e-9).mean()),
        average_borrowed_capital=float(borrowed.mean()), maximum_borrowed_capital=float(borrowed.max()),
        utilization_note='Actual 5m gross/equity, not configured buying power; HALF and native sizing retained.')


def metrics_2x(result, initial):
    return ORIGINAL_METRICS(result, initial) | exposure_metrics(result.intraday_equity_curve)


def leveraged_worker(root, year, smoke=False):
    with adapter():
        return ORIGINAL_WORKER(root,year,smoke=smoke)


def paired_comparison(root):
    rows=[]
    for f in sorted((Path(root)/'cases').glob('*/report.json')):
        other=REFERENCE/'cases'/f.parent.name/'report.json'
        if not other.exists():continue
        new=grid.base.read(f);old=grid.base.read(other)
        grid.base.verify({str(f.parent/k):v for k,v in new['files'].items()})
        grid.base.verify({str(other.parent/k):v for k,v in old['files'].items()})
        if new['eligible_signals']!=old['eligible_signals']:raise ValueError('Unpaired candidate cohort')
        row=dict(year=new['year'],profile=new['profile'],
            return_1x_pct=old['return_pct'],return_2x_pct=new['return_pct'],return_delta_pp=new['return_pct']-old['return_pct'],
            dd_1x_magnitude_pct=-old['max_drawdown_pct'],dd_2x_magnitude_pct=-new['max_drawdown_pct'],
            mean_capital_1x=old['average_gross_capital'],mean_capital_2x=new['average_gross_capital'],
            mean_exposure_1x=old['average_gross_equity_ratio'],mean_exposure_2x=new['average_gross_equity_ratio'],
            peak_exposure_2x=new['maximum_gross_equity_ratio'],
            fraction_bars_above_1x=new['fraction_bars_above_1x'],
            interest_1x=old['margin_interest'],interest_2x=new['margin_interest'])
        rows.append(row)
    pd.DataFrame(rows).to_csv(Path(root)/'paired-1x-2x.partial.csv',index=False)
    if len(rows)==3000:
        pd.DataFrame(rows).to_csv(Path(root)/'paired-1x-2x.csv',index=False)
    return len(rows)


def aggregate_2x(root):
    top=ORIGINAL_AGGREGATE(root)
    count=paired_comparison(root)
    grid.atomic_json(Path(root)/'paired-comparison-status.json',dict(paired_cases=count,total_cases=3000,
        complete=count==3000,reference_grid=str(REFERENCE)))
    return top


@contextmanager
def adapter():
    names=dict(prepare=prepare_2x,snapshot=snapshot_from_reference,configuration=configuration_2x,
        worker=leveraged_worker,metrics=metrics_2x,load_year=load_paired_year,aggregate=aggregate_2x)
    old={k:getattr(grid,k) for k in names}
    for name,value in names.items():setattr(grid,name,value)
    try:yield
    finally:
        for name,value in old.items():setattr(grid,name,value)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','smoke','run'],default='run')
    parser.add_argument('--output',type=Path,default=ROOT)
    parser.add_argument('--workers',type=int,choices=[1,2],default=2)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    with grid.run_lock(args.output), adapter():
        if args.phase=='prepare':prepare_2x(args.output)
        else:grid.run(args.output,workers=args.workers,smoke=args.phase=='smoke')


if __name__=='__main__':main()
