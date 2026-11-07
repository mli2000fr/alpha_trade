"""User-authorized one-pass recovery of ambiguous GPT attempts, within $2 total.

Keep the original immutable protocol, all receipts and cache records. An explicit
new resume authorization adds a conservative reservation for each extra attempt.
No valid or invalid received answer is automatically purchased again.
"""
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import json
from pathlib import Path
import shutil
import time
import uuid

from scripts.research import us_gpt_winner_ab as base
from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from service.local_ai.research_veto import Cache, encoded


def extra_reservations(root):
    return sum((Decimal(base.read(p)['extra_reservation_usd'])
                for p in (root/'resume-attempts').glob('*/authorization.json')),Decimal(0))


def ambiguity_plan(root,packets):
    cache=Cache(root/'analyses.sqlite3');ambiguous=[]
    try:
        for p in packets:
            if not p['context']['news'] or cache.latest(p['key']) is not None:
                continue
            prefix=root/'api'/p['key']
            req=prefix.with_suffix('.request.json');raw=prefix.with_suffix('.response.json')
            if req.exists() and base.read(req)!=p['request']:
                raise ValueError('Requête de journal différente du dossier figé')
            if req.exists() and not raw.exists():
                ambiguous.append(p)
    finally:cache.close()
    return ambiguous


def authorize(root,plan,ambiguous):
    previous=extra_reservations(root)
    extra=sum((base.reservation(p['request']) for p in ambiguous),Decimal(0))
    total=Decimal(plan['maximum_reserved_usd'])+previous+extra
    if total>base.BUDGET:
        raise ValueError(f'Reprise refusée avant appel : réservation cumulée {total} > {base.BUDGET} USD')
    value=dict(authorized_at_utc=datetime.now(timezone.utc).isoformat(),
        user_authorization='Reprend test gpt — explicit user resume, 2026-11-07',
        original_protocol_sha256=digest(root/'protocol.json'),resume_code_sha256=digest(Path(__file__)),
        original_reserved_usd=plan['maximum_reserved_usd'],prior_extra_reservation_usd=str(previous),
        extra_reservation_usd=str(extra),cumulative_maximum_reserved_usd=str(total),budget_usd=str(base.BUDGET),
        ambiguous=[dict(request_key=p['key'],symbol=p['symbol'],date=p['signal_date'],
            maximum_reservation_usd=str(base.reservation(p['request']))) for p in ambiguous],
        automatic_retries=False,existing_answers_recalled=False,prompt_and_decision_rules_unchanged=True)
    return value


def recover(root,transport=None):
    with exclusive_run(root):
        plan,packets=base.verify(root)
        ambiguous=ambiguity_plan(root,packets)
        authorization=authorize(root,plan,ambiguous)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]
        folder=root/'resume-attempts'/stamp;folder.mkdir(parents=True,exist_ok=False)
        for name in ('report.json','progress.json','analysis-report.json'):
            if (root/name).exists():shutil.copyfile(root/name,folder/('before-'+name))
        atomic_json(folder/'authorization.json',authorization)
        atomic_json(root/'report.json',dict(status='RUNNING_AUTHORIZED_RESUME',resume_folder=str(folder),
            maximum_reserved_usd=authorization['cumulative_maximum_reserved_usd']))
        atomic_json(root/'progress.json',dict(status='RECOVERING_AUTHORIZED_GPT_ATTEMPT',
            maximum_reserved_usd=authorization['cumulative_maximum_reserved_usd'],
            retry_count=len(ambiguous),resume_folder=str(folder)))
        client=None
        try:
            for p in ambiguous:
                prefix=folder/p['key'];req=prefix.with_suffix('.request.json')
                with req.open('x',encoding='utf8') as f:f.write(encoded(p['request']))
                print(encoded(dict(status='RETRY_AUTHORIZED_ONCE',symbol=p['symbol'],date=p['signal_date'],
                    cumulative_maximum_reserved_usd=authorization['cumulative_maximum_reserved_usd'])),flush=True)
                started=time.monotonic()
                if transport is not None:
                    raw=transport(p['request'])
                else:
                    if client is None:
                        from service.llm_directional.openai_client import ResponsesClient
                        from service.llm_directional.config import FilterConfig
                        client=ResponsesClient(FilterConfig(model=base.MODEL,provider='openai',
                            analysis_mode='local_data_only',max_output_tokens=16384,timeout_seconds=600))
                    raw=client(p['request'])
                atomic_json(prefix.with_suffix('.response.json'),raw)
                counted=base.cost_for(raw,p['request']);base.normalize(raw,p['request'])
                destination=(root/'api'/p['key']).with_suffix('.response.json')
                # Backfill a missing receipt only; never overwrite an old result.
                with destination.open('x',encoding='utf8') as f:f.write(encoded(raw))
                atomic_json(prefix.with_suffix('.recovery.json'),dict(receipt_backfilled=True,
                    elapsed_seconds=time.monotonic()-started,consumption=counted,
                    original_ambiguous_charge_unknown=True,old_request_journal_preserved=True))
            result=dict(status='AMBIGUOUS_RECEIPTS_RECOVERED',new_calls=len(ambiguous),authorization=authorization)
            atomic_json(folder/'recovery-report.json',result)
            return folder,result
        except Exception as exc:
            error=dict(status='RESUME_FAILED_NO_AUTOMATIC_RETRY',error_type=type(exc).__name__,error=str(exc),
                maximum_reserved_usd=authorization['cumulative_maximum_reserved_usd'],resume_folder=str(folder))
            atomic_json(folder/'recovery-report.json',error)
            atomic_json(root/'report.json',error);atomic_json(root/'progress.json',error)
            raise
        finally:
            if client is not None:client.session.close()


def run(root):
    folder,result=recover(root)
    report=base.run(root)  # Reuses all 155 old receipts plus recovered VAC, then remaining originals.
    report['resume']=dict(folder=str(folder),extra_calls=result['new_calls'],
        cumulative_maximum_reserved_usd=result['authorization']['cumulative_maximum_reserved_usd'],
        original_ambiguous_charge_unknown=True)
    atomic_json(folder/'final-report.json',report)
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output-dir',type=Path,default=base.ROOT)
    a=p.parse_args();report=run(a.output_dir)
    print(encoded({k:v for k,v in report.items() if k not in ('arms','model_comparison')}))


if __name__=='__main__':main()
