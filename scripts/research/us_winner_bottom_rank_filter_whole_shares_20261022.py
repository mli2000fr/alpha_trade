"""V2: reject zero whole-share HALF plans; same native rules, no production edit."""
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path
import argparse
import logging
import shutil

import pandas as pd

from scripts.research import us_winner_bottom_rank_filter_20261022 as study
from common.winner_pyramiding import initial_quantities
from execution_engine.winner_plans import plan_from_target
import backtesting.winner_intraday as native

PARENT=study.ROOT
ROOT=Path('artifacts/research/us_winner_bottom_rank_filter/20261022-v2')
ORIGINAL_STAGE=native.stage_targets
ORIGINAL_ENGINE=study.BacktestEngine
ORIGINAL_CALENDAR=native.get_market_calendar
REFUSALS=[]
CASE_NUMBER=-1
CURRENT_CASE={}


class CachedCalendar:
    """Memoize only deterministic official calendar lookups, not market data."""
    def __init__(self,base):self.base=base
    @lru_cache(maxsize=4096)
    def _sessions(self,start,end):return tuple(self.base.sessions(start,end))
    def sessions(self,start,end):return list(self._sessions(pd.Timestamp(start).date(),pd.Timestamp(end).date()))
    def __getattr__(self,key):return getattr(self.base,key)


def stage_whole_shares(store,targets,config,exec_run_id,*,now=None,calendar=None):
    accepted=[]
    for t in targets:
        if str(t.side or 'long').lower() not in ('long','buy'):
            accepted.append(t);continue
        try:
            plan_from_target(t,config,exec_run_id,now=now,calendar=calendar)
        except ValueError as exc:
            if str(exc)!='Campaign budget cannot fund one whole initial share':raise
            full,initial=initial_quantities(t.target_shares,t.entry_price,t.risk_budget_dollars,config.winner_pyramiding)
            if initial>=1:raise AssertionError('Refusal not backed by native whole-share sizing')
            REFUSALS.append(dict(CURRENT_CASE,symbol=t.symbol,signal_date=t.trade_date,
                full_quantity=full,initial_quantity=initial,entry_price=t.entry_price,
                risk_budget=t.risk_budget_dollars,reason='ZERO_WHOLE_INITIAL_SHARES'))
            continue
        accepted.append(t)
    return ORIGINAL_STAGE(store,accepted,config,exec_run_id,now=now,calendar=calendar)


class ResearchEngine(ORIGINAL_ENGINE):
    def __init__(self,config):
        global CASE_NUMBER,CURRENT_CASE
        CASE_NUMBER+=1
        CURRENT_CASE=dict(year=config.start_date.year,arm=list(study.ARMS)[CASE_NUMBER%3])
        super().__init__(config)


def prepare(root=ROOT):
    if root.exists():raise FileExistsError('New output required')
    p=study.read(PARENT/'protocol.json');study.verify(p['sources'])
    snap=study.read(PARENT/'snapshot.json')
    study.verify({str(PARENT/k):v for k,v in snap['files'].items()})
    files=dict(snap['files'])
    files.update({k:study.digest(PARENT/k) for k in ['snapshot.json','signals-ready.json','frozen-signals.parquet']})
    p['technical_amendment']='Native initial_quantities rejection of zero whole initial shares before staging; no fractional rounding up, budget/stop/threshold change'
    p['preparation_parent']=str(PARENT)
    p['calendar_cache']='Read-only memo of original official sessions; list copy, no price cache or rule change'
    for path in [Path(__file__),Path('tests/test_us_winner_bottom_rank_filter_whole_shares_20261022.py'),PARENT/'protocol.json']:
        p['sources'][str(path)]=study.digest(path)
    p['sources'].update({str(PARENT/k):v for k,v in files.items()})
    root.mkdir(parents=True)
    study.save_new(root/'protocol.json',p)
    for name,sha in files.items():shutil.copyfile(PARENT/name,root/name)
    study.save_new(root/'input-copy-audit.json',dict(files_identical_to_parent=files,old_outcomes_reused=False))
    return p


def run(root=ROOT):
    global CASE_NUMBER,REFUSALS
    CASE_NUMBER=-1;REFUSALS=[]
    old_engine,old_stage,old_calendar=study.BacktestEngine,native.stage_targets,native.get_market_calendar
    calendar=CachedCalendar(ORIGINAL_CALENDAR('US_EQ',allow_us_weekday_fallback=False))
    study.BacktestEngine=ResearchEngine;native.stage_targets=stage_whole_shares
    native.get_market_calendar=lambda *a,**k:calendar
    try:
        r=study.run(root)
        study.save_new(root/'whole-share-refusals.json',REFUSALS)
        return r
    finally:
        study.BacktestEngine=old_engine;native.stage_targets=old_stage;native.get_market_calendar=old_calendar


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=['prepare','run'],required=True)
    parser.add_argument('--output',type=Path,default=ROOT);args=parser.parse_args()
    logging.basicConfig(level=logging.WARNING,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('HTTP forbidden in replay')
    requests.Session.request=forbidden
    {'prepare':prepare,'run':run}[args.phase](args.output)
