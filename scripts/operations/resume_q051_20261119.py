"""One exact PAPER continuation after the 2026-11-19 watcher refresh.

Native pipeline workflows, locks, risk and execution are unchanged. Never rerun
Oracle or the already sealed default risk. Refuse an attempted execution.
"""
from dataclasses import asdict,replace
from datetime import UTC,date,datetime,timedelta
import json
import os
from pathlib import Path
import time

from sqlalchemy import text

from service.forward_pit import batch
from service.forward_pit.us_pipeline import require_paper_account
from service.forward_pit.us_pipeline_recovery import recovery_session
from common.q051_paper import profile_scope,settings
from ihm.services.pipeline_runner import PipelineLaunchOptions,get_pipeline_steps
from ihm.services.process_registry import start_pipeline_workflow,poll_pipeline_run

ROOT=Path(__file__).resolve().parents[2]
SOURCE_BATCH='us_pipeline-20261119103942-24954974'
SOURCE_WORKFLOW='20261119_113947_c7d140cb'
SELECTION='q051-6af2c1804fbb43e6acbd49ddf76b4a00'
DAY=date(2026,11,18)
PROFILE='q051_b_witness_v1'
MODEL='model-factory-20261118172104-2f6a31'
RISK='55b97d7b4f8d4447b594c4f51d63e054'


def test2_only():
    return os.environ.get('ALPHA_Q051_EXACT_TEST2_ONLY')=='1'


def qualify(engine,run_id):
    if engine.url.database!='alpha_trade' or recovery_session(datetime.now(UTC))!=DAY:
        raise ValueError('Continuation limitée au PAPER US avant ouverture du 19 novembre')
    current=settings()
    if not current['enabled'] or current['profile_id']!=PROFILE or current['model_batch_id']!=MODEL:
        raise ValueError('Configuration différente de la sélection approuvée')
    source=json.loads((ROOT/'artifacts/operations/us_pipeline'/SOURCE_BATCH/'plan.json').read_text())
    options=PipelineLaunchOptions(**source['options'])
    if (options.q051_run_id!=SELECTION or options.trade_date!=str(DAY) or options.q051_profile_id!=PROFILE
            or options.execution_mode!='paper' or options.account_id!='default'):
        raise ValueError('Contrat source différent de la continuation exacte')
    record=json.loads((ROOT/'artifacts/ihm_pipeline_runs/pipeline_workflow'/SOURCE_WORKFLOW/'record.json').read_text())
    if record['status']!='failed' or record['workflow_completed_steps']!=2 or record['workflow_total_steps']!=3:
        raise ValueError('Reçu du workflow source modifié')
    children=[]
    for child in record['workflow_child_run_ids']:
        paths=list((ROOT/'artifacts/ihm_pipeline_runs').glob(f'*/{child}/record.json'))
        if len(paths)!=1:raise ValueError('Reçu enfant absent ou ambigu')
        receipt=json.loads(paths[0].read_text())
        if receipt['status']!='completed' or receipt['returncode']!=0:
            raise ValueError('Une étape source n’est pas terminée')
        children.append(receipt['step_key'])
    if children!=['ml_predict','risk_management']:
        raise ValueError('Exécution déjà tentée ou chaîne source différente')
    for account in ['default','test1','test2']:require_paper_account(account)
    from service.q051_paper.pipeline import qualified,digest
    with profile_scope(PROFILE):
        folder,selection=qualified(SELECTION,batch=MODEL,day=DAY,artifacts_dir=options.ml_artifacts_dir)
    risk=json.loads((folder/'accounts/default/risk.json').read_text())
    seal=json.loads((folder/'accounts/default/risk.seal.json').read_text())
    if (risk['status']!='COMPLETED' or risk['risk_run_id']!=RISK or risk['q051_run_id']!=SELECTION
            or seal['risk_sha256']!=digest(folder/'accounts/default/risk.json')):
        raise ValueError('Risque approuvé différent du reçu scellé')
    if not test2_only() and any((folder/'accounts/default'/name).exists() for name in ['execution.claim.json','execution.json']):
        raise ValueError('Une exécution du compte default existe déjà ; réconcilier avant reprise')
    for account in (['test2'] if test2_only() else ['test1','test2']):
        if any((folder/'accounts'/account/name).exists() for name in ['risk.claim.json','risk.json','execution.claim.json','execution.json']):
            raise ValueError(f'{account}: tentative déjà présente ; réconcilier avant reprise')
    with engine.connect() as conn:
        if not test2_only() and conn.execute(text('SELECT COUNT(*) FROM execution_runs WHERE risk_run_id=:risk'),dict(risk=RISK)).scalar():
            raise ValueError('Run d’exécution déjà présent pour ce risque')
        if test2_only():
            for account in ['default','test1']:
                account_folder=folder/'accounts'/account
                saved_risk=json.loads((account_folder/'risk.json').read_text())
                saved_seal=json.loads((account_folder/'risk.seal.json').read_text())
                execution=json.loads((account_folder/'execution.json').read_text())
                if (saved_risk['status']!='COMPLETED' or saved_risk['q051_run_id']!=SELECTION
                        or saved_seal['risk_sha256']!=digest(account_folder/'risk.json')
                        or execution['status']!='COMPLETED' or execution['account_id']!=account
                        or execution['risk_run_id']!=saved_risk['risk_run_id']):
                    raise ValueError('Comptes terminés non qualifiés ; aucune reprise')
                if not conn.execute(text("SELECT COUNT(*) FROM execution_runs WHERE exec_run_id=:run AND account_id=:account AND risk_run_id=:risk AND status='COMPLETED'"),
                        dict(run=execution['exec_run_id'],account=account,risk=saved_risk['risk_run_id'])).scalar():
                    raise ValueError('Exécution terminée non confirmée en SQL')
        if conn.execute(text("SELECT COUNT(*) FROM pit_collection_runs WHERE batch_name='us_pipeline' AND status='RUNNING' AND started_at>=:since AND run_id<>:run"),
                dict(since=datetime.combine(DAY-timedelta(days=1),datetime.min.time()),run=run_id)).scalar():
            raise ValueError('Un autre batch US est actif')
    return options


