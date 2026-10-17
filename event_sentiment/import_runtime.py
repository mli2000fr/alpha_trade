"""Validated import runtime settings and durable local reports (no SQL)."""
from dataclasses import dataclass
import json
import math
from pathlib import Path
import time
import uuid

from common.config_loader import load_config


@dataclass(frozen=True)
class ImportRuntime:
    pipeline_lookback_days: int = 7
    request_timeout_seconds: int = 45
    max_attempts: int = 3
    max_consecutive_symbol_failures: int = 3
    min_success_ratio: float = .95

    def __post_init__(self):
        if (type(self.min_success_ratio) not in (float,int) or not math.isfinite(self.min_success_ratio)
                or not 0 < self.min_success_ratio <= 1):
            raise ValueError('sentiment_news_ingestion.min_success_ratio: nombre dans ]0,1] requis')
        for key, low, high in [('pipeline_lookback_days',1,365),
                ('request_timeout_seconds',5,180),('max_attempts',1,5),
                ('max_consecutive_symbol_failures',1,20)]:
            value=getattr(self,key)
            if type(value) is not int or not low<=value<=high:
                raise ValueError(f'sentiment_news_ingestion.{key}: entier {low}..{high} requis')


def load_import_runtime():
    values=(load_config() or {}).get('sentiment_news_ingestion') or {}
    return ImportRuntime(**values)


def coverage_decision(requested, succeeded, skipped, threshold, *, blocking_error=False):
    if (any(type(n) is not int or n<0 for n in (requested,succeeded,skipped))
            or succeeded+skipped>requested):
        raise ValueError('Compteurs de couverture import incohérents')
    covered=succeeded+skipped
    ratio=covered/requested if requested else 1.
    accepted=not blocking_error and ratio>=threshold
    complete=covered==requested and not blocking_error
    return dict(covered_symbols=covered,success_ratio=ratio,min_success_ratio=threshold,
        coverage_accepted=accepted,collection_complete=complete,blocking_error=blocking_error,
        coverage_status='COMPLETE' if complete else 'PARTIAL_ACCEPTED' if accepted else 'INCOMPLETE')


def print_stage_report(path):
    payload=json.loads(Path(path).read_text(encoding='utf-8'))
    failed=payload.get('failed_symbols',[])
    count=len(failed)
    if payload.get('status')=='FAILED' and 'last_committed_batch_metrics' in payload:
        print(f"Étape 8 — bilan import interrompu : {count} symbole(s) KO connus / {payload['requested']} ; "
              'compteur exact indisponible pour le lot interrompu ; FAILED',flush=True)
        return
    ratio=payload.get('success_ratio')
    ratio_text=f'{ratio:.2%}' if isinstance(ratio,(int,float)) else 'inconnue'
    print(f"Étape 8 — bilan import news : {count} symbole(s) KO / {payload['requested']} ; "
          f"{payload.get('unattempted_symbols',0)} non exécuté(s) ; couverture {ratio_text} ; "
          f"{payload.get('coverage_status',payload['status'])}",flush=True)
    if failed:
        print('Symboles KO : '+', '.join(str(r['symbol']) for r in failed),flush=True)


def write_report(path, payload):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_text(json.dumps(payload,ensure_ascii=False,default=str,indent=2),encoding='utf-8')
        for attempt in range(10):
            try:
                temporary.replace(path)
                return
            except OSError as exc:
                if attempt==9 or not (isinstance(exc,PermissionError) or getattr(exc,'winerror',None) in (5,32,33)):
                    raise
                time.sleep(min(.05*2**attempt,.5))
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except PermissionError:
            pass  # Do not mask the original Windows replacement error.


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description='Bilan local de l’import en fin d’étape 8, sans SQL/API')
    parser.add_argument('--report',type=Path,required=True)
    print_stage_report(parser.parse_args().report)
