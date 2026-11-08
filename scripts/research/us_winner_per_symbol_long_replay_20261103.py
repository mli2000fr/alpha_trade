"""Isolated native Winner replay; only post-Oracle membership is changed.

Use the production risk module and default Winner config. API downloads are
disabled; the existing per-entry retrospective data-coverage rule is retained.
"""
import argparse
from datetime import date
from pathlib import Path
import json
import logging

import pandas as pd

from scripts.research.us_winner_per_symbol_long_20261103 import ROOT,BATCH,ENDS,ARMS,choose,read
from scripts.research.us_concentrated_historical_tapes import digest,atomic_json


def run(root,year,arm):
    from backtesting import winner_campaign_replay as native
    from backtesting.winner_intraday_recovery import RecoveringIntradaySource
    from backtesting.isolation import ReadOnlyReplay
    p=read(root/'protocol.json');training=read(root/'training-report.json')
    if digest('config.yaml')!=p['sources']['config.yaml']:
        raise ValueError('Defaults changed; refuse mixed configuration')
    if digest(root/'predictions.parquet')!=training['predictions_sha256']:
        raise ValueError('Directional predictions changed')
    predictions=pd.read_parquet(root/'predictions.parquet')
    predictions=predictions.loc[predictions.year.eq(year)].copy()
    predictions['trade_date']=pd.to_datetime(predictions.trade_date).dt.date
    if len(predictions)==0:raise ValueError('Missing annual pool')
    picked=choose(predictions,arm)
    selected_keys=set(zip(picked.trade_date,picked.symbol))
    scoremap=predictions.set_index(['trade_date','symbol']).long_probability.to_dict()
    original_validate=native.validate_scores
    workspace=root/'runs'/f'{year}-{arm}'
    workspace.mkdir(parents=True,exist_ok=False)
    class LocalOnlySource(RecoveringIntradaySource):
        def prepare(self,audit):
            # No attempted HTTP or fake repaired bars; all remaining gaps keep
            # the native per-entry holding-window gate and explicit exclusions.
            self.remaining={(r['symbol'],pd.Timestamp(r['date']).date()):r for r in audit['gaps']}
            audit.update(original_missing_sessions=len(audit['gaps']),excluded_symbols=[],
                affected_symbols=sorted({s for s,_ in self.remaining}),repaired_sessions=0,removed_signals=0,
                exclusion_policy='PER_ENTRY_DAY_HOLDING_WINDOW_NO_ORACLE_REFILL',
                recovery=dict(providers=[],attempts=0,sql_modified=False,reason='LOCAL_SQL_ONLY_RESEARCH'))
            return audit
    def filtered(frame,**kwargs):
        if kwargs['top_n']!=20:raise ValueError('Original TOP20 required before filter')
        pool=original_validate(frame,**kwargs)
        current_keys=set(zip(pool.trade_date,pool.symbol))
        expected_keys=set(zip(predictions.trade_date,predictions.symbol))
        if current_keys!=expected_keys:
            raise ValueError('Native Oracle TOP20 differs from frozen cohort; no substitution')
        pool['long_probability']=[scoremap[k] for k in zip(pool.trade_date,pool.symbol)]
        pool['selected_by_direction_model']=[k in selected_keys for k in zip(pool.trade_date,pool.symbol)]
        pool.to_csv(workspace/'selection-audit.csv',index=False)
        return pool.loc[pool.selected_by_direction_model].copy()
    native.validate_scores=filtered
    import backtesting.winner_intraday_recovery as recovery
    recovery.RecoveringIntradaySource=LocalOnlySource
    args=native.build_parser().parse_args([
        '--oracle-batch-id',BATCH,'--start-date',f'{year}-01-01','--end-date',ENDS[year],
        '--top-n','20','--initial-equity','4000','--account-type','margin','--max-leverage','2',
        '--no-factor-market-cap-check','--ignore-missing-intraday','--no-options-filter',
        '--research-assumptions','--output-dir',str(workspace/'artifacts')])
    try:
        with ReadOnlyReplay(workspace).install():
            native.run(args)
            report=read(workspace/'artifacts/report.json')
            report['directional_experiment']=dict(arm=arm,year=year,oracle_top=20,selected_top=(20 if arm=='ORACLE_TOP20' else 10),
                model='INDEPENDENT_ANNUAL_PER_SYMBOL',provider_calls=0,sql_writes=False,
                fewer_than_ten_days=int(picked.groupby('trade_date').size().lt(10).sum()) if arm=='PER_SYMBOL_TOP10' else 0,
                unknown_candidate_probabilities=int(predictions.long_probability.isna().sum()),
                filter_changes_membership_only=True,original_oracle_priority_retained=True)
            atomic_json(workspace/'artifacts/report.json',report)
    finally:
        native.validate_scores=original_validate
        recovery.RecoveringIntradaySource=RecoveringIntradaySource


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--year',type=int,choices=[2024,2025,2026],required=True)
    parser.add_argument('--arm',choices=ARMS,required=True)
    a=parser.parse_args();logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbid_http(*args,**kwargs):
        raise RuntimeError('Broker/provider/LLM HTTP forbidden in this research replay')
    requests.Session.request=forbid_http
    run(a.root,a.year,a.arm)
