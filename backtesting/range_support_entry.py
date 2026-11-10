"""Research-only A2 entry: pre-signal frozen range, next-session support rebound.

No prices after the confirming candle enter a signal. Proposed rules, not a
certified reproduction of video speech. Data are unadjusted regular SIP OHLCV.
"""
from dataclasses import dataclass
from datetime import timedelta
import math

import numpy as np
import pandas as pd

from common.winner_pyramiding import regular_bounds,aware


@dataclass(frozen=True)
class RangeSupportSettings:
    range_bars:int=20
    impulse_bars:int=12
    atr_bars:int=14
    impulse_atr:float=2.
    width_min_atr:float=.8
    width_max_atr:float=5.
    touch_atr:float=.2
    touch_floor:float=.02
    min_touches:int=2
    touch_spacing:int=2
    delay_seconds:int=930

    def __post_init__(self):
        for name in ['range_bars','impulse_bars','atr_bars','min_touches','touch_spacing','delay_seconds']:
            if type(getattr(self,name)) is not int or getattr(self,name)<1:raise ValueError('Positive integer required: '+name)
        for name in ['impulse_atr','width_min_atr','width_max_atr','touch_atr','touch_floor']:
            if not math.isfinite(getattr(self,name)) or getattr(self,name)<=0:raise ValueError('Invalid range parameter')
        if self.width_max_atr<self.width_min_atr:raise ValueError('Range width ordering')


