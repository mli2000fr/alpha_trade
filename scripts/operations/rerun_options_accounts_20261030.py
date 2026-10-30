"""Relance PAPER 11/12 autorisée, après désactivation du blackout earnings.

Publie un nouvel univers et une sélection scellée depuis les données SQL déjà
collectées. Ne supprime aucun ancien verrou, résultat ni ordre.
"""
from dataclasses import replace
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import ssl
import subprocess
import threading
import time
import uuid

import certifi
from sqlalchemy import text

from common.verified_http import verified_session
from database.connection import get_sqlalchemy_engine
from execution_engine.db_io import ExecutionRepository
from ihm.services.pipeline_runner import PipelineLaunchOptions, build_pipeline_command
from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run, list_active_pipeline_runs
from service.alpaca.accounts import AccountRegistry
from service.alpaca.trading_client import AlpacaTradingClient
from service.forward_pit.watcher_startup import ensure_watcher, healthy_service, find_running_service
from service.options_directional.accounts import consumer_directory, require_paper_account, shared_qualified
from service.options_directional.runner import analyze
from service.options_directional.store import directory, write_new


ROOT = Path(__file__).resolve().parents[2]
PLAN = ROOT/'artifacts/operations/us_pipeline/us_pipeline-20261029220502-3c3098ad/plan.json'
ORIGINAL = 'opt-6399bec5c0a647448aaa01c7880e08a4'


def emit(**values):
    print(json.dumps(values, default=str, ensure_ascii=False), flush=True)


def broker_state(account_id):
    with verified_session() as session:
        broker = AlpacaTradingClient(broker_mode='paper', account_id=account_id, session=session)
        account = broker.get_account()
        equity = float(account['equity'])
        if not math.isfinite(equity) or equity <= 0 or account.get('trading_blocked'):
            raise ValueError('Compte papier indisponible pour de nouvelles entrées')
        return dict(equity=equity, buying_power=account['buying_power'],
            positions=[{k:p.get(k) for k in ('symbol','qty','side')} for p in broker.get_positions()],
            open_orders=[{k:o.get(k) for k in ('id','symbol','side','qty','type','status','client_order_id')}
                         for o in broker.list_orders(status='open', limit=500)])


def current_watcher(engine, options, folder, stop_event):
    """Redémarrage borné du seul service papier dont l'identité est vérifiée."""
    from execution_engine.winner_plans import require_current_watcher_code
    account = options.account_id
    process = find_running_service(account)
    if process is not None:
        try:
            require_current_watcher_code(process)
        except ValueError:
            with engine.connect() as conn:
                lease = conn.execute(text('SELECT locked_by_run_id FROM execution_locks WHERE account_id=:scope'),
                    dict(scope='watcher:'+account)).scalar_one_or_none()
                pid = conn.execute(text("SELECT pid FROM watcher_heartbeats WHERE account_id=:account AND "
                    "watcher_name='execution_protection_watcher' ORDER BY last_heartbeat_at DESC LIMIT 1"),
                    dict(account=account)).scalar_one_or_none()
            import psutil
            worker = process
            if pid is None:
                raise ValueError('Identité du watcher non confirmée ; aucun arrêt')
            if int(pid) != process.pid:
                worker = psutil.Process(int(pid))
                # Le lanceur venv Windows attend son interpréteur enfant.
                if worker.ppid() != process.pid or worker.cmdline() != process.cmdline():
                    raise ValueError('Identité du watcher non confirmée ; aucun arrêt')
            emit(phase='RESTART_STALE_WATCHER', account=account, pid=process.pid)
            worker.terminate()
            worker.wait(timeout=15)
            if worker.pid != process.pid:
                try:
                    process.wait(timeout=5)
                except psutil.TimeoutExpired:
                    process.terminate()
                    process.wait(timeout=10)
            if find_running_service(account) is not None:
                raise ValueError('Un autre watcher est apparu ; verrou conservé')
            if lease is not None:
                ExecutionRepository(engine).release_execution_lock(account_id='watcher:'+account, exec_run_id=lease)
            write_new(folder/'watcher_restart.json', dict(account=account, old_pid=process.pid,
                released_lease=lease, broker_orders_untouched=True))
    return ensure_watcher(engine, options, directory=folder, stop_event=stop_event)


def wait_registry_finalization():
    deadline = time.monotonic()+60
    while list_active_pipeline_runs():
        if time.monotonic() >= deadline:
            raise RuntimeError('Le workflow précédent finalise encore ; aucune relance concurrente')
        time.sleep(.5)


