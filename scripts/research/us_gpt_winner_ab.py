"""Paid, budget-capped GPT counterpart to the frozen Qwen 2025 veto experiment."""
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time

import numpy as np
import pandas as pd

from scripts.research.oracle_path_confirmation import exclusive_run
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from service.local_ai.research_veto import Cache, SCHEMA, encoded, key_for, validate_response


SOURCE = Path('artifacts/research/us_local_llm_winner_ab/20261107-v7')
ROOT = Path('artifacts/research/us_gpt_winner_ab/20261107-v1')
MODEL = 'gpt-6-luna'
REVISION = 'openai-gpt-6-luna-identical-qwen-prompt-20261107-v1'
BUDGET = Decimal('2.00')
ENDPOINT = 'https://api.openai.com/v1/responses'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def payload_for(packet):
    messages = packet['request']['messages']
    if [m['role'] for m in messages]!=['system','user']:
        raise ValueError('Deux messages figés system/user requis')
    return dict(model=MODEL,store=False,instructions=messages[0]['content'],input=messages[1]['content'],
        tools=[],tool_choice='none',service_tier='default',reasoning=dict(effort='medium'),
        max_output_tokens=16384,text=dict(format=dict(type='json_schema',name='issuer_news_veto',strict=True,schema=SCHEMA)))


def reservation(request):
    # Conservative byte bound, not an exact tokenizer count. Includes schema,
    # escaping, roles and 4096 extra input tokens; maximum possible output.
    tokens = len(encoded(request).encode('utf8'))+4096
    return (Decimal(tokens)*Decimal('.125')+Decimal(request['max_output_tokens'])*Decimal('.50'))/1000000


def require_budget(requests):
    total=sum((reservation(r) for r in requests),Decimal(0))
    if total>BUDGET:
        raise ValueError(f'Réservation maximale {total} USD supérieure au budget {BUDGET}')
    return total


def normalize(raw,request):
    actual = raw.get('model','')
    if actual!=MODEL and not actual.startswith(MODEL+'-'):
        raise ValueError('Modèle OpenAI différent de la requête autorisée')
    if raw.get('service_tier') not in (None,'default'):
        raise ValueError('Niveau de facturation inattendu')
    if any(v.get('type','').endswith('_call') for v in raw.get('output',[])):
        raise ValueError('Appel outil interdit dans le test sans Web')
    messages = [v for v in raw.get('output',[]) if v.get('type')=='message']
    parts = [c for m in messages for c in m.get('content',[]) if c.get('type')=='output_text']
    complete = raw.get('status')=='completed' and len(messages)==1 and len(parts)==1
    return dict(model=MODEL,actual_model=actual,content=parts[0]['text'] if len(parts)==1 else '',
        finish_reason='stop' if complete else 'length' if raw.get('status')=='incomplete' else 'error',
        request=request,response=raw,usage=raw.get('usage'),response_id=raw.get('id'))


def cost_for(raw,request):
    u = raw.get('usage') or {}
    if any(type(u.get(k)) is not int or u[k]<0 for k in ('input_tokens','output_tokens')):
        raise ValueError('Consommation absente ; ne pas supposer un coût nul')
    if u['output_tokens']>request['max_output_tokens']:
        raise ValueError('Consommation au-delà du plafond de sortie')
    conservative = (Decimal(u['input_tokens'])*Decimal('.125')+Decimal(u['output_tokens'])*Decimal('.50'))/1000000
    if conservative>reservation(request):
        raise ValueError('Réservation conservatrice dépassée ; arrêter les appels restants')
    gross = (Decimal(u['input_tokens'])*Decimal('.10')+Decimal(u['output_tokens'])*Decimal('.50'))/1000000
    return dict(input_tokens=u['input_tokens'],output_tokens=u['output_tokens'],
        reasoning_tokens=(u.get('output_tokens_details') or {}).get('reasoning_tokens'),
        standard_cost_without_cache_discount_usd=float(gross),conservative_cost_usd=float(conservative))


