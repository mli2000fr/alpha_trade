"""Authorized restart of 10 then 11, default PAPER; no execution or claim reset."""
from dataclasses import asdict, fields, replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import ssl
import time
import uuid

import psutil

from service.options_directional.store import write_new, validate_window

PROJECT = Path(__file__).resolve().parents[2]
PLAN = PROJECT/'artifacts/operations/us_pipeline/us_pipeline-20261102220502-aea4d213/plan.json'


def main():
    operation = PROJECT/'artifacts/operations/options_predict_risk_restart'/(
        datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    operation.mkdir(parents=True, exist_ok=False)
    print(json.dumps(dict(phase='PREFLIGHT', operation=str(operation))), flush=True)
    try:
        # Child clients using ordinary Requests need the same verified roots as
        # the system-trust account reader. This affects only this process tree.
        from common.verified_http import verified_context
        context = verified_context()
        bundle = operation/'verified-ca-bundle.pem'
        bundle.write_text(''.join(ssl.DER_cert_to_PEM_cert(cert)
            for cert in context.get_ca_certs(binary_form=True)), encoding='ascii')
        os.environ['REQUESTS_CA_BUNDLE'] = str(bundle)
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            if (proc.info['name'] or '').lower() not in ('python.exe', 'pythonw.exe'):
                continue
            command = proc.info['cmdline'] or []
            if any(item == 'service.options_directional.pipeline' or item == 'risk_management'
                   or Path(item).name == 'run_execution.py' for item in command):
                raise RuntimeError(f'Risque/exécution pipeline déjà actif pid={proc.pid}')
        from common.us_signal_date import resolve_us_signal_date
        day = resolve_us_signal_date().isoformat()
        validate_window(day)
        from risk_management.broker_account import capture_current_account
        snapshot, raw = capture_current_account('default', 'paper')
        from service.alpaca.clientAlpaca import fetch_asset_by_symbol
        asset = fetch_asset_by_symbol('ICHR', account_id='default')
        if asset.get('symbol') != 'ICHR':
            raise ValueError('Réponse de qualification asset inattendue')
        write_new(operation/'preflight.json', dict(account_id='default', mode='paper',
            trade_date=day, equity=snapshot.account.equity, positions=len(snapshot.positions),
            open_orders=len(snapshot.open_orders), verified_asset='ICHR',
            captured_at_utc=datetime.now(timezone.utc).isoformat()))
        from ihm.services.pipeline_runner import PipelineLaunchOptions
        original = json.loads(PLAN.read_text(encoding='utf-8'))
        base = PipelineLaunchOptions(**original['options'])
        from common.capital_presets import resolve_capital_preset_for_equity
        preset = resolve_capital_preset_for_equity(snapshot.account.equity)
        known = {field.name for field in fields(PipelineLaunchOptions)}
        risk_values = {key.removeprefix('pipeline_'):value for key,value in
            preset.to_session_state_values(detected_equity=snapshot.account.equity).items()
            if key.startswith('pipeline_risk_') and key.removeprefix('pipeline_') in known}
        options = replace(base, **risk_values)
        options = replace(options, account_id='default', execution_mode='paper',
            trade_date=day, force_trade_date_to_latest_snapshot=False,
            options_filter_enabled=True, options_filter_run_id='opt-'+uuid.uuid4().hex,
            llm_filter_enabled=False, llm_filter_run_id=None, risk_enable_kelly=False,
            risk_account_equity=snapshot.account.equity, execution_run_id=None)
        write_new(operation/'plan.json', dict(steps=[10,11], source_plan=str(PLAN),
            options=asdict(options), capital_sizing_preset=preset.key,
            execution_authorized_by_this_script=False, old_claims_untouched=True))
        from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run
        workflow = start_pipeline_workflow(options, db_config={'name':'alpha_trade'},
            selected_step_keys=('ml_predict','risk_management'))
        write_new(operation/'workflow.json', dict(workflow_run_id=workflow.run_id,
            options_filter_run_id=options.options_filter_run_id, account_id='default', trade_date=day))
        print(json.dumps(dict(phase='STARTED', workflow_run_id=workflow.run_id,
            options_filter_run_id=options.options_filter_run_id, steps=[10,11], trade_date=day)), flush=True)
        previous = None
        while True:
            state = poll_pipeline_run(workflow.run_id)
            key = (state.get('status'), state.get('workflow_current_step_key'), state.get('workflow_completed_steps'))
            if key != previous:
                print(json.dumps(dict(phase='STATUS', status=key[0], step=key[1], completed=key[2])), flush=True)
                previous = key
            if key[0] not in ('scheduled','starting','running'):
                write_new(operation/'result.json', state)
                print(json.dumps(dict(phase='FINISHED', status=key[0], completed=key[2],
                    operation=str(operation))), flush=True)
                if key[0] != 'completed':
                    raise RuntimeError('Workflow arrêté en échec ; aucune relance automatique')
                break
            time.sleep(1)
    except Exception as exc:
        write_new(operation/'error.json', dict(type=type(exc).__name__, error=str(exc),
            failed_at_utc=datetime.now(timezone.utc).isoformat()))
        raise


if __name__ == '__main__':
    main()