def aggregate_m15(frame,day,*,known_at):
    """Only complete three-component bars closed by known_at; never ffill."""
    start,end=regular_bounds(day);limit=aware(known_at)
    if frame.empty:return pd.DataFrame(columns=['timestamp','end','open','high','low','close','volume'])
    f=frame.copy();f['timestamp']=pd.to_datetime(f.timestamp,utc=True)
    # Future rows, including malformed or duplicated future rows, cannot alter
    # the past signal or its rejection. Validate only known components.
    f=f[(f.timestamp+pd.Timedelta(minutes=5)<=limit)&f.timestamp.ge(start)&f.timestamp.lt(end)]
    if f.timestamp.duplicated().any():raise ValueError('Duplicate known 5m candle')
    values=f[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
    valid=(np.isfinite(values).all(axis=1)&values.gt(0).all(axis=1)
        &values.high.ge(values[['open','close','low']].max(axis=1))
        &values.low.le(values[['open','close','high']].min(axis=1))
        &(f.timestamp-pd.Timestamp(start)).dt.total_seconds().mod(300).eq(0))
    f=f.loc[valid].copy();f[values.columns]=values.loc[valid]
    f['slot']=((f.timestamp-pd.Timestamp(start)).dt.total_seconds()//900).astype(int)
    rows=[]
    for slot,g in f.sort_values('timestamp').groupby('slot'):
        stamp=pd.Timestamp(start)+pd.Timedelta(minutes=15*slot)
        if not g.timestamp.tolist()==list(pd.date_range(stamp,periods=3,freq='5min')):continue
        rows.append(dict(timestamp=stamp,end=stamp+pd.Timedelta(minutes=15),open=float(g.open.iloc[0]),
            high=float(g.high.max()),low=float(g.low.min()),close=float(g.close.iloc[-1]),volume=float(g.volume.sum())))
    return pd.DataFrame(rows,columns=['timestamp','end','open','high','low','close','volume'])


def wilder_atr(frame,period):
    previous=frame.close.shift(1)
    tr=pd.concat([frame.high-frame.low,(frame.high-previous).abs(),(frame.low-previous).abs()],axis=1).max(axis=1)
    result=pd.Series(np.nan,index=frame.index,dtype=float)
    if len(frame)>=period:
        result.iloc[period-1]=tr.iloc[:period].mean()
        for i in range(period,len(frame)):result.iloc[i]=(result.iloc[i-1]*(period-1)+tr.iloc[i])/period
    return result


def spaced_touches(mask,spacing):
    last=-spacing;count=0
    for i,value in enumerate(mask):
        if value and i-last>=spacing:count+=1;last=i
    return count


def freeze_range(history,settings=RangeSupportSettings()):
    """History must be consecutive official M15 slots up to the signal close."""
    c=settings;n=c.atr_bars+c.impulse_bars+c.range_bars
    if len(history)<n:return None,'MISSING_PRE_SIGNAL_M15_CONTEXT'
    f=history.tail(n).reset_index(drop=True).copy();atr=wilder_atr(f,c.atr_bars)
    base=f.tail(c.range_bars);impulse=f.iloc[-c.range_bars-c.impulse_bars:-c.range_bars]
    reference=float(atr.iloc[c.atr_bars-1]);a=float(atr.iloc[-1])
    if min(reference,a)<=0 or not math.isfinite(a):return None,'INVALID_ATR'
    strength=float(impulse.close.iloc[-1]-impulse.open.iloc[0])/reference
    if strength<c.impulse_atr:return None,'NO_BULLISH_PRE_RANGE_IMPULSE'
    lo,hi=float(base.low.min()),float(base.high.max());width=(hi-lo)/a
    if not c.width_min_atr<=width<=c.width_max_atr:return None,'RANGE_WIDTH_OUTSIDE_FIXED_BOUNDS'
    tolerance=max(c.touch_atr*a,c.touch_floor)
    low_hits=spaced_touches(base.low.le(lo+tolerance),c.touch_spacing)
    high_hits=spaced_touches(base.high.ge(hi-tolerance),c.touch_spacing)
    if min(low_hits,high_hits)<c.min_touches:return None,'INSUFFICIENT_SPACED_TOUCHES'
    return dict(low=lo,high=hi,atr=a,tolerance=tolerance,impulse_atr=strength,
        frozen_at=pd.Timestamp(base.end.iloc[-1]).isoformat(),low_touches=low_hits,high_touches=high_hits),'RANGE_READY'


def first_rebound(candles,zone,day,settings=RangeSupportSettings()):
    """First A2 confirmation only; any prior close below support invalidates."""
    start,end=regular_bounds(day);c=settings
    for row in candles.sort_values('timestamp').itertuples():
        if pd.Timestamp(row.end)<=pd.Timestamp(zone['frozen_at']):raise ValueError('Rebound precedes frozen range')
        if row.close<zone['low']-zone['tolerance']:return None,'RANGE_INVALIDATED_BEFORE_REBOUND'
        if (row.low<=zone['low']+zone['tolerance'] and row.close>zone['low']
                and row.close>row.open):
            confirmed=aware(row.end);available=confirmed+timedelta(seconds=c.delay_seconds)
            execution=pd.Timestamp(available).ceil('5min').to_pydatetime()
            if execution>=end:return None,'CONFIRMATION_TOO_LATE_FOR_SAME_SESSION'
            return dict(confirmed_at=confirmed.isoformat(),available_at=available.isoformat(),
                execution_at=execution.isoformat(),setup='A2_RANGE_SUPPORT_LONG',range_low=zone['low'],
                range_high=zone['high'],range_frozen_at=zone['frozen_at']),'A2_CONFIRMED'
    return None,'NO_CONFIRMED_SUPPORT_REBOUND'


class ScheduledEntries:
    """Read-only immutable causal schedule, consumed once on exact clock slots."""
    def __init__(self,frame):
        self.frame=frame.copy();self.consumed=set()
        if self.frame.duplicated(['signal_date','symbol']).any():raise ValueError('Duplicate scheduled candidate')

    def __call__(self,signal_day,day,now,rows):
        if self.frame.empty:return {}
        f=self.frame
        due=f[f.signal_date.eq(str(signal_day))&pd.to_datetime(f.execution_at,utc=True).eq(pd.Timestamp(now))]
        permitted=set(rows.symbol);result={}
        for row in due.to_dict('records'):
            if row['symbol'] not in permitted:continue  # regime/coverage gate veto
            key=(str(signal_day),row['symbol'])
            if key in self.consumed:raise ValueError('Scheduled candidate already consumed')
            if (pd.Timestamp(row['available_at'])>pd.Timestamp(now)
                or pd.Timestamp(row['confirmed_at'])>=pd.Timestamp(now)):
                raise ValueError('Future scheduled entry')
            self.consumed.add(key)
            result[row['symbol']]={k:row[k] for k in ['confirmed_at','available_at','setup']}
        return result
