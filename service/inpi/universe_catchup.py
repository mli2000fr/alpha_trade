"""Finite FR catch-up passes, stopping on quotas/errors; no scheduler changes."""
import argparse
from datetime import UTC, datetime
import json

from service.fr.operational_batch_15a import ROOT, run
from service.inpi.files import atomic


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--max-passes',type=int,default=4)
    args=parser.parse_args()
    if not 1<=args.max_passes<=8: raise ValueError('Rattrapage borné à 1..8 passages')
    path=ROOT/'artifacts/fr/operations/fr_fundamentals_sync/catchup_progress.json'
    report={'status':'RUNNING','started_at':datetime.now(UTC).isoformat(),'passes':[],
            'canonical_go':False,'ml_usable':False}
    atomic(path,report)
    for _ in range(args.max_passes):
        result=run('fr_fundamentals_sync')
        report['passes'].append(result)
        report['updated_at']=datetime.now(UTC).isoformat()
        print(json.dumps({k:result.get(k) for k in ('status','received_count','failed_count','pending_issuers','pause_reason')}),flush=True)
        if result['status']=='FAILED': report['status']='FAILED'
        elif result.get('pause_reason'): report['status']='PAUSED_QUOTA'
        elif result.get('coverage_complete') or result.get('requested_count')==0: report['status']='COMPLETE_OR_NOT_DUE'
        atomic(path,report)
        if report['status']!='RUNNING': break
    if report['status']=='RUNNING': report['status']='PASS_BUDGET_REACHED'
    report['finished_at']=datetime.now(UTC).isoformat(); atomic(path,report)
    if report['status']=='FAILED': raise SystemExit(1)


if __name__=='__main__': main()
