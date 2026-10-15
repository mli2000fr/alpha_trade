"""Versioned technical parity correction: use the native 3% entry-gap function.

The v1 result and code stay unchanged. Ratios versus price differences can fall
on opposite sides of a floating-point boundary (6 -> 6.18). Apply the native
function over every historical candidate, never a tuned tolerance or threshold.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from backtesting.microstructure import should_skip_entry_for_gap
from scripts.research import us_oracle_path_profit_tp15_sl7_dataset as base


ORIGINAL_QUALIFY=base.qualify_path
ORIGINAL_FREEZE=base.freeze
PREVIOUS=Path('artifacts/research/us_oracle_path_profit_filter/20261015-tp15-sl7-dataset-v1')


def qualify_path(grid,j,days,symbol,registry):
    reason=ORIGINAL_QUALIFY(grid,j,days,symbol,registry)
    if reason not in ('','NO_FILL_ENTRY_GAP'):
        return reason
    rejected=should_skip_entry_for_gap(float(grid.close.iloc[j]),float(grid.open.iloc[j+1]),max_gap_pct=.03)
    return 'NO_FILL_ENTRY_GAP' if rejected else ''


def freeze(output):
    marker=output/'protocol.json'
    if marker.exists():
        p=ORIGINAL_FREEZE(output)
        if p.get('technical_correction',{}).get('rule')!='native_should_skip_entry_for_gap':
            raise ValueError('Wrong version of gap qualification')
        return p
    p=ORIGINAL_FREEZE(output)
    for path in [Path(__file__),Path('tests/test_us_oracle_path_profit_tp15_sl7_native_gap.py'),
                 PREVIOUS/'report.json',PREVIOUS/'completion-audit.json']:
        p['sources'][str(path)]=base.digest(path)
    p['technical_correction']=dict(rule='native_should_skip_entry_for_gap',threshold=.03,
        all_candidates=True,epsilon_added=False,coverage_gate_changed=False,
        observed_case='CUK 2022-10-03 close6.00 -> next open6.18: native allows exact3pct',
        previous_dataset=str(PREVIOUS),previous_artifacts_modified=False)
    base.atomic_json(marker,p);return p


def run(output):
    output=Path(output)
    if output.resolve()==PREVIOUS.resolve():raise ValueError('Never overwrite the v1 result')
    previous_q,previous_f=base.qualify_path,base.freeze
    try:
        base.qualify_path,base.freeze=qualify_path,freeze
        return base.run(output)
    finally:
        base.qualify_path,base.freeze=previous_q,previous_f


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    # Keep unit cash-flow details in artifacts, without noisy per-trade console logs.
    logging.getLogger('backtesting.simulator').setLevel(logging.WARNING)
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('Network forbidden in native gap parity research')
    requests.Session.request=forbidden
    with base.plan.original.exclusive_run(args.output):
        try:print(json.dumps(run(args.output),default=str))
        except Exception as exc:
            base.atomic_json(args.output/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)));raise
