"""Descriptive LONG/SHORT breakdown of an already audited frozen experiment."""
import argparse
from pathlib import Path

import pandas as pd

from scripts.research.us_overnight_intraday_pilot import READ
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def side_summary(frame):
    return frame.groupby(['scope','admission','horizon','policy','year','side']).agg(
        n=('net','size'), dates=('date','nunique'), directional_n=('correct','count'),
        accuracy=('correct','mean'), net_win_rate=('net_win','mean'),
        mean_net=('net','mean'), mean_stress=('net_stress','mean')).reset_index()


def write(root):
    target=root/'readout-v1'
    if target.exists(): raise ValueError('Immutable readout')
    report=READ(root/'report.json');verify_hashes(root,report['files'])
    audit=READ(root/'audit.json')
    if audit['report_sha256']!=digest(root/'report.json'):raise ValueError('Audit/report mismatch')
    trades=pd.read_parquet(root/'outcomes.parquet');sides=side_summary(trades)
    annual=pd.read_csv(root/'annual-summary.csv')
    primary=annual[(annual.admission=='NON_OVERLAP20') & annual.horizon.eq(20)]
    longs=sides[(sides.admission=='NON_OVERLAP20') & sides.horizon.eq(20) & sides.side.eq(1)
        & sides.policy.isin(['INTRADAY20','OVERNIGHT20','AGREEMENT20'])]
    reference=primary[primary.policy=='ALWAYS_LONG'][['scope','year','n','mean_net']].rename(
        columns={'n':'unfiltered_long_n','mean_net':'unfiltered_long_mean'})
    contrasts=longs.merge(reference,on=['scope','year'],validate='many_to_one')
    contrasts['conditional_mean_difference']=contrasts.mean_net-contrasts.unfiltered_long_mean
    target.mkdir()
    sides.to_csv(target/'side-summary.csv',index=False)
    contrasts.to_csv(target/'long-only-descriptive.csv',index=False)
    atomic_json(target/'report.json',dict(status='DESCRIPTIVE_BREAKDOWN_NOT_NEW_VALIDATION',
        comparison='Long-only subset vs all original long entries has unequal membership/exposure; NOT paired same-trades causal benefit or portfolio return.',
        predeclared='Protocol required LONG/SHORT breakdown; no additional fitted rule, inverted rule, threshold search or trade simulation.',
        source_hashes={str(f):digest(f) for f in [Path(__file__),Path('tests/test_us_overnight_intraday_readout.py'),root/'report.json',root/'audit.json',root/'outcomes.parquet']},
        files={f.name:digest(f) for f in target.iterdir() if f.is_file()},no_sql_api_order_training=True))
    print('Readout complete',len(sides),'side breakdown rows',flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    write(a.parse_args().output)
