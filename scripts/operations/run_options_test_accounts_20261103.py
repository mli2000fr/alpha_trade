"""Authorized PAPER steps11/12 for test1 and test2, sharing the completed step10."""
from dataclasses import asdict, fields, replace
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import uuid

import psutil
from sqlalchemy import text

from service.options_directional.accounts import consumer_directory, shared_qualified, require_paper_account
from service.options_directional.store import directory, write_new


PROJECT = Path(__file__).resolve().parents[2]
SOURCE = PROJECT/'artifacts/operations/options_predict_risk_restart/20261103T070925Z-ec42acf2'
FILTER = 'opt-3a3ba8ac5dae4e82994ea7b467ba14eb'
ACCOUNTS = ('test1', 'test2')


def main():
    operation = PROJECT/'artifacts/operations/options_secondary_accounts'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    operation.mkdir(parents=True, exist_ok=False)
    print(json.dumps(dict(phase='STARTING', accounts=ACCOUNTS, operation=str(operation))), flush=True)
    bundle = SOURCE/'verified-ca-bundle.pem'
    if not bundle.is_file():
        raise ValueError('Certificats vérifiés absents')
    os.environ['REQUESTS_CA_BUNDLE'] = str(bundle)
    from ihm.services.pipeline_runner import PipelineLaunchOptions
    base = PipelineLaunchOptions(**json.loads((SOURCE/'plan.json').read_text(encoding='utf-8'))['options'])
    if base.options_filter_run_id != FILTER or base.execution_mode != 'paper':
        raise ValueError('Plan de référence différent du filtre demandé')
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        if (proc.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe'):
            continue
        command = proc.info['cmdline'] or []
        if any(arg in ('risk_management', 'service.options_directional.pipeline')
               or Path(arg).name == 'run_execution.py' for arg in command):
            raise RuntimeError(f'Une étape risque/exécution est encore active pid={proc.pid}')
    market_files = {name:hashlib.sha256((directory(FILTER)/name).read_bytes()).hexdigest()
                    for name in ('inputs.json','report.json','seal.json')}
    write_new(operation/'authorization.json', dict(accounts=ACCOUNTS, steps=[11,12], mode='paper',
        options_filter_run_id=FILTER, default_account_excluded=True, market_files=market_files,
        instruction='User requested steps11 and12 on test1 andtest2, 2026-11-03'))
    from database.connection import get_sqlalchemy_engine
    from execution_engine.db_io import ExecutionRepository
    from risk_management.broker_account import capture_current_account
    from common.capital_presets import resolve_capital_preset_for_equity
    from service.forward_pit.watcher_startup import ensure_watcher, healthy_service
    from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    results = []
    try:
        for account in ACCOUNTS:
            folder = operation/account
            folder.mkdir(exist_ok=False)
            try:
                require_paper_account(account)
                report = shared_qualified(FILTER, account_id=account, trade_date=base.trade_date,
                    batch_id=base.ml_predict_batch_id, symbol_source=base.ml_predict_symbol_source)
                consumer = consumer_directory(FILTER, account)
                if consumer.exists() and any(consumer.iterdir()):
                    raise ValueError('Ce compte possède déjà une tentative sur ce filtre ; aucune reprise implicite')
                with engine.connect() as conn:
                    active = conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE account_id=:account AND status='RUNNING'"),
                                          dict(account=account)).scalar_one()
                if active:
                    raise ValueError('Exécution déjà active pour ce compte')
                snapshot, raw = capture_current_account(account, 'paper')
                equity = snapshot.account.equity
                preset = resolve_capital_preset_for_equity(equity)
                known = {field.name for field in fields(PipelineLaunchOptions)}
                risk_values = {key.removeprefix('pipeline_'):value for key,value in
                    preset.to_session_state_values(detected_equity=equity).items()
                    if key.startswith('pipeline_risk_') and key.removeprefix('pipeline_') in known}
                options = replace(base, **risk_values)
                options = replace(options, account_id=account, risk_account_equity=equity,
                    execution_mode='paper', execution_run_id=None, risk_enable_kelly=False,
                    llm_filter_enabled=False, options_filter_run_id=FILTER,
                    force_trade_date_to_latest_snapshot=False)
                write_new(folder/'preflight.json', dict(account_id=account, equity=equity,
                    capital_sizing_preset=preset.key, positions=len(snapshot.positions),
                    open_orders=len(snapshot.open_orders), options_filter_run_id=FILTER,
                    selected=report['selected'], captured_at_utc=datetime.now(timezone.utc).isoformat()))
                write_new(folder/'options.json', asdict(options))
                def before_step(step, current_options, stop_event):
                    if step.key != 'execution':
                        return None
                    state = ensure_watcher(engine, current_options, directory=folder, stop_event=stop_event)
                    write_new(folder/'watcher.json', state)
                    print(json.dumps(dict(phase='WATCHER_READY', account=account, status=state['status'])), flush=True)
                    return state
                workflow = start_pipeline_workflow(options, db_config={'name':'alpha_trade'},
                    selected_step_keys=('risk_management','execution'), before_step=before_step)
                write_new(folder/'workflow.json', dict(workflow_run_id=workflow.run_id,
                    account_id=account, options_filter_run_id=FILTER, steps=[11,12]))
                print(json.dumps(dict(phase='WORKFLOW_STARTED', account=account, workflow_run_id=workflow.run_id)), flush=True)
                previous = None
                while True:
                    state = poll_pipeline_run(workflow.run_id)
                    key = (state.get('status'), state.get('workflow_current_step_key'), state.get('workflow_completed_steps'))
                    if key != previous:
                        print(json.dumps(dict(phase='STATUS', account=account, status=key[0],
                            step=key[1], completed=key[2])), flush=True)
                        previous = key
                    if key[0] not in ('scheduled','starting','running'):
                        write_new(folder/'result.json', state)
                        break
                    time.sleep(1)
                confirmation = dict(account_id=account, status=state['status'], workflow_run_id=workflow.run_id,
                                    watcher_healthy=healthy_service(ExecutionRepository(engine), account))
                for name in ('risk_summary.json','execution.result.json'):
                    path = consumer/name
                    if path.exists():
                        confirmation[name] = json.loads(path.read_text(encoding='utf-8'))
                write_new(folder/'confirmation.json', confirmation)
                results.append(dict(account_id=account, status=state['status'], workflow_run_id=workflow.run_id,
                                    watcher_healthy=confirmation['watcher_healthy']))
            except Exception as exc:
                error = dict(account_id=account, status='failed', error_type=type(exc).__name__, error=str(exc))
                write_new(folder/'error.json', error)
                results.append(error)
                print(json.dumps(dict(phase='ACCOUNT_FAILED', **error)), flush=True)
            # Let the registry finalize/remove terminal workers before starting another account.
            from ihm.services.process_registry import list_active_pipeline_runs
            for _ in range(10):
                if not list_active_pipeline_runs():
                    break
                time.sleep(.2)
        for name, expected in market_files.items():
            if hashlib.sha256((directory(FILTER)/name).read_bytes()).hexdigest() != expected:
                raise ValueError('Archive de sélection modifiée pendant l’opération')
        write_new(operation/'results.json', results)
        print(json.dumps(dict(phase='FINISHED', results=results, operation=str(operation))), flush=True)
    finally:
        engine.dispose()


if __name__ == '__main__':
    main()
