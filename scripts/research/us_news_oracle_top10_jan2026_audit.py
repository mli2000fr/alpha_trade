"""Offline independent path/date/cache-count cross-check; no SQL or API."""
import argparse
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research import us_news_oracle_top10_jan2026 as study


def audit(root):
    p=study.read(root/'protocol.json');report=study.read(root/'report.json')
    study.check_files(root,report['files']);study.check_files(root,p['files'])
    if report['protocol_sha256']!=study.evidence.sha(root/'protocol.json'):raise ValueError('Protocol changed')
    cohort=pd.read_parquet(root/'cohort.parquet');cohort.date=pd.to_datetime(cohort.date)
    paths=pd.read_parquet(root/'outcomes.parquet');paths.date=pd.to_datetime(paths.date)
    prices=pd.read_parquet(root/'prices_snapshot.parquet');prices.date=pd.to_datetime(prices.date)
    if len(cohort)!=200 or len(paths)!=400 or paths.duplicated(['date','symbol','side']).any():raise ValueError('Unexpected cohort')
    if not cohort.groupby('date').oracle_rank.apply(lambda v:set(v)==set(range(1,11))).all():raise ValueError('Not TOP10 daily')
    if set(cohort.date.dt.strftime('%Y-%m-%d'))!=set(p['sessions']):raise ValueError('Dates changed')
    from common.market_calendar import get_market_calendar
    days=pd.DatetimeIndex([s.session_date for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions('2026-01-01','2026-03-31') if s.is_open])
    lookup={(s,d):v for (s,d),v in prices.groupby(['symbol','date'])}
    for r in paths.itertuples():
        target=days[days.get_loc(r.date)+1:days.get_loc(r.date)+21]
        part=pd.concat([lookup[(r.symbol,d)] for d in target]).set_index('date').reindex(target)
        if not r.qualified or len(part)!=20 or part.instrument_id.nunique()!=1:
            raise ValueError('Unexpected missing/unstable path in this complete cohort')
        arr=part[['open','high','low','close','volume']].to_numpy(float)
        if not np.isfinite(arr).all() or (arr<=0).any() or not part.is_filled.eq(0).all() or not part.data_adjustment.eq('split').all():
            raise ValueError('Invalid path accepted')
        if not (part.high>=part[['open','close']].max(axis=1)).all() or not (part.low<=part[['open','close']].min(axis=1)).all():
            raise ValueError('Incoherent OHLC accepted')
        entry=float(part.open.iloc[0]);direction=1 if r.side=='LONG' else -1
        expected='TIMEOUT';hit=None
        for day,bar in part.iterrows():
            opening=direction*(float(bar.open)/entry-1)
            favourable=(float(bar.high)/entry-1) if direction==1 else (1-float(bar.low)/entry)
            adverse=(float(bar.low)/entry-1) if direction==1 else (1-float(bar.high)/entry)
            # Price comparisons avoid introducing a different rounding rule at
            # exact barriers through percentage division.
            stop_open=(bar.open<=entry*.9) if direction==1 else (bar.open>=entry*1.1)
            take_open=(bar.open>=entry*1.2) if direction==1 else (bar.open<=entry*.8)
            stop=(bar.low<=entry*.9) if direction==1 else (bar.high>=entry*1.1)
            take=(bar.high>=entry*1.2) if direction==1 else (bar.low<=entry*.8)
            if stop_open:expected='SL_GAP'
            elif take_open:expected='TP_GAP'
            elif stop and take:expected='AMBIGUOUS'
            elif stop:expected='SL'
            elif take:expected='TP'
            if expected!='TIMEOUT':hit=str(day.date());break
        if r.outcome!=expected or r.hit_date!=hit:raise ValueError('First-barrier order mismatch')
        if r.entry_date!=str(target[0].date()) or r.terminal_date!=str(target[-1].date()):raise ValueError('Off-by-one horizon')
        terminal=direction*(float(part.close.iloc[-1])/entry-1)*100
        if not np.isclose(terminal,r.terminal_signed_return_pct,atol=1e-10):raise ValueError('Terminal return mismatch')
    for side in ('LONG','SHORT'):
        for group,checked in report['groups'][side].items():
            selected=paths[paths.side.eq(side)]
            if group!='ALL_TOP10':selected=selected[selected.decision.eq(group)]
            expected=study.metrics(selected)
            if checked!=expected:raise ValueError('Aggregate mismatch')
    result=dict(status='AUDITED_EXPLORATORY_NON_PIT',created_at_utc=datetime.now(timezone.utc),
        candidate_days=200,side_paths_checked=400,qualified_paths=400,
        full_twenty_session_paths=True,first_entry=str(paths.entry_date.min()),last_terminal=str(paths.terminal_date.max()),
        barrier_order_and_gaps_checked=True,same_bar_ambiguous=int(paths.outcome.eq('AMBIGUOUS').sum()),
        no_new_api_calls=True,sql_access=False,training=False,portfolio_pnl=False,
        historical_news_pit_certified=False,files={n:study.evidence.sha(root/n) for n in ('protocol.json','report.json','outcomes.parquet','prices_snapshot.parquet')})
    study.evidence.save(root/'audit.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    import json
    print(json.dumps(study.evidence.archive.json_value(audit(parser.parse_args().output)),ensure_ascii=False))
