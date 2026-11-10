"""Indexed causal schedules and the exact frozen price priority of A2 audit."""
from collections import OrderedDict
from pathlib import Path

import pandas as pd

from common.winner_pyramiding import regular_bounds
from scripts.research.us_a2_oracle_top20pct_20261109 import BASE,EXT,RECOVERY
from scripts.research.us_concentrated_historical_tapes import digest


class IndexedSchedule:
    def __init__(self,frame):
        if frame.duplicated(['signal_date','symbol']).any():raise ValueError('Duplicate scheduled candidate')
        self.slots={};self.consumed=set()
        for row in frame.to_dict('records'):
            confirmed=pd.Timestamp(row['confirmed_at']);available=pd.Timestamp(row['available_at']);execution=pd.Timestamp(row['execution_at'])
            if available!=confirmed+pd.Timedelta(seconds=930) or execution!=available.ceil('5min'):
                raise ValueError('Invalid A2 delayed execution evidence')
            key=(row['signal_date'],execution.value)
            self.slots.setdefault(key,[]).append({k:row[k] for k in ['symbol','confirmed_at','available_at','setup']})

    def __call__(self,signal_day,day,now,rows):
        key=(str(signal_day),pd.Timestamp(now).value)
        due=self.slots.get(key)
        if not due:return {}
        permitted=set(rows.symbol);result={}
        for row in due:
            if row['symbol'] not in permitted:continue
            candidate=(str(signal_day),row['symbol'])
            if candidate in self.consumed:raise ValueError('Already consumed scheduled candidate')
            self.consumed.add(candidate)
            result[row['symbol']]={k:row[k] for k in ['confirmed_at','available_at','setup']}
        return result


class FixedWait:
    def __init__(self):self.consumed=set()

    def __call__(self,signal_day,day,now,rows):
        opening,_=regular_bounds(day)
        if pd.Timestamp(now)!=pd.Timestamp(opening)+pd.Timedelta(minutes=60):return {}
        key=str(signal_day)
        if key in self.consumed:raise ValueError('Duplicate fixed-wait execution slot')
        self.consumed.add(key)
        return {s:dict(confirmed_at=(pd.Timestamp(opening)+pd.Timedelta(minutes=15)).isoformat(),
            available_at=(pd.Timestamp(opening)+pd.Timedelta(minutes=15,seconds=930)).isoformat(),
            setup='FIXED_1030_NY_WAIT') for s in rows.symbol}


class FrozenPriceSource:
    def __init__(self,manifest):
        self.hashes={Path(k).resolve():v for k,v in manifest['tapes'].items()};self.checked=set();self.cache=OrderedDict()
        self.locations=[BASE/'inputs/base/intraday',BASE/'inputs/extra-intraday',RECOVERY/'intraday',EXT/'inputs/intraday']

    def day(self,day):
        if day in self.cache:self.cache.move_to_end(day);return self.cache[day]
        parts=[]
        for folder in self.locations:
            p=folder/f'{day}.parquet'
            if not p.exists():continue
            if p not in self.checked:
                if digest(p)!=self.hashes.get(p.resolve()):raise ValueError('Changed/unsealed replay tape: '+str(p))
                self.checked.add(p)
            f=pd.read_parquet(p)
            if f.empty:continue
            f=f.copy();f['timestamp']=pd.to_datetime(f.timestamp,utc=True)
            if f.duplicated(['symbol','timestamp']).any():raise ValueError('Duplicate native replay candle')
            parts.append(f)
        f=pd.concat(parts,ignore_index=True).drop_duplicates(['symbol','timestamp'],keep='first') if parts else pd.DataFrame()
        groups={s:g for s,g in f.groupby('symbol')} if not f.empty else {}
        self.cache[day]=groups
        while len(self.cache)>6:self.cache.popitem(last=False)
        return groups

    def __call__(self,day,symbols):
        groups=self.day(day);parts=[groups[s] for s in sorted(symbols) if s in groups]
        return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