def prepare(root,source=SOURCE):
    from common.ia_prompts import load_prompt
    from scripts.research.us_winner_ui_grid_20261107 import ROOT as tape_root
    old = read(source/'protocol.json')
    for n,sha in old['files'].items():
        if digest(source/n)!=sha:
            raise ValueError('Dossier source modifié : '+n)
    if load_prompt('cloud.oracle_directional.v1.research_veto_comparison',runtime='cloud')!=(source/'prompt.txt').read_text(encoding='utf8'):
        raise ValueError('Le prompt de comparaison GPT doit être identique au prompt Qwen archivé')
    native_sources=read(tape_root/'protocol.json')['sources']
    for n,sha in native_sources.items():
        if digest(Path(n))!=sha:raise ValueError('Moteur/référence de la grille modifié : '+n)
    root.mkdir(parents=True,exist_ok=False)
    for n in ('prompt.txt','news-snapshot.parquet','signals.parquet','coverage.csv'):
        shutil.copyfile(source/n,root/n)
    packets = read(source/'requests.json'); inventory = []
    for p in packets:
        original = deepcopy(p)
        p['model'] = MODEL;p['request'] = payload_for(original);p['key'] = key_for(p['request'],REVISION)
        if p['request']['instructions']!=original['request']['messages'][0]['content'] or p['request']['input']!=original['request']['messages'][1]['content']:
            raise ValueError('Prompt ou dossier différent de Qwen')
        if p['context']['news']:
            inventory.append(dict(request_key=p['key'],symbol=p['symbol'],signal_date=p['signal_date'],
                                  maximum_reservation_usd=str(reservation(p['request']))))
    total = require_budget([p['request'] for p in packets if p['context']['news']])
    atomic_json(root/'requests.json',packets)
    deps = {**native_sources,**old['sources'],str(Path(__file__)):digest(Path(__file__)),
        'service/local_ai/research_veto.py':digest(Path('service/local_ai/research_veto.py')),
        'service/llm_directional/openai_client.py':digest(Path('service/llm_directional/openai_client.py')),
        'common/verified_http.py':digest(Path('common/verified_http.py')),
        str(source/'protocol.json'):digest(source/'protocol.json'),
        'config/ia/prompt/cloud/oracle_directional/v1/research_veto_comparison.txt':
            digest(Path('config/ia/prompt/cloud/oracle_directional/v1/research_veto_comparison.txt'))}
    plan = dict(experiment='GPT_VS_QWEN_IDENTICAL_PROMPT_B_2025',created_at_utc=datetime.now(timezone.utc).isoformat(),
        local_source=str(source),model=MODEL,declared_model_revision=REVISION,budget_usd=str(BUDGET),
        max_paid_calls=len(inventory),maximum_reserved_usd=str(total),request_inventory=inventory,
        candidates=len(packets),with_news=len(inventory),without_news=len(packets)-len(inventory),
        prompt_sha256=digest(root/'prompt.txt'),same_system_and_user_text=True,same_schema_and_veto=True,
        provider_runtime=dict(endpoint=ENDPOINT,reasoning_effort='medium',temperature='OMITTED_API_DEFAULT',
            max_output_tokens=16384,timeout_seconds=600,tools=[],service_tier='default'),
        runtime_equivalence_not_claimed=True,automatic_retries=False,paid_cache_separate_from_local=True,
        api_key_env='OPENAI_API_KEY',authorization='User GO after proposal B with maximum 2 USD; test C excluded',
        test_c=False,sql_shared_writes=False,broker_calls=0,training=False,strict_pit=False,independent_holdout=False,
        price_sources=['https://developers.openai.com/api/docs/models/gpt-6-luna',
                       'https://developers.openai.com/api/docs/guides/reasoning'],
        limitations=old['limitations'],baseline=old['baseline'],sources=deps,
        files={n:digest(root/n) for n in ('prompt.txt','requests.json','news-snapshot.parquet','signals.parquet','coverage.csv')})
    atomic_json(root/'protocol.json',plan)
    atomic_json(root/'progress.json',dict(status='PREPARED',total=204,paid_calls_planned=len(inventory),
                                        budget_usd=str(BUDGET),maximum_reserved_usd=str(total)))
    return plan


