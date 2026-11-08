"""Resume the same local cohort, preserving receipts and historical validation errors."""
from dataclasses import replace
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid

from scripts.research import us_local_llm_winner_ab as base
from scripts.research.us_local_llm_winner_campaign import cache_counts,read
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from service.local_ai.research_veto import Cache,validate_response

ROOT=Path('artifacts/research/us_local_llm_winner_ab/20261107-v7')


def transport_recoveries(packets,records):
    """Retry only a received transport error with no LLM receipt, never bad citations."""
    result=[]
    for p in packets:
        old=records.get(p['key'])
        if (old and not old['validation'].get('valid') and old['response'] is None
                and p['context']['news'] and old['validation'].get('error_type')=='RuntimeError'
                and old['validation'].get('error','').startswith(('LM Studio HTTP ', 'LM Studio indisponible'))):
            result.append(p)
    if len(result)>1:
        raise ValueError('Plusieurs erreurs de transport : qualification nécessaire avant reprise')
    return result


def cached_records(root):
    db=sqlite3.connect((root/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
    try:
        return {key:dict(validation=json.loads(v),response=json.loads(raw) if raw else None)
            for key,v,raw in db.execute('SELECT a.request_key,a.validation_json,a.response_json '
                'FROM attempts a WHERE a.id=(SELECT MAX(b.id) FROM attempts b WHERE b.request_key=a.request_key)')}
    finally:db.close()


def run(root):
    folder=root/'resume-attempts'/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8])
    folder.mkdir(parents=True,exist_ok=False)
    campaign=root/'campaign'
    with exclusive_run(campaign):
        plan=base.verified(root);packets=read(root/'requests.json')
        before=cache_counts(root);records=cached_records(root)
        recover=transport_recoveries(packets,records)
        for name in ('campaign/report.json','campaign/progress.json','analysis-report.json','progress.json'):
            if (root/name).exists():shutil.copyfile(root/name,folder/('before-'+name.replace('/','-')))
        db=sqlite3.connect((root/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True)
        backup=sqlite3.connect(folder/'before-analyses.sqlite3')
        try:db.backup(backup)
        finally:backup.close();db.close()
        atomic_json(folder/'authorization.json',dict(user_request='tu peux reprenadre',before=before,
            transport_retries=len(recover),new_pending_calls=before['pending'],cloud_calls=0,broker_calls=0,
            original_protocol_sha256=digest(root/'protocol.json'),resume_script_sha256=digest(Path(__file__)),
            preserve_invalid_receipts=True,automatic_transport_retry=False,
            runtime_context_length=34186,runtime_parallel=1))
        try:
            with exclusive_run(root):
                config=base.Connection(**plan['connection'])
                client=base.Client(config)
                try:
                    runtime=client._request('GET','/models')
                    if config.model not in [m.get('id') for m in runtime.get('data',[])]:
                        raise ValueError('Modèle local attendu indisponible')
                    r=client.session.get(config.base_url.removesuffix('/v1')+'/api/v0/models',
                        headers=client.headers,timeout=(3,10),allow_redirects=False)
                    r.raise_for_status();runtime=r.json()
                    loaded=next((m for m in runtime.get('data',[]) if m.get('id')==config.model),{})
                    if loaded.get('loaded_context_length',0)<34186:
                        raise ValueError('Contexte local inférieur aux 34 186 tokens du protocole')
                    atomic_json(folder/'runtime-models.json',runtime)
                    cache=Cache(root/'analyses.sqlite3')
                    try:
                        for packet in recover:
                            state=dict(status='RECOVERING_TRANSPORT',resume_folder=str(folder),**before,
                                analysis_progress=dict(current_symbol=packet['symbol'],current_signal_date=packet['signal_date']))
                            for path in (folder/'progress.json',campaign/'progress.json',campaign/'report.json'):
                                atomic_json(path,state)
                            client.config=replace(config,max_output_tokens=packet['request']['max_tokens'])
                            response=None
                            try:
                                response=client.chat(packet['request']['messages'],response_format=packet['request']['response_format'])
                                if response['request']!=packet['request']:raise ValueError('Requête de reprise différente')
                                validation=validate_response(response,packet)
                            except Exception as exc:
                                response=getattr(exc,'result',response)
                                validation=dict(valid=False,veto=False,error_type=type(exc).__name__,error=str(exc))
                            cache.put(packet['key'],packet['request'],response,validation)
                            atomic_json(folder/'transport-recovery.json',dict(symbol=packet['symbol'],
                                signal_date=packet['signal_date'],validation=validation,has_receipt=response is not None))
                            if response is None or response.get('finish_reason')=='length':
                                raise ValueError('Reprise transport interrompue ; aucune répétition automatique')
                    finally:cache.close()
                finally:client.close()
            command=[sys.executable,'-X','utf8','-u','-m','scripts.research.us_local_llm_winner_ab',
                'analyze','--output-dir',str(root),'--limit',str(max(1,before['pending']))]
            with (folder/'analyze.log').open('x',encoding='utf-8') as log:
                child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
                atomic_json(folder/'child.json',dict(pid=child.pid,command=command))
                while child.poll() is None:
                    state=dict(status='ANALYZING_LOCAL',resume_folder=str(folder),child_pid=child.pid,
                        updated_at_utc=datetime.now(timezone.utc).isoformat(),**cache_counts(root))
                    if (root/'progress.json').exists():state['analysis_progress']=read(root/'progress.json')
                    for p in (folder/'progress.json',campaign/'progress.json',campaign/'report.json'):
                        atomic_json(p,state)
                    time.sleep(10)
            counts=cache_counts(root)
            report=dict(status='ANALYSIS_COMPLETE_RESEARCH_ONLY' if not counts['pending'] and not counts['invalid']
                else 'INCOMPLETE_ANALYSIS_NO_REPLAY',resume_folder=str(folder),analysis_exit_code=child.returncode,
                **counts,cloud_calls=0,broker_calls=0,finished_at_utc=datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            report=dict(status='FAILED_RESUME_NO_AUTOMATIC_RETRY',error_type=type(exc).__name__,error=str(exc),
                resume_folder=str(folder),**cache_counts(root),cloud_calls=0,broker_calls=0)
        for p in (folder/'report.json',folder/'progress.json',campaign/'report.json',campaign/'progress.json'):
            atomic_json(p,report)
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT)
    args=parser.parse_args()
    report=run(args.output_dir);print(json.dumps(report,ensure_ascii=False))
    if report['status'].startswith('FAILED'):raise SystemExit(1)


if __name__=='__main__':main()
