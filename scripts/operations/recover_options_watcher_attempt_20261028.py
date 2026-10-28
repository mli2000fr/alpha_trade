"""One explicitly authorized recovery; fixed PAPER run, no orders or SQL writes.

This does not change automatic retry policy. It accepts only the known watcher
failure, verifies zero requests/plans and broker activity, then archives three
local attempt receipts under the exact filter's kernel lock. Never executes 12.
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

RUN = 'opt-917380c30aab40cbb99362b3ead15e7c'
RISK = '404615885b1041ac'
ATTEMPT = '65a1a0290ecb448584ce9479cff32243'
EXEC = '7246184a87924be8'
ERROR = 'Restart watcher: process predates the campaign implementation'
CLAIM_HASH = '473aee1a2f49ac42967e8d5114a94145eff61dd7f5ed5a3ea39708262c760193'
NAMES = (f'execution.effects_possible.{ATTEMPT}.json', 'execution.result.json', 'execution.claim.json')


def validate_proof(claim, result, effects, rows, counts, broker_counts):
    if (claim.get('run_id') != RUN or claim.get('risk_run_id') != RISK
            or claim.get('attempt_id') != ATTEMPT or digest(claim) != CLAIM_HASH
            or result.get('claim_sha256') != CLAIM_HASH or effects.get('claim_sha256') != CLAIM_HASH
            or result.get('attempt_id') != ATTEMPT or effects.get('attempt_id') != ATTEMPT
            or result.get('run_id') != RUN or result.get('risk_run_id') != RISK
            or effects.get('risk_run_id') != RISK or result.get('status') != 'CHILD_COMPLETED'):
        raise ValueError('Not the exact authorized historical attempt')
    expected = dict(exec_run_id=EXEC, risk_run_id=RISK, status='FAILED', error_message=ERROR,
        total_submitted=0, total_filled=0, account_id='default', broker_mode='paper')
    if len(rows) != 1 or any(rows[0].get(k) != v for k, v in expected.items()):
        raise ValueError('SQL run is not the exact pre-staging watcher failure')
    required_sql = {'order_requests', 'winner_campaigns', 'active_account_locks', 'active_execution_runs'}
    required_broker = {'positions', 'open_orders', 'orders_today', 'fills_today'}
    if set(counts) != required_sql or any(type(v) is not int or v != 0 for v in counts.values()):
        raise ValueError('SQL requests/plans/active execution evidence; no recovery')
    if set(broker_counts) != required_broker or any(type(v) is not int or v != 0 for v in broker_counts.values()):
        raise ValueError('Broker effects possible; no recovery')


def execution_processes():
    import psutil
    active = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if str(proc.info.get('name') or '').lower() not in ('python.exe', 'pythonw.exe', 'python', 'python3'):
            continue
        args = proc.info.get('cmdline')
        if not isinstance(args, list):
            raise ValueError('Unreadable Python process; no recovery')
        if any(Path(arg).name.lower() == 'run_execution.py' or arg == 'service.options_directional.pipeline'
               for arg in args[1:]):
            active.append(proc.pid)
    if active:
        raise ValueError(f'Execution process active: {active}; no recovery')
    return active


def recover(*, apply=False):
    from common.verified_http import verified_session
    from database.connection import get_sqlalchemy_engine
    from service.alpaca.accounts import AccountRegistry
    from service.alpaca.trading_client import AlpacaTradingClient

    folder = directory(RUN).resolve()
    read = lambda name: json.loads((folder/name).read_text(encoding='utf-8'))
    with risk_lock(folder, lock_name='execution.lock'):
        originals = {name: (folder/name).read_bytes() for name in NAMES}
        effects, result, claim = [read(name) for name in NAMES]
        report, binding, summary, seal = [read(name) for name in
            ('report.json', 'risk_binding.json', 'risk_summary.json', 'seal.json')]
        if (report.get('run_id') != RUN or report.get('account_id') != 'default'
                or report.get('trade_date') != '2026-10-27'
                or binding.get('risk_run_id') != RISK or summary.get('run_id') != RISK
                or summary.get('options_filter_run_id') != RUN or summary.get('run_mode') != 'paper'
                or digest(report) != seal['report_sha256'] or digest(report) != binding['report_sha256']
                or digest(summary) != binding['summary_sha256']
                or digest(report) != claim['report_sha256'] or digest(binding) != claim['binding_sha256']):
            raise ValueError('Altered exact PAPER filter/risk binding')
        execution_processes()
        if AccountRegistry.get().resolve('default').mode != 'paper':
            raise ValueError('Principal account is not PAPER')
        engine = get_sqlalchemy_engine()
        if engine.url.database != 'alpha_trade':
            raise ValueError('Wrong SQL schema')
        try:
            with engine.connect() as conn:
                conn.exec_driver_sql('START TRANSACTION READ ONLY')
                rows = [dict(r) for r in conn.execute(text('SELECT exec_run_id,risk_run_id,status,error_message,'
                    'total_submitted,total_filled,account_id,broker_mode FROM execution_runs WHERE risk_run_id=:risk'),
                    {'risk': RISK}).mappings()]
                counts = {'order_requests': int(conn.execute(text(
                    'SELECT COUNT(*) FROM execution_order_requests WHERE risk_run_id=:risk'), {'risk': RISK}).scalar_one()),
                    'active_account_locks': int(conn.execute(text("SELECT COUNT(*) FROM execution_locks "
                        "WHERE account_id='default' AND expires_at>CURRENT_TIMESTAMP()")).scalar_one()),
                    'active_execution_runs': int(conn.execute(text("SELECT COUNT(*) FROM execution_runs "
                        "WHERE account_id='default' AND status='RUNNING'")).scalar_one())}
                table_exists = conn.execute(text('SELECT COUNT(*) FROM information_schema.tables '
                    "WHERE table_schema=DATABASE() AND table_name='execution_winner_campaigns'")).scalar_one()
                # Any campaign for this account, not just this risk, blocks recovery.
                counts['winner_campaigns'] = int(conn.execute(text("SELECT COUNT(*) FROM execution_winner_campaigns "
                    "WHERE account_id='default'")).scalar_one()) if table_exists else 0
                conn.rollback()
        finally:
            engine.dispose()
        with verified_session() as session:
            broker = AlpacaTradingClient(broker_mode='paper', account_id='default', session=session)
            # Broader than the exact attempt: ALL activity since midnight UTC.
            after = '2026-10-28T00:00:00+00:00'
            responses = dict(positions=broker.get_positions(), open_orders=broker.list_orders(status='open', limit=500),
                orders_today=broker._request('GET', '/v2/orders', params=dict(status='all', after=after,
                    limit=500, direction='asc', nested='true')),
                fills_today=broker._request('GET', '/v2/account/activities/FILL',
                    params=dict(after=after, page_size=100, direction='asc')))
        if any(not isinstance(v, list) for v in responses.values()):
            raise ValueError('Invalid broker evidence')
        broker_counts = {k: len(v) for k, v in responses.items()}
        validate_proof(claim, result, effects, rows, counts, broker_counts)
        execution_processes()
        if any((folder/name).read_bytes() != original for name, original in originals.items()):
            raise ValueError('Attempt changed during checks')
        proof = dict(run_id=RUN, risk_run_id=RISK, attempt_id=ATTEMPT, exec_run_id=EXEC,
            checked_at_utc=datetime.now(timezone.utc).isoformat(), account='default', broker_mode='paper',
            sql_counts=counts, execution_rows=rows, broker_counts=broker_counts,
            report_sha256=digest(report), binding_sha256=digest(binding),
            artifact_sha256={name: hashlib.sha256(value).hexdigest() for name, value in originals.items()},
            authorization='Human user explicitly requested removal of this exact lock on 2026-10-28, to rerun manually once',
            action='Archive only this failed attempt; no SQL history changed; no execution launched')
        if not apply:
            print(json.dumps(dict(status='VERIFIED_READ_ONLY', proof=proof), ensure_ascii=False))
            return
        archive = folder/'execution_attempts'/('operator-watcher-recovery-'+uuid.uuid4().hex)
        if not archive.resolve().is_relative_to(folder):
            raise ValueError('Archive outside exact run')
        archive.mkdir(parents=True, exist_ok=False)
        write_new(archive/'recovery_proof.json', proof)
        # Claim last: an interrupted move stays blocked; the kernel lock also
        # excludes a parallel wrapper throughout validation and archival.
        for name in NAMES:
            (folder/name).rename(archive/name)
        print(json.dumps(dict(status='RECOVERED', run_id=RUN, risk_run_id=RISK, archive=str(archive),
            sql_counts=counts, broker_counts=broker_counts, execution_launched=False), ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Archive the exact authorized failed attempt after all checks')
    recover(apply=parser.parse_args().apply)
