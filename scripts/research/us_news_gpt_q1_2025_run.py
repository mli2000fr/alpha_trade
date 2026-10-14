"""Authorized bounded GPT analysis of immutable Q1 packets; never SQL or orders.

Do not alter prepared texts, scores or decision rules. No Web, automatic retry,
new prediction, training or price-outcome loading. Paid results are journaled.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import logging
import os
from pathlib import Path

from scripts.research import us_news_gpt_september_pilot as pilot
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

LOG=logging.getLogger(__name__)
BUDGET_USD=Decimal('0.50')


def payload_hash(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def paid_payload(packet,model):
    request=pilot.build_request(packet,model)
    # Never inherit Fast/Priority processing from a project default. This does
    # not change the prompt or schema; record the transport addition explicitly.
    request['service_tier']='default'
    return request


def request_inventory(packets,plan,model):
    if len(packets)!=len(plan):
        raise ValueError('Packet/plan mismatch')
    rows=[]
    for index,(packet,item) in enumerate(zip(packets,plan)):
        if (item['packet']!=index or item['symbol']!=packet['symbol']
                or item['decision_date']!=packet['decision_date']):
            raise ValueError('Changed packet order')
        if not item['planned_call']:
            if packet['articles']:
                raise ValueError('Text-bearing packet missing a qualified identity/paid plan')
            continue
        original=pilot.build_request(packet,model)
        if payload_hash(original)!=item['payload_sha256']:
            raise ValueError('Prepared input changed')
        request=paid_payload(packet,model)
        size,cost=pilot.token_cost_bound(request)
        if size>240000:
            raise ValueError('Short-context input budget exceeded')
        rows.append(dict(packet=index,symbol=packet['symbol'],decision_date=packet['decision_date'],
            prepared_request_sha256=item['payload_sha256'],request_sha256=payload_hash(request),
            request_bytes=size,cost_reservation_usd=cost))
    total=sum((Decimal(str(row['cost_reservation_usd'])) for row in rows),Decimal(0))
    if total>BUDGET_USD:
        raise ValueError(f'Refusing paid launch: conservative reservation {total} exceeds {BUDGET_USD}')
    return rows,total


def validate_usage(response,reservation):
    usage=response.get('usage') or {}
    if any(type(usage.get(k)) is not int or usage[k]<0 for k in ['input_tokens','output_tokens']):
        raise ValueError('Missing/invalid usage; never assume zero cost')
    if usage['output_tokens']>pilot.MAX_OUTPUT_TOKENS:
        raise ValueError('Unexpected output usage above approved ceiling')
    if response.get('service_tier') not in (None,'default'):
        raise ValueError('Unexpected paid processing tier; stop remaining calls')
    if not str(response.get('model','')).startswith('gpt-6-luna'):
        raise ValueError('Unexpected returned model; no silent substitution')
    if any(item.get('type','').endswith('_call') for item in response.get('output',[])):
        raise ValueError('Unexpected tool call in text-only pilot')
    cost=(Decimal(usage['input_tokens'])*Decimal('.10')+Decimal(usage['output_tokens'])*Decimal('.50'))/Decimal(1000000)
    if cost>Decimal(str(reservation)):
        raise ValueError('Observed usage exceeds conservative paid reservation')
    return dict(input_tokens=usage['input_tokens'],output_tokens=usage['output_tokens'],
        gross_cost_estimate_usd=float(cost),cached_discount_not_applied=True)


def freeze_authorization(root,*,budget_usd):
    if Decimal(str(budget_usd))!=BUDGET_USD:
        raise ValueError('User approved exactly 0.50 USD; do not expand the budget')
    prepared=pilot.read(root/'prepare.json');verify_hashes(root,prepared['files'])
    protocol=pilot.read(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    if prepared['status']!='PREPARED_AWAITING_PAID_ANALYSIS_GO' or prepared['planned_gpt_calls']!=213:
        raise ValueError('Expected approved complete 213-call preparation')
    packets=pilot.read(root/'packets.json');plan=pilot.read(root/'request-plan.json')
    rows,total=request_inventory(packets,plan,protocol['gpt_model'])
    marker=root/'analysis-protocol.json'
    if marker.exists():
        saved=pilot.read(marker);verify_hashes(Path('.'),saved['sources'])
        if (saved['prepared_sha256']!=digest(root/'prepare.json') or saved['request_inventory']!=rows
                or Decimal(str(saved['budget_usd']))!=BUDGET_USD):
            raise ValueError('Frozen paid authorization changed')
        return saved
    saved=dict(experiment='GPT_TOP10_Q1_2025_PAID_TEXT_ONLY',
        frozen_at_utc=datetime.now(timezone.utc).isoformat(),
        user_authorization='GO after explicit 0.50 USD cap proposal in current chat, 2026-10-14',
        budget_usd=float(BUDGET_USD),max_calls=len(rows),conservative_reserved_usd=float(total),
        prepared_sha256=digest(root/'prepare.json'),prepared_protocol_sha256=digest(root/'protocol.json'),
        prepared_inputs_unchanged=True,transport_addition={'service_tier':'default'},
        model=protocol['gpt_model'],request_inventory=rows,automatic_api_retries=False,
        first_paid_response_wins=True,tools=[],web=False,sql_writes=False,production_changes=False,
        actual_usage_estimate_excludes_taxes_fx_and_account_concurrent_jobs=True,
        analysis_rule='unchanged prepared primary veto; no tuning after responses or economic outcomes',
        sources={str(path):digest(path) for path in [Path(__file__),Path(pilot.__file__),
            Path('tests/test_us_news_gpt_q1_2025_run.py'),Path('common/verified_http.py')]})
    atomic_json(marker,saved)
    return saved


def run(root,*,budget_usd,transport=None):
    root=Path(root)
    authorization=freeze_authorization(root,budget_usd=budget_usd)
    if (root/'analysis.json').exists():
        result=pilot.read(root/'analysis.json');verify_hashes(root,result['files']);return result
    packets=pilot.read(root/'packets.json')
    lookup={row['packet']:row for row in authorization['request_inventory']}
    key=os.environ.get('OPENAI_API_KEY','')
    if transport is None and not key:
        raise ValueError('OPENAI_API_KEY absent; no paid attempt made')
    from common.verified_http import verified_session
    session=verified_session() if transport is None else None
    api=root/'api';api.mkdir(exist_ok=True)
    outcomes=[];usage_rows=[];files={};reserved=Decimal(0);new_calls=0
    try:
        for index,packet in enumerate(packets):
            if index not in lookup:
                outcomes.append(dict(decision_date=packet['decision_date'],symbol=packet['symbol'],
                    oracle_rank=packet['oracle_rank'],decision='UNKNOWN_NO_QUALIFIED_TEXT',confidence=None,
                    veto_long=False,reason='No supplied publication-qualified article',evidence=[]))
                continue
            inventory=lookup[index]
            reserved+=Decimal(str(inventory['cost_reservation_usd']))
            if reserved>BUDGET_USD:
                raise ValueError('Paid reservation budget exhausted BEFORE next call')
            payload=paid_payload(packet,authorization['model'])
            if payload_hash(payload)!=inventory['request_sha256']:
                raise ValueError('Paid request drift')
            prefix=api/f'{index:03d}-{packet["decision_date"]}-{packet["symbol"]}'
            request_path=prefix.with_suffix('.request.json');response_path=prefix.with_suffix('.response.json')
            if response_path.exists():
                if not request_path.exists() or pilot.read(request_path)!=payload:
                    raise ValueError('Cached paid response without identical request')
                response=pilot.read(response_path)
            else:
                if request_path.exists():
                    raise ValueError('Unresolved paid attempt; do not automatically pay again')
                atomic_json(request_path,payload)
                atomic_json(root/'analysis-progress.json',dict(status='GPT_RUNNING',completed_calls=len(usage_rows),
                    total_calls=len(lookup),current_symbol=packet['symbol'],current_date=packet['decision_date'],
                    reserved_usd=float(reserved),max_budget_usd=float(BUDGET_USD),automatic_retries=False))
                if transport is not None:
                    response=transport(payload)
                else:
                    try:
                        raw=session.post('https://api.openai.com/v1/responses',json=payload,
                            headers={'Authorization':f'Bearer {key}'},timeout=(10,60),allow_redirects=False)
                    except Exception as exc:
                        atomic_json(prefix.with_suffix('.error.json'),dict(error_type=type(exc).__name__,retry=False))
                        raise RuntimeError('OpenAI transport interrupted; attempt journaled, no retry') from None
                    if raw.status_code!=200:
                        atomic_json(prefix.with_suffix('.error.json'),dict(http_status=raw.status_code,
                            request_id=raw.headers.get('x-request-id'),retry=False))
                        raise RuntimeError(f'OpenAI HTTP {raw.status_code}; remaining calls stopped')
                    response=raw.json()
                atomic_json(response_path,response)
                new_calls+=1
            counted=validate_usage(response,inventory['cost_reservation_usd'])
            try:
                value=pilot.parse_assessment(response,packet)
            except Exception as exc:
                atomic_json(prefix.with_suffix('.invalid.json'),dict(error_type=type(exc).__name__,
                    error=str(exc)[:400],response_preserved=True,automatic_retry=False))
                raise ValueError(f'Paid answer invalid {packet["decision_date"]}/{packet["symbol"]}; saved, no retry') from None
            value.update(decision_date=packet['decision_date'],symbol=packet['symbol'],oracle_rank=packet['oracle_rank'])
            outcomes.append(value)
            usage_rows.append(dict(symbol=packet['symbol'],decision_date=packet['decision_date'],response_id=response.get('id'),
                model=response.get('model'),service_tier=response.get('service_tier'),usage=response.get('usage'),**counted))
            atomic_json(prefix.with_suffix('.assessment.json'),value)
            for path in [request_path,response_path,prefix.with_suffix('.assessment.json')]:
                files[str(path.relative_to(root))]=digest(path)
            actual=sum(row['gross_cost_estimate_usd'] for row in usage_rows)
            atomic_json(root/'usage.partial.json',usage_rows)
            atomic_json(root/'assessments.partial.json',outcomes)
            atomic_json(root/'analysis-progress.json',dict(status='GPT_RUNNING',completed_calls=len(usage_rows),
                total_calls=len(lookup),gross_cost_estimate_usd=actual,reserved_usd=float(reserved),
                decisions=dict(Counter(row['decision'] for row in outcomes)),
                vetoes=sum(row['veto_long'] for row in outcomes),new_calls_this_process=new_calls))
            if len(usage_rows)%10==0 or len(usage_rows)==len(lookup):
                LOG.info('GPT %d/%d cost_estimate=$%.6f vetoes=%d',len(usage_rows),len(lookup),actual,
                    sum(row['veto_long'] for row in outcomes))
    finally:
        if session is not None:session.close()
    if len(outcomes)!=len(packets) or len(usage_rows)!=len(lookup):
        raise ValueError('Incomplete paid panel; no selection published')
    atomic_json(root/'assessments.json',outcomes);atomic_json(root/'usage.json',usage_rows)
    for name in ['analysis-protocol.json','assessments.json','usage.json']:
        files[name]=digest(root/name)
    result=dict(status='ASSESSMENTS_FROZEN_BEFORE_OUTCOMES',completed_at_utc=datetime.now(timezone.utc).isoformat(),
        candidate_days=len(outcomes),actual_calls=len(usage_rows),new_calls_this_process=new_calls,
        automatic_retries=0,web_calls=0,decisions=dict(Counter(row['decision'] for row in outcomes)),
        vetoed=sum(row['veto_long'] for row in outcomes),
        input_tokens=sum(row['input_tokens'] for row in usage_rows),
        output_tokens=sum(row['output_tokens'] for row in usage_rows),
        gross_cost_estimate_usd=sum(row['gross_cost_estimate_usd'] for row in usage_rows),
        max_budget_usd=float(BUDGET_USD),conservative_reserved_usd=float(reserved),
        files=files)
    atomic_json(root/'analysis.json',result)
    atomic_json(root/'analysis-progress.json',result)
    return result


def main():
    from scripts.research.oracle_path_confirmation import exclusive_run
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--max-cost-usd',type=Decimal,required=True)
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with exclusive_run(args.output):
        try:
            result=run(args.output,budget_usd=args.max_cost_usd)
            print(json.dumps({k:v for k,v in result.items() if k!='files'},default=str))
        except Exception as exc:
            atomic_json(args.output/'analysis-progress.json',dict(status='STOPPED_NO_AUTOMATIC_RETRY',
                error=f'{type(exc).__name__}: {str(exc)[:600]}',max_budget_usd=float(BUDGET_USD)))
            raise


if __name__=='__main__':main()
