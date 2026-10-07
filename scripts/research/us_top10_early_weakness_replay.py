"""Offline frozen comparison: baseline vs full/half next-open J5 weak exits."""
import argparse
from dataclasses import asdict
import json
import logging
from pathlib import Path

import pandas as pd

from common.config_loader import load_config
from service.market import parse_market_regimes
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_concentrated_live_portfolio import ArchivedMacro,run_portfolio
from scripts.research.us_concentrated_contract_audit import frozen_configs


def run(source,output):
    output.mkdir(parents=True,exist_ok=False)
    reference = Path('artifacts/research/us_concentrated_replay/fixed-sl7-oracle_top10-20261007-v1/contract.json')
    contract = json.loads(reference.read_text())
    market = parse_market_regimes((load_config() or {}).get('market_regimes'))
    risk,_ = frozen_configs()
    for key,value in [('market',market),('risk',risk)]:
        if json.loads(json.dumps(asdict(value),default=str)) != contract[key]:
            raise ValueError(f'Changed frozen {key}')
    sector_path = Path('artifacts/research/us_concentrated_replay/live-parity-preflight-current-sectors-20261007-v1/current-sector-mapping.parquet')
    if digest(sector_path) != contract['sector_sha256']:
        raise ValueError('Changed sectors')
    sectors = pd.read_parquet(sector_path).set_index('symbol').sector.to_dict()
    files = ['scores.parquet','bars.parquet','macro.parquet','protocol.json','report.json']
    protocol = dict(experiment='J5_WEAKNESS_2023_2024',start='2023-01-01',end='2024-12-31',
        rule='At fifth close including entry, return from actual fill <0 AND relative SPY return <0',
        execution='Next session open after gap stops and queued regime actions; never same close',
        arms={'BASELINE':None,'EXIT_ALL':1.,'REDUCE_HALF':.5},
        one_decision_per_position=True, initial_stop_pct=.07,tp=False,trailing=False,
        expiry='20 sessions after entry unchanged',capital=4000,
        sources={str(source/f):digest(source/f) for f in files},
        sql_reads=False,sql_writes=False,training=False,threshold_search=False,
        limitations=json.loads((source/'protocol.json').read_text())['limitations'],
        caveat='Rule chosen after descriptive historical audit: exploratory, not independent validation')
    atomic_json(output/'protocol.json',protocol)
    bars = pd.read_parquet(source/'bars.parquet')
    scores = pd.read_parquet(source/'scores.parquet')
    macro = pd.read_parquet(source/'macro.parquet')
    calendar = pd.DatetimeIndex(bars.loc[bars.symbol.eq('SPY') & bars.volume.gt(0),'date']).sort_values()
    frames = {key:bars.pivot(index='date',columns='symbol',values=col).reindex(calendar)
        for key,col in [('opens','open'),('close','close'),('high','high'),('low','low'),('volume','volume')]}
    reports = []
    for arm,fraction in protocol['arms'].items():
        atomic_json(output/'progress.json',dict(status='RUNNING',active_arm=arm,completed=len(reports),total=3))
        result = run_portfolio(frames=frames,scores=scores,sectors=sectors,
            macro=ArchivedMacro(macro),market_config=market,policy='ORACLE_TOP10',
            variant='NO_TP_FIXED_SL_20_AFTER_ENTRY',output=output/arm,
            quality=bars[['date','symbol','is_filled','instrument_id']],initial_stop_pct=.07,
            reject_constrained_entries=True,start_date=protocol['start'],end_date=protocol['end'],
            early_weakness_fraction=fraction)
        if arm == 'BASELINE':
            original = pd.read_parquet(source/'baseline'/'daily.parquet')
            replay = pd.read_parquet(output/arm/'daily.parquet')
            pd.testing.assert_frame_equal(original,replay)
        reports.append(dict(result,arm=arm))
    atomic_json(output/'report.json',dict(status='COMPLETED',baseline_daily_parity=True,runs=reports))
    atomic_json(output/'progress.json',dict(status='COMPLETED',completed=3,total=3))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('artifacts/research/us_concentrated_replay/top10-early-weakness-2023-2024-20261007-v1'))
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        run(args.source,args.output)
    except Exception as exc:
        if args.output.exists():
            atomic_json(args.output/'progress.json',dict(status='FAILED',error=str(exc)))
        raise
