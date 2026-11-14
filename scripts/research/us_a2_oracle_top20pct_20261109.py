"""A2 frequency on TOP20% Oracle, without the per-symbol TOP5 bottleneck.

Same fixed range/thresholds/delay/annual models. No training, PnL, provider,
orders or SQL writes. Original TOP5 and enlarged TOP5 controls on identical data.
"""
from collections import OrderedDict
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import json

import numpy as np
import pandas as pd

from backtesting.range_support_entry import RangeSupportSettings,first_rebound
from backtesting.per_symbol_selection import PerSymbolSelection,select_per_symbol
from common.config_loader import replay_market_registry
from common.market_calendar import get_market_calendar
from scripts.research import us_q051_range_support_a2_20261109 as original
from scripts.research.us_a2_bulk_frequency import m15_groups,freeze_many,as_candles
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest

ROOT=Path('artifacts/research/us_a2_oracle_top20pct/20261109-v1')
BASE=original.BASE
EXT=Path('artifacts/research/us_winner_vol20_extensions/20261109-v1')
RECOVERY=Path('artifacts/research/us_q051_range_support_a2_context/20261109-v1')
COHORTS=('OLD_TOP5_SAME_DATA','ORACLE_TOP10PCT_DIRECT','ORACLE_TOP20PCT_DIRECT','ORACLE_TOP20PCT_PER_SYMBOL_TOP5')


class Archive:
    def __init__(self,sessions):
        self.sessions={s.session_date:s for s in sessions};self.cache=OrderedDict();self.hashes={}
        self.locations=[(BASE/'inputs/base/intraday',BASE/'inputs/manifest.json','base/intraday/'),
            (BASE/'inputs/extra-intraday',BASE/'inputs/manifest.json','extra-intraday/'),
            (RECOVERY/'intraday',RECOVERY/'manifest.json','intraday/'),
            (EXT/'inputs/intraday',EXT/'inputs/manifest.json','intraday/')]
        self.manifests={str(p):{k.replace('\\','/'):v for k,v in original.read(p)['files'].items()}
            for _,p,_ in self.locations}

    def day(self,day):
        if day in self.cache:self.cache.move_to_end(day);return self.cache[day]
        parts=[]
        for folder,manifest,prefix in self.locations:
            p=folder/f'{day}.parquet'
            if not p.exists():continue
            sha=digest(p);expected=self.manifests[str(manifest)].get(prefix+p.name)
            if expected is None or sha!=expected:raise ValueError('Changed or unsealed tape: '+str(p))
            self.hashes[str(p)]=sha;f=pd.read_parquet(p)
            if f.empty:continue
            f=f.copy();f['timestamp']=pd.to_datetime(f.timestamp,utc=True)
            if f.duplicated(['symbol','timestamp']).any():raise ValueError('Ambiguous archived raw bars')
            parts.append(f[['symbol','timestamp','open','high','low','close','volume']])
        frame=pd.concat(parts,ignore_index=True).drop_duplicates(['symbol','timestamp'],keep='first') if parts else pd.DataFrame()
        session=self.sessions[day]
        groups=m15_groups(frame,session.open_at_utc,session.close_at_utc)
        opens={(s,int(t.value)):float(p) for s,t,p in frame[['symbol','timestamp','open']].itertuples(index=False,name=None)} if not frame.empty else {}
        value=(groups,opens);self.cache[day]=value
        while len(self.cache)>6:self.cache.popitem(last=False)
        return value


def flags_frame(pool,old):
    per=select_per_symbol(pool,PerSymbolSelection(oracle_top_n=358,long_top_n=5,
        allow_long=True,allow_short=False,min_long_probability=.5,min_long_auc=.5))
    per_keys=set(zip(pd.to_datetime(per.loc[per.selected,'date']),per.loc[per.selected,'symbol']))
    old_keys=set(zip(pd.to_datetime(old.trade_date),old.symbol))
    frame=pool[['trade_date','symbol','rank','entry_year']].copy()
    keys=list(zip(pd.to_datetime(frame.trade_date),frame.symbol))
    frame['OLD_TOP5_SAME_DATA']=[x in old_keys for x in keys]
    frame['ORACLE_TOP20PCT_PER_SYMBOL_TOP5']=[x in per_keys for x in keys]
    frame['ORACLE_TOP10PCT_DIRECT']=frame['rank'].le(179)
    frame['ORACLE_TOP20PCT_DIRECT']=True
    if frame.OLD_TOP5_SAME_DATA.sum()!=len(old):raise ValueError('Original selected cohort not contained in TOP358')
    return frame


