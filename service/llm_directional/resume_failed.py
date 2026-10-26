"""Explicit bounded paid retry, append-only child run; valid answers are reused.

Only failed symbols may call the provider. Their local packets are refreshed;
the inherited answers, ranks, request/response bytes and expiry are not changed.
No Oracle inference, risk process, order or implicit automatic retry.
"""
import argparse
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import re

from sqlalchemy import select

from .config import FilterConfig
from .openai_client import ResponsesClient,build_request
from .repository import Repository,runs,digest,dumps,utcnow
from .validation import parse_response,select_symbols
from . import runner


def naive_utc(stamp):
    return stamp.astimezone(timezone.utc).replace(tzinfo=None) if stamp.tzinfo else stamp


def equivalent_resumed_request(actual, expected):
    """Only JSON object ordering in the input string may differ after refresh.

    The caller must first verify resume lineage and limit this to retried symbols.
    Prompts, schema, model and every other request field remain exact matches.
    """
    if not isinstance(actual,dict) or not isinstance(expected,dict) or set(actual)!=set(expected):
        return False
    if any(actual[k]!=expected[k] for k in expected if k!='input'):
        return False
    def unique_object(pairs):
        result={}
        for key,value in pairs:
            if key in result:raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def reject_constant(value):
        raise ValueError('Non-finite JSON constant')
    try:
        if not isinstance(actual.get('input'),str) or not isinstance(expected.get('input'),str):
            return False
        left=json.loads(actual['input'],object_pairs_hook=unique_object,parse_constant=reject_constant)
        right=json.loads(expected['input'],object_pairs_hook=unique_object,parse_constant=reject_constant)
        # Canonical encoding distinguishes JSON numbers from booleans (1 != true).
        return isinstance(left,dict) and isinstance(right,dict) and dumps(left)==dumps(right)
    except (ValueError,TypeError):
        return False


def prepare(engine,parent_id,expected_symbols,now,timeout_seconds=300):
    parent,items=Repository(engine).get(parent_id)
    snapshot=json.loads(parent['input_json']);cfg=FilterConfig(**json.loads(parent['config_json']))
    now=naive_utc(now)
    if (parent['status']!='FAILED' or parent['risk_started_at'] or parent['risk_run_id']
            or parent['execution_started_at'] or snapshot.get('research_only') or snapshot.get('resume')
            or digest(snapshot)!=parent['input_sha256'] or not parent['completed_at']):
        raise ValueError('Parent failed, unused, original and unaltered required for bounded resume')
    deadline=parent['completed_at']+timedelta(hours=cfg.max_run_age_hours)
    if now>deadline:raise ValueError('Parent analysis expired; its valid answers cannot be renewed by a retry')
    runner.validate_analysis_window(parent['trade_date'],now=now.replace(tzinfo=timezone.utc))
    if cfg.provider!='openai' or cfg.analysis_mode!='local_data_only':
        raise ValueError('This bounded resume qualifies OpenAI local_data_only only')
    contexts={c['symbol']:c for c in snapshot['candidates']}
    if (len(contexts)!=len(items) or {i['symbol'] for i in items}!=set(contexts)
            or parent['protocol_version']!=runner._protocol(snapshot['candidates'])):
        raise ValueError('Parent candidate/protocol archive incomplete')
    failed={i['symbol'] for i in items if i['status']=='FAILED'}
    if not failed or failed!=set(expected_symbols) or len(expected_symbols)!=len(failed):
        raise ValueError('Failed symbol set differs from explicitly authorized subset')
    config=replace(cfg,timeout_seconds=timeout_seconds)
    valid=[]
    for item in items:
        context=contexts[item['symbol']]
        if (item['oracle_rank']!=context['oracle_rank']
                or not runner._oracle_score_matches_snapshot(item['oracle_score'],context['oracle_score'])
                or json.loads(item['request_json'])!=build_request(context,cfg)):
            raise ValueError('Parent ranking/request differs from hashed snapshot')
        if item['status']=='FAILED':continue
        if item['status']!='VALID':raise ValueError('Unresolved parent answer')
        raw=json.loads(item['response_json'])
        if digest(raw)!=item['response_sha256']:raise ValueError('Parent raw answer altered')
        parsed=parse_response(raw,item['symbol'],cfg,item['observed_at'],context=context)
        saved=json.loads(item['assessment_json'])
        if any(saved.get(k)!=v for k,v in parsed.items()):raise ValueError('Parent assessment altered')
        # Timeout is a transport setting only, never a changed question/schema.
        if build_request(context,config)!=json.loads(item['request_json']):raise ValueError('Retry changes valid requests')
        valid.append(item)
    return parent,snapshot,config,items,valid,deadline


