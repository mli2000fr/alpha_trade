"""Collect remaining authorized answers once, with strict validity and cache costs.

Preserve the original runner, authorization, prompts and paid replies. Invalid
evidence stays UNKNOWN_INVALID_RESPONSE, never ABSTAIN/BEARISH or a veto. No live
publication. A subsequent portfolio is a valid-replies-only diagnostic if any
technical answer is invalid, not a completed qualification of the full filter.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import json
import logging
import os
from pathlib import Path

from scripts.research import us_news_gpt_q1_2025_run as initial
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

pilot=initial.pilot
LOG=logging.getLogger(__name__)
CAP=Decimal('.50')


def usage_with_cache(response):
    usage=response.get('usage') or {}
    details=usage.get('input_tokens_details') or {}
    values=[usage.get('input_tokens'),usage.get('output_tokens'),
            details.get('cache_write_tokens',0),details.get('cached_tokens',0)]
    if any(type(x) is not int or x<0 for x in values):
        raise ValueError('Unknown/invalid billable usage; no zero assumption')
    inputs,outputs,writes,cached=values
    if writes+cached>inputs or outputs>pilot.MAX_OUTPUT_TOKENS:
        raise ValueError('Inconsistent usage')
    if response.get('service_tier') not in (None,'default') or not str(response.get('model','')).startswith('gpt-6-luna'):
        raise ValueError('Unexpected processing tier/model')
    if any(item.get('type','').endswith('_call') for item in response.get('output',[])):
        raise ValueError('Unexpected tool call')
    # Ignore cache-read discount for a conservative estimate, but DO include
    # the .125 vs .10 surcharge on cache-written input tokens.
    gross=(Decimal(inputs)*Decimal('.10')+Decimal(writes)*Decimal('.025')+
           Decimal(outputs)*Decimal('.50'))/Decimal(1000000)
    return dict(input_tokens=inputs,output_tokens=outputs,cache_write_tokens=writes,cached_tokens=cached,
        gross_cost_estimate_usd=float(gross),cached_discount_not_applied=True)


def worst_call_cost(payload):
    size=len(json.dumps(payload,ensure_ascii=False).encode('utf-8'))
    if size>240000:raise ValueError('Oversized short-context request')
    return (Decimal(size+2000)*Decimal('.125')+Decimal(pilot.MAX_OUTPUT_TOKENS)*Decimal('.50'))/Decimal(1000000)


def qualify_or_unknown(response,packet):
    try:
        value=pilot.parse_assessment(response,packet)
        value['technical_status']='VALID'
    except Exception as exc:
        value=dict(decision='UNKNOWN_INVALID_RESPONSE',confidence=None,veto_long=False,
            reason=f'{type(exc).__name__}: {str(exc)[:350]}',evidence=[],technical_status='INVALID_PRESERVED')
    value.update(decision_date=packet['decision_date'],symbol=packet['symbol'],oracle_rank=packet['oracle_rank'])
    return value


def freeze(root):
    prepared=pilot.read(root/'prepare.json');verify_hashes(root,prepared['files'])
    protocol=pilot.read(root/'protocol.json');verify_hashes(Path('.'),protocol['sources'])
    authorization=pilot.read(root/'analysis-protocol.json');verify_hashes(Path('.'),authorization['sources'])
    if Decimal(str(authorization['budget_usd']))!=CAP:
        raise ValueError('Unapproved budget')
    marker=root/'analysis-continuation.json'
    if marker.exists():
        saved=pilot.read(marker);verify_hashes(Path('.'),saved['sources'])
        if saved['authorization_sha256']!=digest(root/'analysis-protocol.json'):
            raise ValueError('Authorization changed')
        return authorization
    amendment=dict(recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        authorization_sha256=digest(root/'analysis-protocol.json'),earlier_stop=pilot.read(root/'analysis-progress.json'),
        prompt_schema_threshold_dates_unmodified=True,no_paid_retry=True,no_outcomes_loaded=True,
        invalid_evidence_policy='retain original answer, mark UNKNOWN_INVALID_RESPONSE, no veto; no live qualification',
        economic_label_if_invalid='VALID_REPLIES_ONLY_EXPLORATORY_DIAGNOSTIC_NOT_FULL_FILTER_VALIDATION',
        budget_policy='observed conservative spend INCLUDING cache writes + worst next request <=0.50 USD before each call',
        maximum_possible_input_rate_per_million=.125,output_rate_per_million=.50,
        original_all_call_reservation_did_not_include_cache_write_premium=True,
        cap_usd=.50,stop_if_unknown_spend_or_ambiguous_request=True,
        sources={str(path):digest(path) for path in [Path(__file__),Path('tests/test_us_news_gpt_q1_2025_continue.py')]})
    atomic_json(marker,amendment)
    return authorization


def run(root,*,transport=None):
    root=Path(root);authorization=freeze(root)
    if (root/'analysis.json').exists():
        saved=pilot.read(root/'analysis.json');verify_hashes(root,saved['files']);return saved
    packets=pilot.read(root/'packets.json')
    inventory={item['packet']:item for item in authorization['request_inventory']}
    api=root/'api'
    # Account for EVERY already-paid response, including the invalid one.
    already_spent=Decimal(0)
    for request in api.glob('*.request.json'):
        response=request.with_name(request.name.replace('.request.json','.response.json'))
        if not response.exists():
            raise ValueError('Unresolved paid attempt; cannot retry/estimate its spend safely')
        already_spent+=Decimal(str(usage_with_cache(pilot.read(response))['gross_cost_estimate_usd']))
    if already_spent>CAP:raise ValueError('Approved spend exhausted')
    key=os.environ.get('OPENAI_API_KEY','')
    if transport is None and not key:raise ValueError('OPENAI_API_KEY absent')
    from common.verified_http import verified_session
    session=verified_session() if transport is None else None
    outcomes=[];usage_rows=[];files={};new_calls=0;spent=already_spent
    try:
        for index,packet in enumerate(packets):
            if index not in inventory:
                outcomes.append(dict(decision_date=packet['decision_date'],symbol=packet['symbol'],
                    oracle_rank=packet['oracle_rank'],decision='UNKNOWN_NO_QUALIFIED_TEXT',confidence=None,
                    veto_long=False,reason='No supplied publication-qualified article',evidence=[],technical_status='NO_INPUT'))
                continue
            request=initial.paid_payload(packet,authorization['model'])
            if initial.payload_hash(request)!=inventory[index]['request_sha256']:
                raise ValueError('Changed frozen paid input')
            prefix=api/f'{index:03d}-{packet["decision_date"]}-{packet["symbol"]}'
            request_path=prefix.with_suffix('.request.json');response_path=prefix.with_suffix('.response.json')
            if response_path.exists():
                if pilot.read(request_path)!=request:raise ValueError('Cached request mismatch')
                response=pilot.read(response_path)
            else:
                if request_path.exists():raise ValueError('Unresolved paid request')
                worst=worst_call_cost(request)
                if spent+worst>CAP:
                    raise ValueError('Hard cap reached BEFORE next call, including worst-case cache writes')
                atomic_json(prefix.with_suffix('.reservation.json'),dict(spent_before_usd=float(spent),
                    worst_next_call_usd=float(worst),cap_usd=float(CAP)))
                atomic_json(request_path,request)
                if transport is not None:
                    response=transport(request)
                else:
                    try:
                        raw=session.post('https://api.openai.com/v1/responses',json=request,
                            headers={'Authorization':f'Bearer {key}'},timeout=(10,60),allow_redirects=False)
                    except Exception as exc:
                        atomic_json(prefix.with_suffix('.error.json'),dict(error_type=type(exc).__name__,retry=False))
                        raise RuntimeError('OpenAI transport interrupted; no retry') from None
                    if raw.status_code!=200:
                        atomic_json(prefix.with_suffix('.error.json'),dict(http_status=raw.status_code,
                            request_id=raw.headers.get('x-request-id'),retry=False))
                        raise RuntimeError(f'OpenAI HTTP {raw.status_code}; stop, no retry')
                    response=raw.json()
                atomic_json(response_path,response);new_calls+=1
                counted=usage_with_cache(response)
                cost=Decimal(str(counted['gross_cost_estimate_usd']))
                if cost>worst:raise ValueError('Usage exceeded worst next-call bound')
                spent+=cost
            counted=usage_with_cache(response)
            value=qualify_or_unknown(response,packet)
            atomic_json(prefix.with_suffix('.strict-qualification.json'),value)
            outcomes.append(value)
            usage_rows.append(dict(symbol=packet['symbol'],decision_date=packet['decision_date'],
                response_id=response.get('id'),model=response.get('model'),service_tier=response.get('service_tier'),
                usage=response.get('usage'),**counted))
            for path in [request_path,response_path,prefix.with_suffix('.strict-qualification.json')]:
                files[str(path.relative_to(root))]=digest(path)
            atomic_json(root/'usage.partial.json',usage_rows);atomic_json(root/'assessments.partial.json',outcomes)
            atomic_json(root/'analysis-progress.json',dict(status='GPT_RUNNING_STRICT_QUALIFICATION',
                completed_calls=len(usage_rows),total_calls=len(inventory),gross_cost_estimate_usd=float(spent),
                max_budget_usd=float(CAP),new_calls_this_process=new_calls,
                invalid_responses=sum(v['technical_status']=='INVALID_PRESERVED' for v in outcomes),
                decisions=dict(Counter(v['decision'] for v in outcomes)),vetoes=sum(v['veto_long'] for v in outcomes)))
            if len(usage_rows)%10==0 or len(usage_rows)==len(inventory):
                LOG.info('GPT %d/%d cost_with_cache_writes=$%.6f veto=%d invalid=%d',len(usage_rows),len(inventory),float(spent),
                    sum(v['veto_long'] for v in outcomes),sum(v['technical_status']=='INVALID_PRESERVED' for v in outcomes))
    finally:
        if session is not None:session.close()
    invalid=sum(v['technical_status']=='INVALID_PRESERVED' for v in outcomes)
    if len(outcomes)!=len(packets) or len(usage_rows)!=len(inventory):raise ValueError('Incomplete frozen panel')
    atomic_json(root/'assessments.json',outcomes);atomic_json(root/'usage.json',usage_rows)
    for name in ['analysis-protocol.json','analysis-continuation.json','assessments.json','usage.json']:
        files[name]=digest(root/name)
    saved=dict(status='FROZEN_VALID_REPLIES_ONLY_WITH_TECHNICAL_UNKNOWNS' if invalid else 'ASSESSMENTS_FROZEN_BEFORE_OUTCOMES',
        completed_at_utc=datetime.now(timezone.utc).isoformat(),candidate_days=len(outcomes),actual_calls=len(usage_rows),
        new_calls_in_continuation=new_calls,automatic_retries=0,web_calls=0,invalid_responses=invalid,
        full_filter_qualified=not bool(invalid),vetoed=sum(v['veto_long'] for v in outcomes),
        decisions=dict(Counter(v['decision'] for v in outcomes)),
        input_tokens=sum(v['input_tokens'] for v in usage_rows),output_tokens=sum(v['output_tokens'] for v in usage_rows),
        cache_write_tokens=sum(v['cache_write_tokens'] for v in usage_rows),cached_tokens=sum(v['cached_tokens'] for v in usage_rows),
        gross_cost_estimate_usd=float(spent),max_budget_usd=float(CAP),cache_write_premium_included=True,
        no_price_outcomes_read=True,no_production_publication=True,files=files)
    atomic_json(root/'analysis.json',saved);atomic_json(root/'analysis-progress.json',saved)
    return saved


def main():
    from scripts.research.oracle_path_confirmation import exclusive_run
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    with exclusive_run(args.output):
        try:
            result=run(args.output);print(json.dumps({k:v for k,v in result.items() if k!='files'},default=str))
        except Exception as exc:
            atomic_json(args.output/'analysis-progress.json',dict(status='STOPPED_NO_AUTOMATIC_RETRY',
                error=f'{type(exc).__name__}: {str(exc)[:500]}',max_budget_usd=float(CAP)))
            raise


if __name__=='__main__':main()
