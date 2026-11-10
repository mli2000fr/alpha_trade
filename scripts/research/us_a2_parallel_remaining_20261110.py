"""Run the two pending cost stresses alongside the existing two replay workers.

The frozen replay's exclusive result-directory creation arbitrates ownership.
The old coordinator can encounter only an already-owned output directory for
these cases; preserve its receipts and reconcile after that coordinator exits.
No frozen replay source or inputs are changed.
"""
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from multiprocessing import get_context
from pathlib import Path
import json
import time

import psutil

from scripts.research import us_a2_top20pct_economic_20261109 as campaign


ROOT = campaign.ROOT
EXTRA = ('A2_COST25', 'OPEN_COMMON_COST25')
OLD_PID = 50616
OLD_CREATED = 1794264525.9008749


def old_alive():
    try:
        return abs(psutil.Process(OLD_PID).create_time() - OLD_CREATED) < .01
    except psutil.NoSuchProcess:
        return False


def update(status, **fields):
    campaign.atomic_json(ROOT / 'parallel-progress.json', dict(
        status=status, extra_cases=list(EXTRA), original_coordinator_pid=OLD_PID,
        updated_at_utc=datetime.now(timezone.utc).isoformat(), **fields))


def run():
    receipt = ROOT / 'parallel-launch.json'
    with receipt.open('x', encoding='utf-8') as stream:
        json.dump(dict(extra_cases=list(EXTRA), original_coordinator_pid=OLD_PID,
                       original_coordinator_created=OLD_CREATED,
                       ownership='Exclusive result directory; never replace an existing result',
                       requested_at_utc=datetime.now(timezone.utc).isoformat()), stream, indent=2)
    results, failures = [], []
    update('STARTING_TWO_EXTRA_WORKERS')
    with ProcessPoolExecutor(max_workers=2, mp_context=get_context('spawn')) as pool:
        tasks = {pool.submit(campaign.replay, str(ROOT), name): name for name in EXTRA
                 if not (ROOT / 'cases' / name / 'result').exists()}
        for task in as_completed(tasks):
            try:
                results.append(task.result())
            except Exception as exc:
                # A concurrent original worker may acquire the same directory
                # first. Its run owns that case and must be awaited, not retried.
                if not isinstance(exc, FileExistsError):
                    failures.append(dict(profile=tasks[task], error_type=type(exc).__name__, error=str(exc)))
            update('EXTRA_WORKERS_RUNNING', results=results, failures=failures)
    update('WAITING_ORIGINAL_COORDINATOR', results=results, failures=failures)
    while old_alive():
        time.sleep(10)
    # The original coordinator has now finished writing global metadata.
    for name in ('progress.json', 'report.json'):
        path = ROOT / name
        if path.exists():
            target = ROOT / ('original-coordinator-' + name)
            with target.open('xb') as stream:
                stream.write(path.read_bytes())
    collected, incomplete = [], []
    for name in campaign.CASES:
        folder = ROOT / 'cases' / name
        progress = campaign.read(folder / 'progress.json') if (folder / 'progress.json').exists() else {}
        isolation = campaign.read(folder / 'isolation.json') if (folder / 'isolation.json').exists() else {}
        if (progress.get('status') != 'COMPLETED_EXPLORATORY'
                or isolation.get('status') != 'COMPLETED'
                or not (folder / 'result' / 'report.json').exists()):
            incomplete.append(dict(profile=name, progress=progress, isolation_status=isolation.get('status')))
        else:
            collected.append(dict(profile=name, folder=str(folder), ihm_run_id=progress['ihm_run_id']))
    if incomplete:
        terminal = dict(status='INCOMPLETE_CASES', results=collected, failures=incomplete,
                        acceleration_errors=failures)
        campaign.atomic_json(ROOT / 'report.json', terminal)
        campaign.atomic_json(ROOT / 'progress.json', terminal)
        update('INCOMPLETE_CASES', failures=incomplete)
        return
    if not (ROOT / 'comparison.csv').exists():
        campaign.finalize(ROOT, collected)
    update('COMPLETED_EXPLORATORY', results=collected, acceleration_errors=failures,
           original_coordinator_receipts_preserved=True)


if __name__ == '__main__':
    try:
        run()
    except Exception as exc:
        update('PARALLEL_COORDINATOR_FAILED', error_type=type(exc).__name__, error=str(exc))
        raise