def verify(root):
    plan = read(root/'protocol.json')
    for n,sha in plan['files'].items():
        if digest(root/n)!=sha:raise ValueError('Entrée figée modifiée : '+n)
    for n,sha in plan['sources'].items():
        if digest(Path(n))!=sha:raise ValueError('Source figée modifiée : '+n)
    if Decimal(plan['budget_usd'])!=BUDGET or Decimal(plan['maximum_reserved_usd'])>BUDGET:
        raise ValueError('Budget modifié ou dépassé avant appel')
    packets = read(root/'requests.json')
    for p in packets:
        if p['key']!=key_for(p['request'],REVISION):raise ValueError('Identité de requête modifiée')
    if sum((reservation(p['request']) for p in packets if p['context']['news']),Decimal(0))>BUDGET:
        raise ValueError('Réservation totale au-delà du budget')
    return plan,packets


def analyze(root,transport=None):
    plan,packets = verify(root)
    if transport is None and not os.environ.get('OPENAI_API_KEY'):
        raise ValueError('OPENAI_API_KEY absente ; aucun appel tenté')
    client = None;cache = Cache(root/'analyses.sqlite3');api = root/'api';api.mkdir(exist_ok=True)
    costs=[];calls=0;decisions=[]
    try:
        for p in packets:
            prior = cache.latest(p['key'])
            if prior is not None:
                if prior['request']!=p['request']:raise ValueError('Cache avec une autre requête')
                if prior['response'] is not None:
                    costs.append(cost_for(prior['response']['response'],p['request']))
                decisions.append(dict(symbol=p['symbol'],signal_date=p['signal_date'],**prior['validation']))
                continue
            if not p['context']['news']:
                validation=dict(valid=True,veto=False,reason='NO_QUALIFIED_NEWS_KEEP_BASELINE')
                cache.put(p['key'],p['request'],None,validation)
                decisions.append(dict(symbol=p['symbol'],signal_date=p['signal_date'],**validation))
                continue
            prefix = api/p['key'];req_path = prefix.with_suffix('.request.json');raw_path = prefix.with_suffix('.response.json')
            atomic_json(root/'progress.json',dict(status='ANALYZING_GPT',completed=len(decisions),total=len(packets),
                new_paid_calls=calls,current_symbol=p['symbol'],current_signal_date=p['signal_date'],
                budget_usd=str(BUDGET),maximum_reserved_usd=plan['maximum_reserved_usd'],
                conservative_cost_recorded_usd=sum(v['conservative_cost_usd'] for v in costs)))
            if raw_path.exists():
                if not req_path.exists() or read(req_path)!=p['request']:raise ValueError('Reçu sans requête identique')
                raw = read(raw_path)
            else:
                if req_path.exists():raise ValueError('Tentative payante ambiguë ; aucune répétition automatique')
                # Exclusive journal BEFORE a potentially paid request.
                with req_path.open('x',encoding='utf8') as stream:stream.write(encoded(p['request']))
                started = time.monotonic()
                try:
                    if transport is not None:
                        raw = transport(p['request'])
                    else:
                        if client is None:
                            from service.llm_directional.openai_client import ResponsesClient
                            from service.llm_directional.config import FilterConfig
                            client = ResponsesClient(FilterConfig(model=MODEL,provider='openai',
                                analysis_mode='local_data_only',max_output_tokens=16384,timeout_seconds=600))
                        raw = client(p['request'])
                    calls += 1
                    atomic_json(raw_path,raw)
                    atomic_json(prefix.with_suffix('.timing.json'),dict(elapsed_seconds=time.monotonic()-started))
                except Exception as exc:
                    atomic_json(prefix.with_suffix('.error.json'),dict(error_type=type(exc).__name__,
                        error=str(exc),automatic_retry=False,maximum_reserved_usd=str(reservation(p['request']))))
                    raise
            costs.append(cost_for(raw,p['request']))
            normalized = normalize(raw,p['request'])
            try:
                validation = validate_response(normalized,p)
            except Exception as exc:
                validation = dict(valid=False,veto=False,error_type=type(exc).__name__,error=str(exc))
            cache.put(p['key'],p['request'],normalized,validation)
            decisions.append(dict(symbol=p['symbol'],signal_date=p['signal_date'],**validation))
            print(encoded(dict(symbol=p['symbol'],date=p['signal_date'],valid=validation['valid'],veto=validation['veto'],
                cost_usd=costs[-1]['standard_cost_without_cache_discount_usd'])),flush=True)
        atomic_json(root/'decisions.json',decisions)
        result = dict(status='ANALYSIS_COMPLETE_RESEARCH_ONLY' if all(v['valid'] for v in decisions) else 'ANALYSIS_INCOMPLETE',
            valid=sum(v['valid'] for v in decisions),invalid=sum(not v['valid'] for v in decisions),total=len(packets),
            vetoes=sum(v['veto'] for v in decisions),new_paid_calls=calls,paid_responses=len(costs),
            standard_cost_without_cache_discount_usd=sum(v['standard_cost_without_cache_discount_usd'] for v in costs),
            conservative_cost_usd=sum(v['conservative_cost_usd'] for v in costs),budget_usd=str(BUDGET))
        atomic_json(root/'analysis-report.json',result);atomic_json(root/'progress.json',result)
        return result
    finally:
        cache.close()
        if client is not None:client.session.close()