def handler(engine,cfg,run_id,dry_run):
    options=qualify(engine,run_id)
    plan=dict(trade_date=str(DAY),strategy_profile=PROFILE,account_id='default',
        source_batch_run_id=SOURCE_BATCH,source_workflow_run_id=SOURCE_WORKFLOW,
        q051_run_id=SELECTION,options=asdict(options),selected_step_numbers=[12],
        resume_steps={'default':[12],'test1':[11,12],'test2':[11,12]},account_workflows=[],
        counter_unit='pipeline_steps',training=False,execution_mode='paper',
        preserved_steps=['default:10','default:11'])
    if test2_only():
        plan.update(account_id='test2',selected_step_numbers=[11,12],resume_steps={'test2':[11,12]},
            preserved_steps=['default:10','default:11','default:12','test1:11','test1:12'])
    outcome=batch.Outcome(requested=sum(len(numbers) for numbers in plan['resume_steps'].values()),details=plan)
    if dry_run:return outcome
    directory=ROOT/'artifacts/operations/us_pipeline'/run_id
    directory.mkdir(parents=True,exist_ok=False)
    (directory/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    def before(step,opts,stop):
        if step.key=='execution':
            from service.forward_pit.watcher_startup import ensure_watcher
            return ensure_watcher(engine,opts,directory=directory,stop_event=stop)
    for account,numbers in plan['resume_steps'].items():
        steps=tuple(s for s in get_pipeline_steps() if s.num in {str(n) for n in numbers})
        result=dict(account_id=account,selected_step_numbers=numbers,status='starting')
        plan['account_workflows'].append(result)
        offset=outcome.persisted;deadline=None
        try:
            record=start_pipeline_workflow(replace(options,account_id=account),db_config={'name':'alpha_trade'},
                selected_step_keys=tuple(s.key for s in steps),before_step=before)
            result['workflow_run_id']=record.run_id
            print(f'Exact continuation account={account} workflow={record.run_id} steps={numbers}',flush=True)
            while True:
                snapshot=poll_pipeline_run(record.run_id)
                if snapshot is None:raise ValueError('Suivi du workflow perdu ; aucun compte suivant lancé')
                completed=int(snapshot.get('workflow_completed_steps') or 0)
                outcome.persisted=outcome.received=offset+completed
                if snapshot['status'] in {'starting','running','scheduled'}:
                    time.sleep(.5);continue
                if snapshot.get('workflow_finalizing'):
                    deadline=deadline or time.monotonic()+120
                    if time.monotonic()>deadline:raise ValueError('Finalisation du workflow non terminée')
                    time.sleep(.5);continue
                result.update(status=snapshot['status'],completed_steps=completed,log=snapshot.get('combined_path'))
                if snapshot['status']!='completed' or completed!=len(steps):
                    raise ValueError(f'Continuation interrompue compte={account} après {completed}/{len(steps)} étapes')
                break
        except Exception as exc:
            outcome.failed=1;plan['failed_account_id']=account
            raise batch.BatchRunError(str(exc),outcome) from exc
    return outcome


if __name__=='__main__':
    import sys
    if '--batch' not in sys.argv or sys.argv[sys.argv.index('--batch')+1:] == [] or sys.argv[sys.argv.index('--batch')+1]!='us_pipeline':
        raise ValueError('Cette continuation exacte est réservée au batch us_pipeline')
    batch.HANDLERS['us_pipeline']=handler
    batch.main()
