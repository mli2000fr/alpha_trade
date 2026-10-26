"""Explicit human stop of the historical TOP10 1x grid, never operational batches."""
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import time

ROOT = Path(__file__).resolve().parents[2]
GRID = ROOT/'artifacts/research/us_winner_native_grid_2017_2026/20261023-v1'
RECEIPT = ROOT/'artifacts/operations/winner-stop-top10-1x-20261026-v1'
LEGACY = 'scripts.research.us_winner_legacy_resume_20261024'
TARGETS = {'scripts.research.us_winner_grid_supervisor_repair_20261023',
           'scripts.research.us_winner_cent_qualification_20261024'}


def flag(command, name):
    return command[command.index(name)+1] if name in command and command.index(name)+1 < len(command) else None


def role(command):
    module = flag(command, '-m')
    if module == 'scripts.research.us_winner_stop_2x_20261026' and flag(command, '--phase') == 'supervise':
        return '1x_supervisor'
    if module == LEGACY and flag(command, '--kind') == '1x' and flag(command, '--target') in TARGETS:
        return '1x_worker' if flag(command, '--phase') in ('year', 'resume', 'qualify') else '1x_supervisor'
    if module == 'scripts.research.us_winner_native_grid_2017_2026_20261023':
        output = flag(command, '--output')
        if output and Path(output).resolve() != GRID.resolve():
            return None
        return '1x_worker'
    return None


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.stop-1x.tmp')
    temporary.write_text(json.dumps(data, indent=2, default=str, allow_nan=False), encoding='utf-8')
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    import psutil
    if (RECEIPT/'stop-receipt.json').exists():
        raise ValueError('Stop already receipted; inspect before another action')
    RECEIPT.mkdir(parents=True, exist_ok=True)
    targets, untouched = [], []
    for process in psutil.process_iter(['pid', 'ppid', 'name', 'cmdline', 'create_time']):
        try:
            info = process.info
            command = info['cmdline'] or []
            selected = role(command)
            if not selected:
                if flag(command, '-m') == 'service.forward_pit.batch':
                    untouched.append(dict(pid=process.pid, batch=flag(command, '--batch')))
                continue
            if Path(process.cwd()).resolve() != ROOT:
                raise ValueError('Unexpected workspace for matching process')
            targets.append(dict(pid=process.pid, parent=info['ppid'], created=info['create_time'],
                                command=command, role=selected))
        except psutil.NoSuchProcess:
            continue
    before = {str(p.relative_to(ROOT)): sha(p) for p in (GRID/'cases').glob('*/report.json')}
    save(RECEIPT/'before-stop.json', dict(at_utc=datetime.now(timezone.utc).isoformat(),
                                         targets=targets, untouched_batches=untouched, reports=before))
    by_id = {item['pid'] for item in targets}
    targets.sort(key=lambda r: (r['role'] != '1x_supervisor', -int(r['parent'] in by_id)))
    stopped = []
    for item in targets:
        try:
            process = psutil.Process(item['pid'])
            if process.create_time() != item['created'] or role(process.cmdline()) != item['role']:
                raise ValueError('Process identity changed; stop aborted')
            process.terminate()
            try:
                process.wait(timeout=5)
            except psutil.TimeoutExpired:
                if process.create_time() != item['created']:
                    raise ValueError('PID reused during stop')
                process.kill()
                process.wait(timeout=5)
            stopped.append(item['pid'])
        except psutil.NoSuchProcess:
            stopped.append(item['pid'])
    time.sleep(.2)
    living = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            if role(p.info['cmdline'] or []):
                living.append(p.pid)
        except psutil.NoSuchProcess:
            pass
    if living:
        raise ValueError(f'Matching grid processes remain: {living}')
    for name, expected in before.items():
        if sha(ROOT/name) != expected:
            raise ValueError('Existing completed report changed during stop: '+name)
    request = dict(status='STOPPED_BY_USER', kind='1x', at_utc=datetime.now(timezone.utc).isoformat(),
                   reason='Human requested stop of TOP10 grid without leverage',
                   automatic_resume_authorized=False, completed_results_preserved=True)
    save(GRID/'user-stop.json', request)
    progress = json.loads((GRID/'progress.json').read_text(encoding='utf-8'))
    reports = list((GRID/'cases').glob('*/report.json'))
    counts = {}
    for path in reports:
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('status') == 'COMPLETED_EXPLORATORY':
            year = str(report['year'])
            counts[year] = counts.get(year, 0)+1
    save(GRID/'progress.json', {**progress, **request, 'completed_runs': sum(counts.values()),
         'completed_by_year': counts, 'active_years': {}, 'pending_years': [],
         'updated_at_utc': datetime.now(timezone.utc).isoformat()})
    for path in GRID.glob('year-*.json'):
        report = json.loads(path.read_text(encoding='utf-8'))
        if report.get('status') == 'RUNNING':
            save(path, {**report, **request, 'completed_runs': counts.get(str(report['year']), 0)})
    cents = ROOT/'artifacts/research/us_winner_cent_qualification/20261024-v1'
    for folder in cents.glob('1x-20*'):
        if (folder/'request.json').exists():
            save(folder/'user-stop.json', request)
    save(ROOT/'artifacts/operations/winner-stop-top10-2x-20261026-v1/progress-1x.json', request)
    result = dict(**request, terminated_pids=stopped, completed_reports_before=len(before),
                  completed_reports_after=len(reports), completed_by_year=counts,
                  existing_report_hashes_unchanged=True, no_output_deleted=True,
                  no_recursive_process_kill=True, untouched_batches=untouched)
    save(RECEIPT/'stop-receipt.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