def refresh_failed(engine,context,config,now):
    from sqlalchemy import text
    from .fresh_evidence import enrich_contexts,validate_fresh_packet
    fields=('symbol','oracle_rank','oracle_score','issuer_reference','trade_date','horizon_sessions',
        'prices_through_decision_date','oracle_target','oracle_directional')
    base={k:deepcopy(context[k]) for k in fields if k in context}
    with engine.connect() as conn:
        identity=conn.execute(text('SELECT company_name,exchange FROM stock_metadata WHERE symbol=:symbol'),
            {'symbol':context['symbol']}).mappings().one()
    if dict(identity)!=context['issuer_reference']:raise ValueError('Issuer identity changed; review before retry')
    base['observed_at_utc']=str(now)
    fresh=enrich_contexts(engine,[base],config,now.replace(tzinfo=timezone.utc))[0]
    validate_fresh_packet(fresh,config,now,before_call=True)
    return fresh


def public_payload_check(context,request):
    """Permit only the financial-research packet; never brokerage/secrets data."""
    allowed={'analysis_mode','analysis_protocol','assessment_objective','direction_score_policy',
        'evidence_cutoff_utc','evidence_exclusions','freshness_policy','horizon_sessions','issuer_reference',
        'local_data_status','local_evidence','local_evidence_sha256','observed_at_utc','oracle_directional',
        'oracle_rank','oracle_score','oracle_target','prices_through_decision_date','symbol','trade_date'}
    if set(context)-allowed:raise ValueError('Unexpected context fields in outbound financial packet')
    if request.get('tools') or request.get('tool_choice')!='none':raise ValueError('Bounded retry cannot use external search/tools')
    forbidden={'password','api_key','authorization','secret','broker_account','account_equity','holdings','positions'}
    def check(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if str(key).lower() in forbidden:raise ValueError('Private/secret field in outbound packet')
                check(item)
        elif isinstance(value,list):
            for item in value:check(item)
        elif isinstance(value,str) and re.search(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}',value):
            raise ValueError('Possible secret in outbound packet')
    check(context)
    kinds={s['kind'] for s in context.get('local_evidence',[])}
    if kinds-{'consensus','news','earnings_calendar','sec','price_volume','fundamentals'}:
        raise ValueError('Unqualified outbound evidence family')
    return dict(symbol=context['symbol'],issuer=context['issuer_reference'],model=request['model'],
        analysis_mode=context['analysis_mode'],request_sha256=digest(request),
        context_fields=sorted(context),local_evidence_counts={k:sum(s['kind']==k for s in context['local_evidence']) for k in sorted(kinds)},
        max_output_tokens=request['max_output_tokens'],web_tools=0,private_brokerage_fields=0)


def validate_resume_lineage(engine,run,snapshot,now):
    """Downstream guard: cloning an answer never grants it another 24 hours."""
    resume=snapshot['resume'];parent,items=Repository(engine).get(resume['parent_run_id'])
    cfg=FilterConfig(**json.loads(parent['config_json']))
    deadline=parent['completed_at']+timedelta(hours=cfg.max_run_age_hours)
    if (resume['parent_input_sha256']!=parent['input_sha256']
            or digest(json.loads(parent['input_json']))!=parent['input_sha256']
            or resume['inherited_valid_until_utc']!=deadline.isoformat()
            or naive_utc(now)>deadline):
        raise ValueError('Resumed LLM inherited deadline/parent snapshot invalid or expired')
    child_cfg=FilterConfig(**json.loads(run['config_json']))
    if replace(cfg,timeout_seconds=child_cfg.timeout_seconds)!=child_cfg:
        raise ValueError('Resume changed policy/model instead of transport timeout only')
    _,child_items=Repository(engine).get(run['run_id'])
    old={i['symbol']:i for i in items};new={i['symbol']:i for i in child_items}
    expected_reused={i['symbol'] for i in items if i['status']=='VALID'}
    expected_failed={i['symbol'] for i in items if i['status']=='FAILED'}
    if (set(resume['reused_symbols'])!=expected_reused or set(resume['retried_symbols'])!=expected_failed
            or set(new)!=set(old) or parent['status']!='FAILED'):
        raise ValueError('Resume candidate lineage mismatch')
    contexts={c['symbol']:c for c in snapshot['candidates']}
    old_contexts={c['symbol']:c for c in json.loads(parent['input_json'])['candidates']}
    for symbol in expected_reused:
        for field in ('observed_at','request_json','response_json','response_sha256','assessment_json','sources_json'):
            if old[symbol][field]!=new[symbol][field]:raise ValueError('Reused answer changed: '+symbol+'/'+field)
        if contexts[symbol]!=old_contexts[symbol]:raise ValueError('Reused evidence context changed')


def resume(*,engine,parent_id,expected_symbols,run_id,output_dir,client=None,refresher=refresh_failed,
           now=None,timeout_seconds=300,check_account=True):
    now=naive_utc(now or utcnow());repo=Repository(engine)
    # Deterministic explicit ID prevents a second paid call after an ambiguous attempt.
    with engine.connect() as conn:
        if conn.execute(select(runs.c.run_id).where(runs.c.run_id==run_id)).first():
            raise ValueError('Resume ID already exists; inspect its result, no automatic paid replay')
    parent,snapshot,config,items,valid,deadline=prepare(engine,parent_id,expected_symbols,now,timeout_seconds)
    if check_account:runner.assert_paper_account(config.account_id)
    contexts={c['symbol']:deepcopy(c) for c in snapshot['candidates']}
    for symbol in expected_symbols:
        contexts[symbol]=refresher(engine,contexts[symbol],config,now)
    chosen=sorted(contexts.values(),key=lambda c:c['oracle_rank'])
    child=deepcopy(snapshot)
    child.update(candidates=chosen,parent_run_id=parent_id,resume=dict(parent_run_id=parent_id,
        parent_input_sha256=parent['input_sha256'],inherited_valid_until_utc=deadline.isoformat(),
        reused_symbols=[i['symbol'] for i in valid],retried_symbols=list(expected_symbols),
        evidence_refreshed_for_failed_only=True))
    output=Path(output_dir);output.mkdir(parents=True,exist_ok=False)
    repo.create(run_id=run_id,trade_date=parent['trade_date'],batch_id=parent['batch_id'],account_id=parent['account_id'],
        status='RUNNING',started_at=now,config_json=dumps(config.snapshot()),input_json=dumps(child),
        input_sha256=digest(child),protocol_version=parent['protocol_version'])
    decisions=[];errors=[]
    clock=(lambda:naive_utc(utcnow())) if client is None else (lambda:now)
    try:
        for item in valid:
            fields={k:item[k] for k in ('symbol','oracle_rank','oracle_score','observed_at','request_json','response_json','response_sha256')}
            repo.record(run_id=run_id,**fields,status='RECEIVED',selected=False)
            parsed=json.loads(item['assessment_json']);decisions.append(parsed)
            repo.finalize_assessment(run_id,item['symbol'],status='VALID',parsed=parsed,error=None)
        transport=client or ResponsesClient(config)
        from .fresh_evidence import validate_fresh_packet
        for symbol in expected_symbols:
            context=contexts[symbol];request=build_request(json.loads(dumps(context)),config);raw=None;error=None;parsed=None
            public_payload_check(context,request)
            observed=clock()
            try:
                runner.validate_analysis_window(parent['trade_date'],now=observed.replace(tzinfo=timezone.utc))
                if observed>deadline:raise ValueError('Parent deadline reached before paid retry')
                validate_fresh_packet(context,config,observed,before_call=True)
                logging.info('Single authorized GPT retry symbol=%s timeout=%s reused=%s',symbol,config.timeout_seconds,len(valid))
                raw=transport(request);observed=clock()
            except Exception as exc:error=type(exc).__name__+': '+str(exc)[:600]
            repo.record(run_id=run_id,symbol=symbol,oracle_rank=context['oracle_rank'],oracle_score=context['oracle_score'],
                observed_at=observed,request_json=dumps(request),response_json=dumps(raw) if raw is not None else None,
                response_sha256=digest(raw) if raw is not None else None,status='RECEIVED',selected=False)
            try:
                if error:raise RuntimeError(error)
                parsed=parse_response(raw,symbol,config,observed,context=context)
                parsed['oracle_rank']=context['oracle_rank'];decisions.append(parsed)
            except Exception as exc:error=type(exc).__name__+': '+str(exc)[:600];errors.append(symbol+': '+error)
            repo.finalize_assessment(run_id,symbol,status='FAILED' if error else 'VALID',parsed=parsed,error=error)
        finished=clock()
        runner.validate_analysis_window(parent['trade_date'],now=finished.replace(tzinfo=timezone.utc))
        if finished>deadline:raise ValueError('Parent analysis expired during retry')
        selected=[] if errors else select_symbols(decisions,config)
        current_run,_=repo.get(run_id)
        validate_resume_lineage(engine,current_run,child,finished)
        repo.finish(run_id,'FAILED' if errors else 'COMPLETED',selected,'\n'.join(errors) or None)
    except Exception:
        try:repo.finish(run_id,'FAILED',[],'Bounded resume interrupted; inspect archive before any retry')
        except Exception:pass
        raise
    if errors:raise RuntimeError('Bounded GPT retry failed; original valid answers preserved; '+str(errors))
    run,_=repo.get(run_id);validate_resume_lineage(engine,run,child,finished)
    from .report import report
    view=report(engine,run_id)
    view['resume']=child['resume']
    (output/'report.json').write_text(dumps(view),encoding='utf-8')
    return view


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--parent-run-id',required=True);p.add_argument('--symbols',required=True)
    p.add_argument('--run-id',required=True);p.add_argument('--output-dir',required=True)
    p.add_argument('--preview',action='store_true',help='Read-only financial-payload verification; zero provider calls and SQL writes')
    a=p.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    from database.connection import get_sqlalchemy_engine
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    try:
        if a.preview:
            now=utcnow()
            parent,snapshot,config,items,valid,deadline=prepare(engine,a.parent_run_id,a.symbols.split(','),now)
            previews=[]
            for context in snapshot['candidates']:
                if context['symbol'] in a.symbols.split(','):
                    fresh=refresh_failed(engine,context,config,now)
                    previews.append(public_payload_check(fresh,build_request(fresh,config)))
            print(dumps(dict(status='READ_ONLY_PUBLIC_FINANCIAL_PAYLOAD_PREVIEW',provider_calls=0,SQL_writes=0,
                reused_answers=len(valid),timeout_seconds=config.timeout_seconds,inherited_valid_until_utc=deadline,requests=previews)))
            return
        result=resume(engine=engine,parent_id=a.parent_run_id,expected_symbols=a.symbols.split(','),
            run_id=a.run_id,output_dir=a.output_dir)
        print(dumps({k:result[k] for k in ('run_id','status','trade_date','resume')}))
    finally:engine.dispose()


if __name__=='__main__':main()
