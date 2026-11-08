"""Matched Qwen/GPT receipts replay; no inference, provider or broker access."""
import argparse
from collections import Counter
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_gpt_winner_favorable_only import classify
from scripts.research.us_gpt_winner_invalid_excluded import METRICS
from service.local_ai.research_veto import key_for

ROOT=Path('artifacts/research/us_qwen_gpt_winner_comparison/20261108-v1')
LOCAL=Path('artifacts/research/us_local_llm_winner_ab/20261107-v7')
GPT=Path('artifacts/research/us_gpt_winner_ab/20261107-v1')
GPT_RESULT=Path('artifacts/research/us_gpt_winner_favorable_only/20261108-v1')


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def decisions(packets,records):
    rows=classify(packets,records)
    for row in rows:
        old=records[row['request_key']]['validation']
        row['VETO_INVALID_EXCLUDED']=bool(old['valid'] and not old['veto'])
    return rows


def run(root):
    from backtesting.simulator import BacktestEngine
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.winner_campaign_replay import metrics
    from scripts.research import us_winner_ui_grid_20261107 as grid
    root.mkdir(parents=True,exist_ok=False)
    try:
        plan=read(LOCAL/'protocol.json');packets=read(LOCAL/'requests.json')
        for name,sha in plan['files'].items():
            if digest(LOCAL/name)!=sha:raise ValueError('Archive Qwen modifiée : '+name)
        if any(p['key']!=key_for(p['request'],plan['declared_model_revision']) for p in packets):
            raise ValueError('Identité de requête Qwen incompatible')
        gpt_packets=read(GPT/'requests.json')
        bykey=lambda ps:{(p['signal_date'],p['symbol']):p for p in ps}
        left,right=bykey(packets),bykey(gpt_packets)
        if left.keys()!=right.keys() or any(left[k]['context']!=right[k]['context'] for k in left):
            raise ValueError('Dossiers Qwen et GPT différents')
        if digest(LOCAL/'prompt.txt')!=digest(GPT/'prompt.txt'):
            raise ValueError('Prompts Qwen et GPT différents')
        with sqlite3.connect((LOCAL/'analyses.sqlite3').resolve().as_uri()+'?mode=ro',uri=True) as db:
            records={key:dict(validation=json.loads(v),response=json.loads(raw) if raw else None)
                for key,v,raw in db.execute('SELECT request_key,validation_json,response_json FROM attempts a '
                    'WHERE id=(SELECT MAX(id) FROM attempts b WHERE b.request_key=a.request_key)')}
        rows=decisions(packets,records);ledger=pd.DataFrame(rows)
        ledger.to_csv(root/'decisions.csv',index=False)
        base=pd.read_parquet(LOCAL/'signals.parquet')
        if len(base)!=len(rows) or set(zip(base.trade_date.astype(str).str[:10],base.symbol))!=set(left):
            raise ValueError('Signaux et analyses différents')
        if digest(LOCAL/'signals.parquet')!=digest(GPT/'signals.parquet'):
            raise ValueError('Signaux GPT/Qwen différents')
        grid.verify_inputs(grid.ROOT)
        # Preserve historical inference code hashes. Financial inputs are sealed;
        # new native engine code is recorded, with exact baseline reproduction.
        historical_changes={n:dict(original=sha,current=digest(Path(n)))
            for n,sha in plan['sources'].items() if digest(Path(n))!=sha}
        engine_sources={str(p):digest(p) for folder,pattern in [('backtesting','winner*.py'),
            ('risk_management','*.py'),('execution_engine','winner*.py'),('common','winner*.py')]
            for p in Path(folder).glob(pattern)}
        for name in ['backtesting/simulator.py','backtesting/production_risk_replay.py',
            'backtesting/adaptive_breaker.py','backtesting/regime_trailing.py','execution_engine/config.py']:
            engine_sources[name]=digest(Path(name))
        protocol=dict(year=2025,initial_equity=4000.,policy='VALIDATED_VETO_AND_INVALID_EXCLUDED_NO_REFILL',
            favorable_policy='VALID_FAVORABLE_ONLY',invalid='EXCLUDE',no_news='KEEP_VETO_ARM_EXCLUDE_FAVORABLE_ARM',
            contexts_identical=True,prompts_identical=True,script_sha256=digest(Path(__file__)),
            files={str(r/n):digest(r/n) for r,names in [(LOCAL,['requests.json','analyses.sqlite3','signals.parquet','prompt.txt']),
                (GPT_RESULT,['report.json'])] for n in names},
            original_inference_source_changes=historical_changes,current_engine_sources=engine_sources,
            api_calls=0,broker_calls=0,shared_sql_writes=0,strict_pit=False,independent_holdout=False,
            created_at_utc=datetime.now(timezone.utc).isoformat())
        atomic_json(root/'protocol.json',protocol)
        grid.initialize_worker(grid.ROOT)
        reference=read(grid.REFERENCE/'report.json');reports=[]
        for arm,flag in [('A_REFERENCE',None),('QWEN_VETO_INVALID_EXCLUDED','VETO_INVALID_EXCLUDED'),
                         ('QWEN_FAVORABLE_ONLY','FAVORABLE_ONLY')]:
            selected=base.copy()
            if flag:
                keep={(r['signal_date'],r['symbol']) for r in rows if r[flag]}
                selected=base.loc[[(str(r.trade_date)[:10],r.symbol) in keep for r in base.itertuples()]]
            out=root/arm;out.mkdir();selected.to_csv(out/'signals.csv',index=False)
            with ReadOnlyReplay(root).install():
                def progress(done,total,day):
                    atomic_json(root/'progress.json',dict(status='REPLAYING',arm=arm,completed=done,total=total,last_date=str(day)))
                cfg=grid.configuration(grid.DATA['plan']['reference'],grid.DATA['plan']['cases'][0])
                result=BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],
                    high=grid.DATA['pivots']['high'],low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],
                    signals_df=selected,sector_map=grid.DATA['sectors'],intraday_source=grid.DATA['source'],
                    winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
                report=metrics(result,4000.)
                if arm=='A_REFERENCE':
                    for field in METRICS:
                        if not np.isclose(report[field],reference[field],rtol=1e-10,atol=1e-6):
                            raise ValueError('Témoin non reproduit : '+field)
                report.update(arm=arm,selected_signals=len(selected),excluded_signals=len(base)-len(selected))
                atomic_json(out/'report.json',report)
                result.closed_trades_df.to_csv(out/'trades.csv',index=False)
                result.trade_events_df.to_csv(out/'events.csv',index=False)
                result.equity_curve.rename('equity').to_csv(out/'equity-daily.csv')
                reports.append(report)
        gpt_report=read(GPT_RESULT/'report.json')
        for report in gpt_report['arms']:
            if report['arm']=='A_REFERENCE':
                for field in METRICS:
                    if not np.isclose(report[field],reports[0][field],rtol=1e-10,atol=1e-6):
                        raise ValueError('Référence GPT différente : '+field)
            else:reports.append(dict(report,reused_verified_GPT=True))
        pd.DataFrame([{k:r.get(k) for k in ('arm',)+METRICS+('selected_signals','excluded_signals')} for r in reports]).to_csv(root/'comparison.csv',index=False)
        counts=dict(Counter((r['assessment'] or ('NO_NEWS' if not r['has_news'] else 'INVALID')) for r in rows))
        report=dict(status='COMPLETED_EXPLORATORY',arms=reports,selection_counts=counts,
            baseline_reproduction='PASS',contexts_identical=True,prompts_identical=True,strict_pit=False,
            api_calls=0,broker_calls=0,shared_sql_writes=0)
        atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status=report['status']))
        return report
    except Exception as exc:
        atomic_json(root/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT)
    print(json.dumps(run(parser.parse_args().output_dir),ensure_ascii=False))