def replay(root):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from scripts.research import us_winner_ui_grid_20261107 as grid
    _,packets = verify(root)
    if read(root/'analysis-report.json')['status']!='ANALYSIS_COMPLETE_RESEARCH_ONLY':
        raise ValueError('Analyses non validées : pas de comparatif économique complet')
    cache=Cache(root/'analyses.sqlite3');excluded=set()
    try:
        for p in packets:
            saved=cache.latest(p['key'])
            if not saved or not saved['validation']['valid']:raise ValueError('Réponse manquante ou invalide')
            val=validate_response(saved['response'],p) if saved['response'] is not None else saved['validation']
            if val['veto']:excluded.add((p['signal_date'],p['symbol']))
    finally:cache.close()
    grid.verify_inputs(grid.ROOT);grid.initialize_worker(grid.ROOT)
    folder=root/'replay';folder.mkdir(exist_ok=False);base=pd.read_parquet(root/'signals.parquet');reports=[]
    for arm in ('A_REFERENCE','B_GPT_VETO'):
        out=folder/arm;out.mkdir()
        selected=base if arm=='A_REFERENCE' else base.loc[[(str(r.trade_date)[:10],r.symbol) not in excluded for r in base.itertuples()]]
        with ReadOnlyReplay(root).install():
            def progress(done,total,day):
                value=dict(status='REPLAYING',arm=arm,completed=done,total=total,last_date=day)
                atomic_json(out/'progress.json',value);atomic_json(root/'progress.json',value)
            cfg=grid.configuration(grid.DATA['plan']['reference'],grid.DATA['plan']['cases'][0])
            result=BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],
                high=grid.DATA['pivots']['high'],low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],
                signals_df=selected,sector_map=grid.DATA['sectors'],intraday_source=grid.DATA['source'],
                winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
            report=metrics(result,4000.)
            if arm=='A_REFERENCE':
                original=read(grid.REFERENCE/'report.json')
                for key in ('final_equity','return_pct','max_drawdown_pct','closed_lot_trades','costs','margin_interest','average_gross_capital'):
                    if not np.isclose(report[key],original[key],rtol=1e-10,atol=1e-6):raise ValueError('Référence différente : '+key)
            report.update(arm=arm,selected_signals=len(selected),excluded_signals=len(base)-len(selected),strict_pit=False)
            atomic_json(out/'report.json',report);selected.to_csv(out/'signals.csv',index=False)
            result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
            result.closed_trades_df.to_csv(out/'trades.csv',index=False);result.trade_events_df.to_csv(out/'events.csv',index=False)
            reports.append(report)
    pd.DataFrame(reports).to_csv(folder/'comparison.csv',index=False)
    atomic_json(folder/'report.json',dict(status='COMPLETED_EXPLORATORY',arms=reports))
    return reports