def main(requested_accounts=None, prepared_selection=None):
    base = PipelineLaunchOptions(**json.loads(PLAN.read_text(encoding='utf-8'))['options'])
    if base.execution_mode != 'paper' or base.llm_filter_enabled or base.trade_date != '2026-10-29':
        raise ValueError('Contexte PAPER exact du 29/10 requis')
    original_id=prepared_selection or ORIGINAL
    old = shared_qualified(original_id, account_id='default', trade_date=base.trade_date,
        batch_id=base.ml_live_predict_batch_id, symbol_source=base.ml_predict_symbol_source)
    accounts = ['default'] + [a.account_id for a in AccountRegistry.get().list_accounts()
                              if a.account_id != 'default' and a.mode == 'paper']
    if requested_accounts is not None:
        if not requested_accounts or set(requested_accounts)-set(accounts):
            raise ValueError('Liste de comptes PAPER explicites invalide')
        accounts = [a for a in accounts if a in requested_accounts]
    if 'default' not in accounts:
        raise ValueError('Cette opération commence par default')
    for account in accounts:
        require_paper_account(account)
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    operation = ROOT/'artifacts/operations/options_accounts_blackout_disabled'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    operation.mkdir(parents=True, exist_ok=False)
    emit(phase='PREPARING', directory=str(operation), accounts=accounts)
    write_new(operation/'authorization.json', dict(accounts=accounts, steps=[11,12], mode='paper',
        original_selection=original_id, trade_date=base.trade_date,
        authorization='User requested default then other PAPER accounts, after earnings blackout -1',
        prior_claims_preserved=True))
    bundle = operation/'verified-ca-bundle.pem'
    pem = Path(certifi.where()).read_text(encoding='ascii')
    for certificate, encoding, _ in ssl.enum_certificates('ROOT'):
        if encoding == 'x509_asn':
            pem += '\n'+ssl.DER_cert_to_PEM_cert(certificate)
    bundle.write_text(pem, encoding='ascii')
    os.environ['REQUESTS_CA_BUNDLE'] = str(bundle)
    states = {}
    for account in accounts:
        with engine.connect() as conn:
            active = conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE account_id=:account AND status='RUNNING'"),
                                  dict(account=account)).scalar_one()
        if active:
            raise ValueError(f'Une exécution est déjà active pour {account}')
        states[account] = broker_state(account)
        from execution_engine.winner_campaign_store import WinnerCampaignStore
        known_buys = {op['broker_id'] for r in WinnerCampaignStore(engine).rows(account,'paper')
            for op in r['state']['operations'] if op['action']=='ENTRY'
            and op['status']=='SUBMITTED' and op.get('broker_id')}
        for order in states[account]['open_orders']:
            if order['side']=='buy' and order['symbol'] in old['selected'] and order['id'] not in known_buys:
                raise ValueError(f'Achat ouvert sans campagne Winner réconciliée sur {account}')
    write_new(operation/'preflight.json', states)
    base = replace(base, selector_earnings_blackout_days=-1, allow_fractional_shares=False,
                   risk_account_equity=states['default']['equity'])
    command = build_pipeline_command('publish_tradable_universe', base)
    with (operation/'universe.stdout.log').open('x', encoding='utf-8') as stdout, (operation/'universe.stderr.log').open('x', encoding='utf-8') as stderr:
        subprocess.run(command, cwd=ROOT, check=True, stdout=stdout, stderr=stderr)
    with engine.connect() as conn:
        latest = dict(conn.execute(text("SELECT universe_run_id,tradable_rows,rows_expected,status FROM tradable_universe_runs "
            "WHERE snapshot_date=:day AND capital_preset_key=:preset AND status='completed' AND data_quality_grade='full' "
            "ORDER BY finished_at DESC LIMIT 1"), dict(day=base.trade_date, preset=old['capital_preset_key'])).mappings().one())
        exclusions = [dict(r) for r in conn.execute(text("SELECT symbol,is_tradable,tradability_reason_code,earnings_blackout "
            "FROM tradable_universe_history WHERE universe_run_id=:run AND symbol IN ('BAND','COHU','UCTT','SIMO')"),
            dict(run=latest['universe_run_id'])).mappings()]
    if len(exclusions) != 4 or any(r['earnings_blackout'] for r in exclusions):
        raise ValueError('La nouvelle publication ne prouve pas la désactivation earnings')
    write_new(operation/'universe.json', dict(**latest, selection=exclusions))
    emit(phase='UNIVERSE_PUBLISHED', **latest, selection=exclusions)
    new_id = 'opt-'+uuid.uuid4().hex
    report = analyze(engine, run_id=new_id, batch_id=old['batch_id'], trade_date=old['trade_date'],
        symbol_source=old['symbol_source'], capital_preset_key=old['capital_preset_key'],
        artifacts_dir=base.ml_artifacts_dir, producer_account_id='default')
    if report['selected'] != old['selected']:
        raise ValueError('La sélection a changé ; aucune exécution engagée')
    write_new(operation/'selection_refresh.json', dict(old=original_id, new=new_id,
        selected=report['selected'], oracle_reused=True, provider_downloads=0, llm_calls=0))
    results = []
    for account in accounts:
        folder = operation/account
        folder.mkdir(exist_ok=False)
        started = datetime.now(timezone.utc).isoformat()
        try:
            current = broker_state(account)
            write_new(folder/'preflight.json', current)
            from common.capital_presets import resolve_capital_preset_for_equity
            from dataclasses import fields
            preset = resolve_capital_preset_for_equity(current['equity'])
            known = {f.name for f in fields(PipelineLaunchOptions)}
            risk_values = {key.removeprefix('pipeline_'):value for key,value in
                preset.to_session_state_values(detected_equity=current['equity']).items()
                if key.startswith('pipeline_risk_') and key.removeprefix('pipeline_') in known}
            options = replace(base, **risk_values)
            options = replace(options, account_id=account, execution_mode='paper', execution_run_id=None,
                options_filter_enabled=True, options_filter_run_id=new_id, llm_filter_enabled=False,
                risk_account_equity=current['equity'], risk_enable_kelly=False)
            write_new(folder/'risk_options.json', dict(capital_sizing_preset=preset.key, **risk_values))

            def before_step(step, current_options, stop_event):
                if step.key != 'execution':
                    return None
                result = ensure_watcher(engine, current_options, directory=folder, stop_event=stop_event)
                write_new(folder/'watcher.json', result)
                return result

            ready = current_watcher(engine, options, folder, threading.Event())
            write_new(folder/'watcher_before_risk.json', ready)
            wait_registry_finalization()
            workflow = start_pipeline_workflow(options, db_config={'name':'alpha_trade'},
                selected_step_keys=('risk_management','execution'), before_step=before_step)
            write_new(folder/'workflow.json', dict(run_id=workflow.run_id, account_id=account,
                options_filter_run_id=new_id, trade_date=base.trade_date, steps=[11,12]))
            emit(phase='WORKFLOW_STARTED', account=account, run_id=workflow.run_id, selection=new_id)
            previous = None
            while True:
                state = poll_pipeline_run(workflow.run_id)
                key = (state.get('status'), state.get('workflow_current_step_key'), state.get('workflow_completed_steps'))
                if key != previous:
                    emit(phase='STATUS', account=account, status=key[0], step=key[1], completed=key[2])
                    previous = key
                if state.get('status') not in ('scheduled','starting','running'):
                    write_new(folder/'result.json', state)
                    break
                time.sleep(1)
            result = dict(account_id=account, status=state['status'], workflow_run_id=workflow.run_id)
            consumer = consumer_directory(new_id, account)
            if (consumer/'risk_summary.json').exists():
                summary = json.loads((consumer/'risk_summary.json').read_text(encoding='utf-8'))
                result.update(risk_run_id=summary['run_id'], accepted_symbols=summary.get('accepted_symbols'),
                              rejected_symbols=summary.get('rejected_symbols'), account_equity=summary.get('account_equity'))
                with engine.connect() as conn:
                    result['targets'] = [dict(r) for r in conn.execute(text("SELECT symbol,side,shares FROM portfolio_targets WHERE run_id=:run AND account_id=:account"),
                        dict(run=summary['run_id'],account=account)).mappings()]
                    result['executions'] = [dict(r) for r in conn.execute(text("SELECT exec_run_id,status,total_submitted,total_filled,error_message FROM execution_runs WHERE risk_run_id=:run AND account_id=:account"),
                        dict(run=summary['run_id'],account=account)).mappings()]
            result['watcher_healthy'] = healthy_service(ExecutionRepository(engine), account)
            with verified_session() as session:
                broker = AlpacaTradingClient(broker_mode='paper', account_id=account, session=session)
                orders = broker._request('GET','/v2/orders',params=dict(status='all', after=started, limit=500, direction='asc', nested='true'))
                result['broker_orders'] = [{k:o.get(k) for k in ('id','symbol','side','qty','type','limit_price','status','filled_qty','filled_avg_price')} for o in orders]
            write_new(folder/'confirmation.json', result)
            results.append(result)
            emit(phase='ACCOUNT_FINISHED', **result)
            wait_registry_finalization()
        except Exception as exc:
            result = dict(account_id=account,status='FAILED',error=str(exc))
            write_new(folder/'error.json', result)
            results.append(result)
            emit(phase='ACCOUNT_FAILED', **result)
    write_new(operation/'summary.json', dict(accounts=results, options_filter_run_id=new_id,
        universe_run_id=latest['universe_run_id'], original_claims_preserved=True))
    emit(phase='FINISHED', directory=str(operation), accounts=results)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--accounts',nargs='+')
    parser.add_argument('--prepared-selection')
    args=parser.parse_args()
    main(args.accounts,args.prepared_selection)
