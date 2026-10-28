"""Recover ONE legacy options execution claim after the proven RiskDbIo pre-order crash.

GET broker + READ ONLY SQL + local archival; never run execution or delete history.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import uuid

from sqlalchemy import text

from service.options_directional.risk_attempts import risk_lock
from service.options_directional.store import directory, digest, write_new


def recover(run_id, log_path):
    import psutil
    from common.verified_http import verified_session
    from database.connection import get_sqlalchemy_engine
    from service.alpaca.accounts import AccountRegistry
    from service.alpaca.trading_client import AlpacaTradingClient

    folder = directory(run_id).resolve()
    read = lambda name: json.loads((folder/name).read_text(encoding='utf-8'))
    with risk_lock(folder, lock_name='execution.lock'):
        claim, report, binding, summary, seal = [read(n) for n in (
            'execution.claim.json', 'report.json', 'risk_binding.json', 'risk_summary.json', 'seal.json')]
        if claim.get('attempt_id') or (folder/'execution.result.json').exists():
            raise ValueError('Only an unresolved legacy claim can use this recovery')
        if (digest(report) != seal['report_sha256'] or binding['report_sha256'] != digest(report)
                or binding['summary_sha256'] != digest(summary) or binding['risk_run_id'] != summary['run_id']
                or summary.get('options_filter_run_id') != run_id or report['run_id'] != run_id
                or summary.get('run_mode') != 'paper' or report.get('account_id') != 'default'):
            raise ValueError('Invalid exact PAPER risk/filter binding')
        log = log_path.read_text(encoding='utf-8')
        if not all(needle in log for needle in (run_id, binding['risk_run_id'],
            'in _load_pre_submission_adv_vol', "ImportError: cannot import name 'RiskDbIo'")):
            raise ValueError('Required exact pre-order failure log missing')
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if str(proc.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe', 'python', 'python3'):
                continue
            args = proc.info['cmdline']
            if not isinstance(args, list):
                raise ValueError('Unreadable Python process; cannot establish execution is idle')
            if (any(Path(arg).name.lower() == 'run_execution.py' for arg in args[1:])
                    or 'service.options_directional.pipeline' in args[1:]):
                processes.append(proc.info['pid'])
        if processes:
            raise ValueError('An execution process is still active; no recovery')
        if AccountRegistry.get().resolve('default').mode != 'paper':
            raise ValueError('Principal account must be PAPER')
        engine = get_sqlalchemy_engine()
        if engine.url.database != 'alpha_trade':
            raise ValueError('Wrong SQL schema')
        counts = {}
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql("SET SESSION time_zone='+00:00'")
                conn.exec_driver_sql('START TRANSACTION READ ONLY')
                for table in ('execution_runs', 'execution_order_requests', 'execution_winner_campaigns'):
                    exists = conn.execute(text('SELECT COUNT(*) FROM information_schema.tables '
                        'WHERE table_schema=DATABASE() AND table_name=:table'), {'table': table}).scalar_one()
                    if not exists:
                        if table != 'execution_winner_campaigns':
                            raise ValueError('Required execution table unavailable')
                        counts[table] = 0
                    else:
                        counts[table] = conn.execute(text(f'SELECT COUNT(*) FROM {table} WHERE risk_run_id=:risk'),
                            {'risk': binding['risk_run_id']}).scalar_one()
                counts['active_account_locks'] = conn.execute(text('SELECT COUNT(*) FROM execution_locks '
                    "WHERE account_id='default' AND expires_at>UTC_TIMESTAMP()" )).scalar_one()
                conn.rollback()
        finally:
            engine.dispose()
        if any(counts.values()):
            raise ValueError('SQL execution evidence or account lock exists; outcome cannot be cleared')
        with verified_session() as session:
            broker = AlpacaTradingClient(broker_mode='paper', account_id='default', session=session)
            positions = broker.get_positions()
            orders = broker._request('GET', '/v2/orders', params=dict(status='all', after=claim['started_at'],
                limit=500, direction='asc', nested='true'))
            open_orders = broker.list_orders(status='open', limit=500)
            fills = broker._request('GET', '/v2/account/activities/FILL',
                params=dict(after=claim['started_at'], page_size=100, direction='asc'))
        # Strict zero permits no truncation, no round-trip fills and no unrelated
        # standing order which could make the recovery ambiguous.
        if any(not isinstance(v, list) or v for v in (positions, orders, open_orders, fills)):
            raise ValueError('Broker evidence nonempty/invalid; no recovery')
        if read('execution.claim.json') != claim:
            raise ValueError('Claim changed during checks')
        archive = folder/'execution_attempts'/('legacy-'+uuid.uuid4().hex)
        if not archive.resolve().is_relative_to(folder):
            raise ValueError('Archive outside exact options run')
        archive.mkdir(parents=True, exist_ok=False)
        proof = dict(run_id=run_id, risk_run_id=binding['risk_run_id'], account='default', broker_mode='paper',
            claim_sha256=digest(claim), report_sha256=digest(report), binding_sha256=digest(binding),
            checked_at_utc=datetime.now(timezone.utc).isoformat(), sql_counts=counts,
            broker_counts=dict(positions=0, orders_since_claim=0, open_orders=0, fills_since_claim=0),
            execution_processes=processes, error='ImportError RiskDbIo before executor/transition phase',
            log_sha256=hashlib.sha256(log_path.read_bytes()).hexdigest(), log_path=str(log_path),
            action='Archive legacy claim only; no execution launched')
        write_new(archive/'recovery_proof.json', proof)
        (folder/'execution.claim.json').rename(archive/'execution.claim.json')
        print(json.dumps(dict(status='RECOVERED', run_id=run_id, risk_run_id=binding['risk_run_id'],
            archive=str(archive), sql_counts=counts, broker_counts=proof['broker_counts'], execution_launched=False)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--failure-log', required=True, type=Path)
    args = parser.parse_args()
    recover(args.run_id, args.failure_log)
