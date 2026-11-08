"""Versioned correction of rejected zero-volume daily prices; keep old tapes intact."""
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_winner_continuous_annual_models_20261108 import read

OLD=Path('artifacts/research/us_winner_continuous_annual_models/20261108-v2')
NEW=Path('artifacts/research/us_winner_continuous_annual_models/20261108-v4')


def run():
    from database.connection import get_sqlalchemy_engine
    from backtesting.winner_data import daily_bars
    from backtesting.isolation import ReadOnlyReplay
    plan=read(OLD/'protocol.json');manifest=read(OLD/'inputs/manifest.json')
    changed={n:dict(old=sha,new=digest(Path(n))) for n,sha in plan['sources'].items() if digest(Path(n))!=sha}
    for name,change in changed.items():
        normalized=Path(name).read_bytes().replace(b'\r\n',b'\n')
        change['line_endings_only']=change['old'] in {
            hashlib.sha256(normalized).hexdigest(),hashlib.sha256(normalized.replace(b'\n',b'\r\n')).hexdigest()}
    semantic={str(Path(n)).replace('\\','/') for n,v in changed.items() if not v['line_endings_only']}
    if semantic!={'backtesting/winner_data.py'}:
        raise ValueError('Ce correctif exige une seule différence source : lecteur daily')
    for name,sha in manifest['files'].items():
        if digest(OLD/'inputs'/name)!=sha:raise ValueError('Ancienne entrée modifiée : '+name)
    NEW.mkdir(parents=True,exist_ok=False)
    atomic_json(NEW/'progress.json',dict(status='READING_ZERO_VOLUME_PRICE_CORRECTION'))
    old=pd.read_parquet(OLD/'inputs/daily.parquet')
    start,end=old.date.min().date(),old.date.max().date();names=manifest['symbols']
    parts=[]
    with ReadOnlyReplay(NEW).install():
        with get_sqlalchemy_engine(db_name='alpha_trade').connect() as conn,conn.begin():
            conn.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY'))
            for offset in range(0,len(names),100):
                part=daily_bars(conn,names[offset:offset+100],start,end)
                parts.append(part.loc[part.volume.eq(0)].copy())
    candidates=pd.concat(parts,ignore_index=True)
    existing=set(zip(old.symbol,pd.to_datetime(old.date)))
    additions=candidates.loc[[(r.symbol,pd.Timestamp(r.date)) not in existing for r in candidates.itertuples()]]
    if additions.empty:raise ValueError('Aucune ligne de prix à corriger')
    if not ((additions.symbol=='TPB')&pd.to_datetime(additions.date).eq('2026-06-18')).any():
        raise ValueError('Correction TPB absente')
    inputs=NEW/'inputs';inputs.mkdir()
    for path in (OLD/'inputs').rglob('*'):
        if not path.is_file() or path.name in ('manifest.json','daily.parquet'):continue
        target=inputs/path.relative_to(OLD/'inputs');target.parent.mkdir(parents=True,exist_ok=True)
        os.link(path,target)  # Immutable original payloads, never overwritten.
    combined=pd.concat([old,additions],ignore_index=True).sort_values(['date','symbol'])
    if combined.duplicated(['date','symbol']).any():raise ValueError('Doublons après correction')
    combined.to_parquet(inputs/'daily.parquet',index=False)
    additions.to_csv(NEW/'added-zero-volume-daily-prices.csv',index=False)
    amended={**plan,'sources':{**plan['sources'],**{n:v['new'] for n,v in changed.items()},
            str(Path(__file__)):digest(Path(__file__))},
        'prepared_at_utc':datetime.now(timezone.utc).isoformat(),
        'price_correction':dict(previous_root=str(OLD),previous_protocol_sha256=digest(OLD/'protocol.json'),
            previous_manifest_sha256=digest(OLD/'inputs/manifest.json'),source_changes=changed,
            added_rows=len(additions),existing_rows_unchanged=True,rule='VALID_CANONICAL_OHLC_WITH_REPORTED_ZERO_VOLUME',
            provider_calls=0,broker_calls=0,SQL_writes=0)}
    atomic_json(NEW/'protocol.json',amended)
    files={str(p.relative_to(inputs)):digest(p) for p in inputs.rglob('*') if p.is_file()}
    atomic_json(inputs/'manifest.json',{**manifest,'files':files,
        'transaction':'ORIGINAL_FROZEN_INPUTS_PLUS_READ_ONLY_QUALIFIED_ZERO_VOLUME_DAILY_ADDITIONS'})
    request=read(OLD/'replay-request.json')
    atomic_json(NEW/'replay-request.json',request)
    atomic_json(NEW/'progress.json',dict(status='INPUTS_FROZEN',sessions=manifest['sessions'],
        correction_rows=len(additions),selection_policy=request['selection_policy']))
    return dict(status='INPUTS_FROZEN',root=str(NEW),added_rows=len(additions),replay_required=True)


if __name__=='__main__':print(json.dumps(run(),ensure_ascii=False))
