"""Enrich old bundles with diagnostics; no fit, SQL write or portfolio replay."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time

import joblib
import pandas as pd

from . import directional as d
from .directional_metrics import model_metrics
from .train import atomic_json,digest


def evaluate(root,*,engine=None,output=None):
    from modelFactory.oracle.build_labels import nyse_sessions
    from modelFactory.oracle.security_continuity import SecurityDiscontinuity
    from modelFactory.data_loader import load_benchmark_bars
    root=Path(root).resolve();manifest,checksum=d.load_manifest(root)
    protocol=json.loads((root/'protocol.json').read_text(encoding='utf-8'))
    out=Path(output or root/'directional/diagnostics').resolve()
    out.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    state=dict(status='RUNNING',completed=0,total=len(protocol['universe']),models=0,
        training_launched=False,SQL_writes=False,portfolio_replay=False,provider_calls=0)
    def progress():
        state['elapsed_seconds']=round(time.monotonic()-started,1)
        atomic_json(out/'progress.json',state)
        print(json.dumps(state,ensure_ascii=False),flush=True)
    try:
        progress()
        data=protocol['training_config']['data']
        start,end=pd.Timestamp(data['training_start_date']),pd.Timestamp(data['training_end_date'])
        calendar=nyse_sessions(start.date(),end.date())
        reconstructed=not bool(manifest.get('benchmark_file'))
        if reconstructed:
            if engine is None:raise ValueError('Old bundle requires read-only benchmark access')
            bench=load_benchmark_bars(engine,benchmark_symbol=data['benchmark_symbol'],
                start_date=str(start.date()),end_date=str(end.date()))
        else:bench=pd.read_parquet(root/manifest['benchmark_file'])
        bench.to_parquet(out/'benchmark.parquet',index=False)
        registry={symbol:tuple(SecurityDiscontinuity(symbol=str(row['symbol']),
            last_predecessor_date=pd.Timestamp(row['last_predecessor_date']),
            first_successor_date=pd.Timestamp(row['first_successor_date']),reason=row['reason']) for row in rows)
            for symbol,rows in protocol.get('security_discontinuities',{}).items()}
        by_symbol={}
        for row in manifest['models']:by_symbol.setdefault(row['symbol'],[]).append(row)
        records=[];files=[];seen=set()
        for relative,expected in sorted(manifest['source_hashes'].items()):
            path=(root/relative).resolve()
            if not path.is_relative_to(root) or digest(path)!=expected:
                raise ValueError('Frozen bars missing or modified: '+relative)
            bars=pd.read_parquet(path);chunk_predictions=[]
            for symbol,g in bars.groupby('symbol'):
                if symbol in seen:raise ValueError('Duplicate symbol across training chunks')
                seen.add(symbol)
                if symbol in by_symbol:
                    features=d.panels(g,bench,calendar)
                    panel=features.merge(d.labels(g,calendar,d.Settings(**manifest['contract']),registry.get(symbol,())),
                        on='date',validate='one_to_one')
                    for record in by_symbol[symbol]:
                        weights=joblib.load(root/record['file'])
                        metrics,predictions=model_metrics(panel,weights,record,calendar,end,
                            horizon_sessions=manifest['contract']['horizon_sessions'])
                        records.append(dict(symbol=symbol,year=record['year'],side=record['side'],
                            model_sha256=record['sha256'],metrics=metrics))
                        if len(predictions):chunk_predictions.append(predictions)
                state.update(completed=len(seen),models=len(records),symbol=symbol)
            if chunk_predictions:
                frame=pd.concat(chunk_predictions,ignore_index=True)
                dest=out/('oos-'+path.parent.name+'.parquet');frame.to_parquet(dest,index=False)
                files.append(dict(path=dest.name,sha256=digest(dest),rows=len(frame),
                    min_date=str(frame.date.min().date()),max_date=str(frame.date.max().date()),
                    symbols=sorted(frame.symbol.unique().tolist())))
            progress()
        if len(records)!=len(manifest['models']) or seen!=set(protocol['universe']):
            raise ValueError('Incomplete diagnostic coverage')
        report=dict(status='COMPLETED',schema_version=1,created_at=datetime.now(timezone.utc).isoformat(),
            oracle_protocol_sha256=digest(root/'protocol.json'),manifest_sha256=checksum,
            models=records,source_hashes=manifest['source_hashes'],oos_files=files,
            benchmark_file='benchmark.parquet',benchmark_sha256=digest(out/'benchmark.parquet'),
            benchmark_reconstructed_from_SQL=reconstructed,
            calibration_is_independent_test=False,score_threshold=.5,
            nonoverlap_phase=f"global calendar index modulo{manifest['contract']['horizon_sessions']+1} ==0",
            training_launched=False,SQL_writes=False,portfolio_replay=False,provider_calls=0)
        atomic_json(out/'report.json',report)
        state['status']='COMPLETED';progress()
        return report
    except Exception as exc:
        state.update(status='FAILED',error_type=type(exc).__name__,error=str(exc));progress()
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--batch-id',required=True)
    parser.add_argument('--artifacts-dir',type=Path,default=Path('artifacts/models'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    from .predict import load_contract
    root,_,_,_=load_contract(args.artifacts_dir,args.batch_id)
    from database.connection import get_sqlalchemy_engine
    from sqlalchemy import event
    engine=get_sqlalchemy_engine(db_name='alpha_trade')
    def readonly(conn,cursor,statement,parameters,context,executemany):
        if statement.lstrip().split(None,1)[0].upper() not in ('SELECT','SHOW','SET','DESCRIBE'):
            raise ValueError('SQL writes forbidden during directional diagnostics')
    event.listen(engine,'before_cursor_execute',readonly)
    try:evaluate(root,engine=engine,output=args.output)
    finally:
        event.remove(engine,'before_cursor_execute',readonly)
        engine.dispose()
