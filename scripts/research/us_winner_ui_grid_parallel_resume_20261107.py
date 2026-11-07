"""Change only scheduler concurrency; reuse the sealed experiment and outputs."""
import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path

import psutil

from scripts.research.us_winner_ui_grid_20261107 import ROOT,read,digest,atomic_json


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--workers',type=int,default=8)
    args=parser.parse_args()
    if not 1<=args.workers<=min(12,psutil.cpu_count() or 1):
        parser.error('Workers must be between 1 and min(12, logical CPU count)')
    # Never have two coordinators write into the same case directories.
    ancestors={psutil.Process().pid,*[p.pid for p in psutil.Process().parents()]}
    for process in psutil.process_iter(['cmdline','name']):
        if process.pid in ancestors or 'python' not in str(process.info.get('name')).lower():continue
        command=process.info.get('cmdline')
        if command is None:
            raise RuntimeError(f'Cannot verify Python process {process.pid}; inspect before resuming')
        owns_grid=('scripts.research.us_winner_ui_grid_20261107' in command or
                   'scripts.research.us_winner_ui_grid_parallel_resume_20261107' in command)
        if owns_grid:
            raise RuntimeError(f'Another sweep coordinator is still running: {process.pid}')
    root=args.root
    initial={p.parent.name:digest(p) for p in (root/'cases').glob('*/report.json')}
    directory=root/'runtime-amendments';directory.mkdir(exist_ok=True)
    receipt=directory/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-workers.json')
    atomic_json(receipt,dict(reason='User requested more simultaneous simulations',workers=args.workers,
        original_frozen_workers=read(root/'protocol.json')['workers'],
        financial_protocol_sha256=digest(root/'protocol.json'),input_manifest_sha256=digest(root/'inputs/manifest.json'),
        completed_before_resume=initial,financial_parameters_changed=False,
        started_at_utc=datetime.now(timezone.utc).isoformat(),launcher_sha256=digest(__file__)))
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    from scripts.research.us_winner_ui_grid_20261107 import run
    run(root,args.workers)
    assert all(digest(root/'cases'/name/'report.json')==sha for name,sha in initial.items()),'Completed reports changed'
    print(json.dumps(dict(status='COMPLETED',workers=args.workers,previous_reports_unchanged=len(initial))))


if __name__=='__main__':main()
