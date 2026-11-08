"""Bounded timing/format probe, using already frozen local research dossiers."""
from dataclasses import asdict, replace
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import time

import numpy as np

from scripts.research.us_concentrated_historical_tapes import atomic_json, digest
from service.local_ai.lm_studio import Client, load_connection
from service.local_ai.research_veto import Cache, SCHEMA, encoded, key_for, validate_response


def run(source, output, limit=3):
    output.mkdir(parents=True,exist_ok=False)
    plan=json.loads((source/'protocol.json').read_text(encoding='utf8'))
    for name,sha in plan['files'].items():
        if digest(source/name)!=sha:
            raise ValueError('Archive source modifiée : '+name)
    packets=json.loads((source/'requests.json').read_text(encoding='utf8'))
    eligible=[p for p in packets if p['context']['news']]
    ordered=sorted(eligible,key=lambda p:len(encoded(p['request'])))
    chosen=[]
    for p in (eligible[0],ordered[len(ordered)//2],ordered[-1]):
        if (p['symbol'],p['signal_date']) not in [(v['symbol'],v['signal_date']) for v in chosen]:
            chosen.append(p)
    config=replace(load_connection(),max_output_tokens=8192,timeout_seconds=300)
    frozen=dict(started_utc=datetime.now(timezone.utc).isoformat(),source_protocol_sha256=digest(source/'protocol.json'),
        connection=asdict(config),selection='First chronologically, median and maximum request size with news; no outcomes',
        cohort=plan['candidates'],with_news=len(eligible),maximum_calls=min(limit,len(chosen)),
        cloud_calls=0,broker_calls=0,training=False,replay=False)
    atomic_json(output/'protocol.json',frozen)
    cache=Cache(output/'analyses.sqlite3');reports=[];client=Client(config)
    try:
        if config.model not in client.models():
            raise ValueError('Modèle local demandé indisponible')
        for p in chosen[:limit]:
            request=dict(model=config.model,messages=p['request']['messages'],temperature=config.temperature,
                max_tokens=config.max_output_tokens,stream=False,response_format=dict(type='json_schema',
                    json_schema=dict(name='issuer_news_veto',strict=True,schema=SCHEMA)))
            key=key_for(request,plan['declared_model_revision'])
            atomic_json(output/'progress.json',dict(status='PROBING',completed=len(reports),total=min(limit,len(chosen)),
                symbol=p['symbol'],request_characters=len(encoded(request)),started_utc=datetime.now(timezone.utc).isoformat()))
            print(f"PROBE {len(reports)+1} {p['symbol']} {p['signal_date']} chars={len(encoded(request))}",flush=True)
            started=time.monotonic();response=None
            try:
                response=client.chat(request['messages'],response_format=request['response_format'])
                validation=validate_response(response,p)
            except Exception as exc:
                response=getattr(exc,'result',response)
                validation=dict(valid=False,veto=False,error_type=type(exc).__name__,error=str(exc))
            elapsed=time.monotonic()-started
            cache.put(key,request,response,validation)
            report=dict(symbol=p['symbol'],signal_date=p['signal_date'],elapsed_seconds=elapsed,
                request_characters=len(encoded(request)),valid=validation['valid'],
                error=validation.get('error'),finish_reason=response.get('finish_reason') if response else None,
                usage=response.get('usage') if response else None,
                assessment=validation.get('analysis',{}).get('assessment'),veto=validation['veto'])
            reports.append(report);atomic_json(output/f"response-{len(reports)}.json",dict(request=request,response=response,validation=validation))
            print(encoded(report),flush=True)
            if not validation['valid']:
                break
        seconds=[r['elapsed_seconds'] for r in reports]
        valid=bool(reports) and all(r['valid'] for r in reports)
        summary=dict(status='PILOT_VALID' if valid else 'PILOT_INCOMPLETE',calls=len(reports),reports=reports,
            mean_seconds=float(np.mean(seconds)),cloud_calls=0,broker_calls=0,
            full_166_serial_estimate_minutes=float(np.mean(seconds)*len(eligible)/60) if valid else None,
            serial_range_minutes=[min(seconds)*len(eligible)/60,max(seconds)*len(eligible)/60] if valid else None,
            estimate_not_guaranteed=True,economic_backtest_started=False)
        atomic_json(output/'report.json',summary);atomic_json(output/'progress.json',summary)
        return summary
    finally:
        client.close();cache.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    p.add_argument('--limit',type=int,choices=[1,2,3],default=3)
    a=p.parse_args();print(encoded(run(a.source,a.output_dir,a.limit)))


if __name__=='__main__':main()
