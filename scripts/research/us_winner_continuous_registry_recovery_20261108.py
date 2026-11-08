"""Continue the requested study with immutable prices and a pinned market registry."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
import shutil
from pathlib import Path

import numpy as np

from common.config_loader import load_market_registry,replay_market_registry
from common.market_context import MarketContext,MarketRegistry
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_winner_continuous_annual_models_20261108 import read,replay

OLD=Path('artifacts/research/us_winner_continuous_annual_models/20261108-v4')
ROOT=Path('artifacts/research/us_winner_continuous_annual_models/20261108-v6')


def restore_registry(root):
    payload=read(root/'inputs/market-registry.json')
    contexts=[]
    for record in payload['contexts']:
        context=MarketContext.from_mapping({'schema_version':1,**record})
        if context.fingerprint!=record['fingerprint']:raise ValueError('Contexte marché modifié')
        contexts.append(context)
    return MarketRegistry.from_contexts(contexts)


def prepare(root):
    plan=read(OLD/'protocol.json');manifest=read(OLD/'inputs/manifest.json')
    changed={}
    for name,sha in plan['sources'].items():
        current=digest(Path(name))
        if current==sha:continue
        raw=Path(name).read_bytes().replace(b'\r\n',b'\n')
        eol=sha in {hashlib.sha256(raw).hexdigest(),hashlib.sha256(raw.replace(b'\n',b'\r\n')).hexdigest()}
        if not eol and str(Path(name)).replace('\\','/')!='backtesting/winner_intraday.py':
            raise ValueError('Autre changement de moteur à qualifier : '+name)
        changed[name]=dict(original=sha,current=current,line_endings_only=eol)
    for name,sha in manifest['files'].items():
        if digest(OLD/'inputs'/name)!=sha:raise ValueError('Prix ou signaux modifiés : '+name)
    registry=load_market_registry();registry.assert_compatible('US_EQ','us_primary')
    root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    atomic_json(root/'progress.json',dict(status='PREPARING_PINNED_MARKET_REGISTRY'))
    for name in manifest['files']:
        source=OLD/'inputs'/name;target=inputs/name
        target.parent.mkdir(parents=True,exist_ok=True)
        try:os.link(source,target)
        except PermissionError:shutil.copyfile(source,target)
    atomic_json(inputs/'market-registry.json',dict(schema_version=1,
        contexts=[registry.resolve(code).to_manifest() for code in registry.market_codes],
        mode='VALIDATED_ONCE_PINNED_FOR_REPLAY'))
    restored=restore_registry(root)
    if restored.resolve('US_EQ').fingerprint!=registry.resolve('US_EQ').fingerprint:
        raise ValueError('Contexte US différent après archivage')
    sources={n:v['current'] if n in changed else sha for n,sha in plan['sources'].items()
             for v in [changed.get(n,{})]}
    for name in ['common/config_loader.py','common/market_context.py','common/market_calendar.py',
                 'backtesting/frozen_market_registry.py',str(Path(__file__))]:
        sources[name]=digest(Path(name))
    atomic_json(root/'protocol.json',{**plan,'sources':sources,
        'registry_recovery':dict(previous_root=str(OLD),previous_protocol_sha256=digest(OLD/'protocol.json'),
            price_and_signal_changes=False,source_changes=changed,
            market_registry_sha256=digest(inputs/'market-registry.json'),
            created_at_utc=datetime.now(timezone.utc).isoformat(),SQL_writes=0,provider_calls=0,broker_calls=0)})
    atomic_json(inputs/'manifest.json',{**manifest,'files':{**manifest['files'],
        'market-registry.json':digest(inputs/'market-registry.json')}})
    atomic_json(root/'replay-request.json',read(OLD/'replay-request.json'))
    atomic_json(root/'progress.json',dict(status='INPUTS_FROZEN',sessions=manifest['sessions'],
        market_registry='PINNED',SQL_writes=0,provider_calls=0,broker_calls=0))


def validate_reference(root):
    from backtesting.isolation import ReadOnlyReplay
    from backtesting.simulator import BacktestEngine
    from backtesting.winner_campaign_replay import metrics
    from scripts.research import us_winner_ui_grid_20261107 as grid
    from scripts.research.us_gpt_winner_invalid_excluded import METRICS
    import pandas as pd
    grid.verify_inputs(grid.ROOT);grid.initialize_worker(grid.ROOT)
    signals=pd.read_csv(grid.REFERENCE/'signals.csv',parse_dates=['trade_date'])
    expected=read(grid.REFERENCE/'report.json')
    out=root/'validation-2025';out.mkdir(exist_ok=False)
    with ReadOnlyReplay(root).install(),replay_market_registry(restore_registry(root)):
        def progress(done,total,day):
            atomic_json(root/'progress.json',dict(status='VALIDATING_REFERENCE_2025',completed=done,total=total,last_date=str(day)))
        cfg=grid.configuration(grid.DATA['plan']['reference'],grid.DATA['plan']['cases'][0])
        result=BacktestEngine(cfg).run(open_df=grid.DATA['pivots']['open'],close=grid.DATA['pivots']['close'],
            high=grid.DATA['pivots']['high'],low=grid.DATA['pivots']['low'],volume=grid.DATA['pivots']['volume'],
            signals_df=signals,sector_map=grid.DATA['sectors'],intraday_source=grid.DATA['source'],
            winner_research_assumptions=True,winner_progress=progress,winner_corporate_actions=grid.DATA['actions'])
        report=metrics(result,4000.)
        for name in METRICS:
            if not np.isclose(report[name],expected[name],rtol=1e-10,atol=1e-6):
                raise ValueError('Résultats LONG modifiés : '+name)
        atomic_json(out/'report.json',dict(status='PASS',metrics={k:report[k] for k in METRICS},
            original_report_sha256=digest(grid.REFERENCE/'report.json'),
            market_registry=result.tracker_snapshot['winner_replay']['market_registry']))


def run(root):
    prepare(root);validate_reference(root)
    with replay_market_registry(restore_registry(root)):
        return replay(root,'uniform20pct')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output-dir',type=Path,default=ROOT)
    args=parser.parse_args()
    try:result=run(args.output_dir)
    except Exception as exc:
        if args.output_dir.exists():atomic_json(args.output_dir/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
    print(json.dumps(result,ensure_ascii=False))