def run(root=ROOT):
    root=Path(root);root.mkdir(parents=True,exist_ok=False);inputs=root/'inputs';inputs.mkdir()
    c=RangeSupportSettings();pool_path=EXT/'inputs/signals-oracle-358.parquet'
    pool=pd.read_parquet(pool_path);pool['trade_date']=pd.to_datetime(pool.trade_date)
    if pool.duplicated(['trade_date','symbol']).any() or not pool.groupby('trade_date').size().eq(358).all():
        raise ValueError('Invalid frozen TOP20% cohort')
    counts=pool.groupby('trade_date')['rank'].agg(['min','max'])
    if not counts['min'].eq(1).all() or not counts['max'].eq(358).all():raise ValueError('Oracle ordering differs')
    old_path=BASE/'inputs/signals-Q051_050.parquet';old=pd.read_parquet(old_path)
    settings=asdict(c);previous=original.read(Path('artifacts/research/us_q051_range_support_a2/20261109-v2/request.json'))
    if settings!=previous['settings']:raise ValueError('A2 parameters changed')
    sources=[Path(__file__),Path('scripts/research/us_a2_bulk_frequency.py'),Path('backtesting/range_support_entry.py'),
        pool_path,old_path,BASE/'inputs/manifest.json',EXT/'inputs/manifest.json',RECOVERY/'manifest.json']
    atomic_json(root/'request.json',dict(start='2021-01-01',end='2026-10-01',oracle_horizon=10,universe_size=1790,
        oracle_top_n=358,settings=settings,cohorts=COHORTS,main='TOP20% Oracle -> A2 -> regime -> native risk, no per-symbol filter before A2',
        prior='TOP10% Oracle -> TOP5 per-symbol >.50/calibration AUC>=.50 -> A2',
        invariants='Same annual Oracle weights, frozen range at J, confirmation on J+1, delay930s, no parameter fit',
        data_priority='Original base/extra, then existing context recovery, then extended tapes; no original print replaced',
        source_hashes={str(p):digest(p) for p in sources},frequency_gate=previous['frequency_gate'],
        analysis='FREQUENCY_ONLY; no economic backtest or direction accuracy claimed',
        training=False,provider_calls=0,SQL_writes=0,orders=0,production_changes=False,
        retrospective=True,independent_holdout=False,created_at_utc=datetime.now(timezone.utc).isoformat()))
    atomic_json(root/'progress.json',dict(status='FREEZING_COMPARABLE_COHORTS',completed=0,total=1443))
    frame=flags_frame(pool,old);frame.to_parquet(inputs/'cohorts.parquet',index=False);del pool
    with replay_market_registry(original.shared.restore_registry(BASE)):
        calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s for s in calendar.sessions(pd.Timestamp('2020-12-15').date(),pd.Timestamp('2026-10-01').date()) if s.is_open]
    positions={s.session_date:i for i,s in enumerate(sessions)};archive=Archive(sessions)
    pivots,_,_=original.shared.market_data(BASE);spy=pivots['close']['SPY']
    extra=pd.read_parquet(EXT/'inputs/daily.parquet',columns=['date','symbol','open'])
    daily_open=pd.concat([pivots['open'],extra.pivot(index='date',columns='symbol',values='open')],axis=1)
    output=inputs/'audits';output.mkdir();log=[];events=[];year=None;total=frame.trade_date.nunique()
    needed=c.atr_bars+c.impulse_bars+c.range_bars;processed=0
    for done,(day_frame,rows) in enumerate(frame.groupby('trade_date'),1):
        day=pd.Timestamp(day_frame).date();idx=positions[day];entry=sessions[idx+1]
        if year is not None and year!=entry.session_date.year:
            pd.DataFrame(log).to_parquet(output/f'{year}.parquet',index=False);log=[]
        year=entry.session_date.year
        context_sessions=sessions[max(0,idx-3):idx+1]
        expected=pd.DatetimeIndex([t for s in context_sessions for t in pd.date_range(s.open_at_utc,s.close_at_utc,freq='15min',inclusive='left')])[-needed:].asi8
        contexts=[archive.day(s.session_date)[0] for s in context_sessions]
        current,opens=archive.day(entry.session_date)
        hist=spy.loc[:pd.Timestamp(day)].tail(200)
        regime=bool(len(hist)==200 and np.isfinite(hist).all() and hist.iloc[-1]>.98*hist.mean())
        records=rows.to_dict('records');qualified=[];matrices=[]
        for i,row in enumerate(records):
            row.update(signal_date=str(day),entry_day=str(entry.session_date),year=year,regime_allowed=regime,
                context_qualified=False,range_qualified=False,confirmed=False,execution_evidence=False,
                reason='MISSING_PRE_SIGNAL_M15_CONTEXT')
            row.pop('trade_date',None)
            parts=[d[row['symbol']] for d in contexts if row['symbol'] in d]
            if not parts:continue
            times=np.concatenate([p[0] for p in parts])[-needed:]
            if len(times)!=needed or not np.array_equal(times,expected):continue
            row['context_qualified']=True
            qualified.append(i);matrices.append(np.concatenate([p[1] for p in parts])[-needed:])
        zones,reasons=freeze_many(np.stack(matrices),sessions[idx].close_at_utc,c) if matrices else ([],[])
        for i,zone,reason in zip(qualified,zones,reasons):
            row=records[i];row['reason']=reason
            if zone is None:continue
            row['range_qualified']=True
            candles=as_candles(current.get(row['symbol']),entry.open_at_utc,entry.close_at_utc)
            event,reason=first_rebound(candles,zone,entry.session_date,c);row['reason']=reason
            if event is None:continue
            row['confirmed']=True
            actual=opens.get((row['symbol'],pd.Timestamp(event['execution_at']).value))
            first=opens.get((row['symbol'],pd.Timestamp(entry.open_at_utc).value))
            canonical=daily_open.at[pd.Timestamp(entry.session_date),row['symbol']] if row['symbol'] in daily_open else np.nan
            evidence=bool(actual is not None and actual>0 and first is not None and first>0
                and np.isfinite(canonical) and abs(canonical/first-1)<=.01+1e-12)
            row['execution_evidence']=evidence
            events.append({**row,**event})
        log.extend(records);processed+=len(records)
        atomic_json(root/'progress.json',dict(status='COUNTING_A2_ON_TOP20_PERCENT',completed=done,total=total,
            processed_candidates=processed,last_signal_date=str(day),confirmed_so_far=len(events)))
    if log:pd.DataFrame(log).to_parquet(output/f'{year}.parquet',index=False)
    event_frame=pd.DataFrame(events);event_frame.to_parquet(inputs/'a2-events.parquet',index=False)
    audits=pd.concat([pd.read_parquet(p) for p in sorted(output.glob('*.parquet'))],ignore_index=True)
    summary=[];annual=[]
    for cohort in COHORTS:
        a=audits[audits[cohort]];q=event_frame[event_frame[cohort]&event_frame.regime_allowed]
        last={};independent=0
        for row in q.sort_values(['signal_date','symbol']).itertuples():
            k=positions[pd.Timestamp(row.signal_date).date()]
            if k>=last.get(row.symbol,-999)+11:independent+=1;last[row.symbol]=k
        years=q.groupby('year').size().to_dict();g=previous['frequency_gate']
        passed=(len(q)>=g['min_signals'] and q.symbol.nunique()>=g['min_symbols']
            and independent>=g['min_nonoverlapping'] and sum(n>=5 for n in years.values())>=g['min_years_with_five_signals'])
        summary.append(dict(cohort=cohort,candidates=len(a),context_qualified=int(a.context_qualified.sum()),
            ranges=int(a.range_qualified.sum()),confirmed=int(a.confirmed.sum()),regime_allowed_signals=len(q),
            companies=int(q.symbol.nunique()),nonoverlapping=independent,execution_evidence_signals=int(q.execution_evidence.sum()),
            frequency_pass=bool(passed),by_year=years))
        for y in range(2021,2027):
            z=a[a.year.eq(y)];e=q[q.year.eq(y)]
            annual.append(dict(cohort=cohort,year=y,candidates=len(z),context_qualified=int(z.context_qualified.sum()),
                ranges=int(z.range_qualified.sum()),confirmed=int(z.confirmed.sum()),regime_allowed_signals=len(e),companies=int(e.symbol.nunique()),
                execution_evidence_signals=int(e.execution_evidence.sum())))
    pd.DataFrame([{k:v for k,v in s.items() if k!='by_year'} for s in summary]).to_csv(root/'comparison.csv',index=False)
    pd.DataFrame(annual).to_csv(root/'annual-frequency.csv',index=False)
    old_events=pd.read_parquet(Path('artifacts/research/us_q051_range_support_a2/20261109-v2/inputs/schedule-A2.parquet'))
    actual={(r.signal_date,r.symbol):r.execution_at for r in event_frame.itertuples()}
    for row in old_events.itertuples():
        if actual.get((row.signal_date,row.symbol))!=row.execution_at:raise ValueError('Previously confirmed A2 changed')
    atomic_json(inputs/'manifest.json',dict(files={str(p.relative_to(inputs)):digest(p) for p in inputs.rglob('*') if p.is_file()},
        tapes=archive.hashes,provider_calls=0,SQL_writes=0,orders=0))
    atomic_json(root/'validation.json',dict(status='PASS',previous_24_confirmations_preserved=True,
        scalar_detector_parity='Unit-tested on201 price windows including positive setup',old_cohort_candidates=int(audits.OLD_TOP5_SAME_DATA.sum())))
    report=dict(status='COMPLETED_FREQUENCY_ONLY',period='2021-01-01 through2026-10-01',cohorts=summary,
        pnl_computed=False,training=False,provider_calls=0,SQL_writes=0,orders=0,production_changes=False,
        warning='Events are not accepted portfolio trades or winners; context incomplete and prices retrospective',
        finished_at_utc=datetime.now(timezone.utc).isoformat())
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',report)


if __name__=='__main__':
    try:run()
    except Exception as exc:
        if ROOT.exists():atomic_json(ROOT/'progress.json',dict(status='FAILED',error_type=type(exc).__name__,error=str(exc)))
        raise
