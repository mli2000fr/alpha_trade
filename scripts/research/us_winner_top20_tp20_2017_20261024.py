"""Matched TP20 versus no-TP replay, same TOP20/2017 capacity experiment."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import logging

import pandas as pd

from scripts.research import us_winner_top20_capacity_2017_20261024 as capacity

ROOT = Path('artifacts/research/us_winner_top20_tp20_2017/20261024-v1')
BASELINE = capacity.ROOT
DOC = Path('doc/ml/winner_top20_tp20_2017_protocole_20261024.md')
TEST = Path('tests/test_us_winner_top20_tp20_2017_20261024.py')
PROFILE = dict(capacity.PROFILE, name='SL5_TROFF_H20_TP20', take_profit_pct=.20)


@contextmanager
def replay_context():
    """Process-local parameters; never edit the sealed predecessor or production."""
    original_root, original_profile = capacity.ROOT, capacity.PROFILE
    capacity.ROOT, capacity.PROFILE = ROOT, PROFILE
    try:
        yield
    finally:
        capacity.ROOT, capacity.PROFILE = original_root, original_profile


def prepare():
    if (ROOT/'protocol.json').exists():
        p = capacity.read_json(ROOT/'protocol.json')
        capacity.grid.base.verify(p['sources'])
        return p
    p = deepcopy(capacity.read_json(BASELINE/'protocol.json'))
    capacity.grid.base.verify(p['sources'])
    baselines = {}
    for arm in capacity.ARMS:
        path = BASELINE/arm/'report.json'
        report = capacity.read_json(path)
        if not report['status'].startswith('COMPLETED') or report['audit']['status'] != 'PASS_SCALAR_EXITS_CASH_FEES_AND_ENTRIES':
            raise ValueError('A completed audited no-TP counterpart is required: '+arm)
        capacity.grid.base.verify({str(path.parent/n): v for n, v in report['files'].items()})
        if report['policy']['take_profit_pct'] is not None:
            raise ValueError('Counterpart must have no price TP')
        baselines[arm] = str(path)
        p['sources'][str(path)] = capacity.grid.base.digest(path)
    paths = [Path(__file__), DOC, TEST, BASELINE/'protocol.json',
             Path('scripts/research/us_winner_top20_capacity_2017_20261024.py')]
    p['sources'].update({str(path): capacity.grid.base.digest(path) for path in paths})
    p.update(created_at_utc=datetime.now(timezone.utc).isoformat(),
        experiment='TOP20_2017_ADD_TP20_ONLY', profiles=[PROFILE], no_tp_baselines=baselines,
        sole_change_from_no_tp='take_profit_pct: null -> 0.20', total_runs=2,
        comparison_is_post_hoc=True, independent_holdout=False)
    p['requested_changes'] = dict(p['requested_changes'], take_profit_pct=.20)
    ROOT.mkdir(parents=True, exist_ok=True)
    capacity.grid.base.save_new(ROOT/'protocol.json', p)
    capacity.grid.atomic_json(ROOT/'progress.json', dict(status='PREPARED', completed_runs=0, total_runs=2))
    return p


def comparison_rows(baselines, reports):
    rows, deltas = [], []
    for arm in capacity.ARMS:
        old, new = baselines[arm], reports[arm]
        for tag, report in [('NO_TP', old), ('TP20', new)]:
            rows.append(dict(variant=tag, **{k: v for k, v in report.items() if not isinstance(v, (dict, list))}))
        deltas.append(dict(arm=arm, return_delta_pp=new['return_pct']-old['return_pct'],
            drawdown_delta_pp=new['max_drawdown_pct']-old['max_drawdown_pct'],
            final_equity_delta=new['final_equity']-old['final_equity'],
            average_gross_capital_delta=new['average_gross_capital']-old['average_gross_capital'],
            win_rate_delta_pp=(new['win_pct']-old['win_pct']) if new['win_pct'] is not None and old['win_pct'] is not None else None))
    return rows, deltas


def run():
    ROOT.mkdir(parents=True, exist_ok=True)
    try:
        with capacity.grid.run_lock(ROOT), capacity.safe_reads(), replay_context():
            protocol = prepare()
            if (ROOT/'report.json').exists():
                return
            import requests
            def forbidden(*_args, **_kwargs):
                raise RuntimeError('No SQL/provider/broker requests in this replay')
            requests.Session.request = forbidden
            capacity.grid.atomic_json(ROOT/'progress.json', dict(status='READING_FROZEN_INPUTS', completed_runs=0, total_runs=2))
            inputs = capacity.load_inputs()
            reports = {arm: capacity.run_arm(protocol, arm, inputs) for arm in capacity.ARMS}
            baselines = {arm: capacity.read_json(path) for arm, path in protocol['no_tp_baselines'].items()}
            rows, deltas = comparison_rows(baselines, reports)
            pd.DataFrame(rows).to_csv(ROOT/'comparison.csv', index=False)
            pd.DataFrame(deltas).to_csv(ROOT/'paired-deltas.csv', index=False)
            capacity.grid.base.verify(protocol['sources'])
            capacity.grid.base.save_new(ROOT/'report.json', dict(status='COMPLETED_AUDITED_EXPLORATORY',
                comparison=rows, paired_deltas=deltas, independent_holdout=False,
                full_live_parity=False, future_coverage_selection_bias=True,
                files={name: capacity.grid.base.digest(ROOT/name) for name in ['comparison.csv', 'paired-deltas.csv']}))
            capacity.grid.atomic_json(ROOT/'progress.json', dict(status='COMPLETED_AUDITED_EXPLORATORY', completed_runs=2, total_runs=2))
    except BaseException as exc:
        capacity.grid.atomic_json(ROOT/'progress.json', dict(status='FAILED', error_type=type(exc).__name__, error=str(exc)))
        raise


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    logging.basicConfig(level=logging.ERROR, force=True)
    run()