def compare(root):
    from collections import Counter
    plan,packets=verify(root);local=Path(plan['local_source'])
    local_packets={(p['signal_date'],p['symbol']):p for p in read(local/'requests.json')}
    left=sqlite3.connect((local/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
    right=sqlite3.connect((root/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True,timeout=5)
    left.execute('BEGIN');right.execute('BEGIN');rows=[]
    def latest(db,key):
        row=db.execute('SELECT validation_json FROM attempts WHERE request_key=? ORDER BY id DESC LIMIT 1',(key,)).fetchone()
        return dict(validation=json.loads(row[0])) if row else None
    try:
        for p in packets:
            identity=(p['signal_date'],p['symbol']);q=local_packets[identity]
            if p['request']['instructions']!=q['request']['messages'][0]['content'] or p['request']['input']!=q['request']['messages'][1]['content']:
                raise ValueError('Données/prompts différents entre fournisseurs')
            a=latest(left,q['key']);b=latest(right,p['key'])
            row=dict(signal_date=identity[0],symbol=identity[1],has_news=bool(p['context']['news']))
            for name,v in (('qwen',a),('gpt',b)):
                val=v['validation'] if v else {}
                row.update({name+'_status':'PENDING' if v is None else 'VALID' if val.get('valid') else 'INVALID',
                    name+'_veto':val.get('veto'),name+'_assessment':(val.get('analysis') or {}).get('assessment'),
                    name+'_error':val.get('error')})
            rows.append(row)
    finally:left.close();right.close()
    pd.DataFrame(rows).to_csv(root/'gpt-vs-qwen.csv',index=False)
    paired=[r for r in rows if r['has_news'] and r['qwen_status']==r['gpt_status']=='VALID']
    result=dict(status='DESCRIPTIVE_PARTIAL' if any(r['qwen_status']!='VALID' or r['gpt_status']!='VALID' for r in rows)
        else 'DESCRIPTIVE_COMPLETE',same_prompts_and_evidence=True,total=len(rows),news_candidates=sum(r['has_news'] for r in rows),
        qwen_status_counts=dict(Counter(r['qwen_status'] for r in rows if r['has_news'])),
        gpt_status_counts=dict(Counter(r['gpt_status'] for r in rows if r['has_news'])),paired_valid_with_news=len(paired),
        agreement_count=sum(r['qwen_assessment']==r['gpt_assessment'] for r in paired),
        veto_agreement_count=sum(r['qwen_veto']==r['gpt_veto'] for r in paired),
        excluded_no_news_from_agreement=True,technical_agreement_is_not_directional_accuracy=True,strict_pit=False)
    atomic_json(root/'gpt-vs-qwen-report.json',result)
    return result


def run(root):
    if not (root/'protocol.json').exists():prepare(root)
    with exclusive_run(root):
        try:
            result=analyze(root)
            if result['status']=='ANALYSIS_COMPLETE_RESEARCH_ONLY':
                arms=replay(root);status='COMPLETED_EXPLORATORY'
            else:
                arms=None;status='INCOMPLETE_ANALYSIS_NO_REPLAY'
            comparison=compare(root)
            report=dict(status=status,analysis=result,arms=arms,model_comparison=comparison,
                budget_usd=str(BUDGET),test_c=False,broker_calls=0,finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)
            return report
        except Exception as exc:
            result=dict(status='FAILED_STOPPED_NO_AUTOMATIC_RETRY',error_type=type(exc).__name__,error=str(exc),
                        budget_usd=str(BUDGET),finished_at_utc=datetime.now(timezone.utc).isoformat())
            atomic_json(root/'report.json',result);atomic_json(root/'progress.json',result)
            raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('phase',choices=['prepare','run','compare'])
    p.add_argument('--output-dir',type=Path,default=ROOT)
    a=p.parse_args()
    result=prepare(a.output_dir) if a.phase=='prepare' else compare(a.output_dir) if a.phase=='compare' else run(a.output_dir)
    print(encoded({k:v for k,v in result.items() if k not in ('baseline','sources','files','request_inventory','arms')}))


if __name__=='__main__':main()
