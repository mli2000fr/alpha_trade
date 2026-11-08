"""Finish the user's restart with exact-bound PAPER step12 and watcher verification."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import time

from service.options_directional.store import write_new


def main():
    root = Path(__file__).resolve().parents[2]
    operation = root/'artifacts/operations/options_predict_risk_restart/20261103T070925Z-ec42acf2'
    result = json.loads((operation/'result.json').read_text(encoding='utf-8'))
    plan = json.loads((operation/'plan.json').read_text(encoding='utf-8'))
    if result.get('status') != 'completed' or result.get('workflow_completed_steps') != 2:
        raise ValueError('Les étapes 10 et11 doivent avoir réussi')
    if (operation/'execution_workflow.json').exists():
        raise ValueError('Exécution déjà lancée ; aucune nouvelle tentative automatique')
    os.environ['REQUESTS_CA_BUNDLE'] = str(operation/'verified-ca-bundle.pem')
    from ihm.services.pipeline_runner import PipelineLaunchOptions
    options = PipelineLaunchOptions(**plan['options'])
    if options.account_id != 'default' or options.execution_mode != 'paper':
        raise ValueError('Compte default PAPER exclusivement')
    from service.options_directional.accounts import shared_qualified, load_risk_publication
    report = shared_qualified(options.options_filter_run_id, trade_date=options.trade_date,
        batch_id=options.ml_predict_batch_id, symbol_source=options.ml_predict_symbol_source,
        account_id='default')
    binding, summary = load_risk_publication(report, 'default')
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine(db_name='alpha_trade')
    from service.forward_pit.watcher_startup import ensure_watcher
    def before_step(step, current_options, stop_event):
        state = ensure_watcher(engine, current_options, directory=operation, stop_event=stop_event)
        write_new(operation/'execution_watcher.json', state)
        print(json.dumps(dict(phase='WATCHER_VERIFIED', **state)), flush=True)
        return state
    from ihm.services.process_registry import start_pipeline_workflow, poll_pipeline_run
    workflow = start_pipeline_workflow(options, db_config={'name':'alpha_trade'},
        selected_step_keys=('execution',), before_step=before_step)
    write_new(operation/'execution_workflow.json', dict(workflow_run_id=workflow.run_id,
        options_filter_run_id=report['run_id'], risk_run_id=binding['risk_run_id'],
        account_id='default', mode='paper', started_at_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(phase='EXECUTION_STARTED', workflow_run_id=workflow.run_id)), flush=True)
    previous = None
    while True:
        state = poll_pipeline_run(workflow.run_id)
        key = (state.get('status'), state.get('workflow_current_step_key'))
        if key != previous:
            print(json.dumps(dict(phase='STATUS', status=key[0], step=key[1])), flush=True)
            previous = key
        if key[0] not in ('scheduled','starting','running'):
            write_new(operation/'execution_result.json', state)
            print(json.dumps(dict(phase='FINISHED', status=key[0])), flush=True)
            if key[0] != 'completed':
                raise RuntimeError('Exécution arrêtée en échec ; aucune reprise automatique')
            break
        time.sleep(1)
    engine.dispose()


if __name__ == '__main__':
    main()
