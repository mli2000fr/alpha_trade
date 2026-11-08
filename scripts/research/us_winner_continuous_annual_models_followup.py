"""Local coordinator for this requested replay, no inference/provider/broker calls."""
import argparse
from datetime import datetime,timezone
from pathlib import Path
import json
import subprocess
import sys
import time

from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json
from scripts.research.us_winner_continuous_annual_models_20261108 import ROOT,POLICIES,read


def run(root):
    folder=root/'coordinator';folder.mkdir(exist_ok=True)
    with exclusive_run(folder):
        if (folder/'report.json').exists():raise ValueError('Coordinateur déjà terminé ; vérifier le bilan')
        started=time.monotonic()
        while not (root/'inputs/manifest.json').is_file():
            state=read(root/'progress.json') if (root/'progress.json').exists() else {}
            if state.get('status')=='FAILED':raise ValueError('Préparation en échec : '+state.get('error',''))
            if time.monotonic()-started>12*3600:raise TimeoutError('Préparation non terminée après12h ; aucune relance automatique')
            atomic_json(folder/'progress.json',dict(status='WAITING_FOR_FROZEN_INPUTS',input_progress=state,
                updated_at_utc=datetime.now(timezone.utc).isoformat()))
            time.sleep(10)
        request=read(root/'replay-request.json');policy=request['selection_policy']
        if policy not in POLICIES:raise ValueError('Politique de sélection non qualifiée')
        atomic_json(folder/'selected-policy.json',dict(**request,started_at_utc=datetime.now(timezone.utc).isoformat()))
        command=[sys.executable,'-X','utf8','-u','-m','scripts.research.us_winner_continuous_annual_models_20261108',
            'replay','--output-dir',str(root),'--selection-policy',policy]
        with (folder/'replay.log').open('x',encoding='utf-8') as log:
            child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            atomic_json(folder/'child.json',dict(pid=child.pid,command=command))
            while child.poll() is None:
                progress=read(root/'progress.json')
                atomic_json(folder/'progress.json',dict(status='REPLAYING_CONTINUOUS',policy=policy,replay_progress=progress))
                time.sleep(10)
        target=root/('continuous-'+policy)/'report.json'
        status='COMPLETED_EXPLORATORY' if child.returncode==0 and target.exists() else 'FAILED_NO_AUTOMATIC_RETRY'
        report=dict(status=status,selection_policy=policy,replay_exit_code=child.returncode,
            output=str(target.parent),finished_at_utc=datetime.now(timezone.utc).isoformat(),
            broker_calls=0,provider_calls=0,SQL_writes=0)
        atomic_json(folder/'report.json',report);atomic_json(folder/'progress.json',report)
        return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT)
    args=parser.parse_args()
    try:result=run(args.output_dir)
    except Exception as exc:
        result=dict(status='FAILED_NO_AUTOMATIC_RETRY',error_type=type(exc).__name__,error=str(exc))
        folder=args.output_dir/'coordinator';folder.mkdir(exist_ok=True)
        atomic_json(folder/'report.json',result);atomic_json(folder/'progress.json',result)
    print(json.dumps(result,ensure_ascii=False))
    if result['status']!='COMPLETED_EXPLORATORY':raise SystemExit(1)


if __name__=='__main__':main()
