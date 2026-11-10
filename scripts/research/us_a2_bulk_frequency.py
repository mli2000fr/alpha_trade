"""Array implementation of the unchanged A2 rules for large Oracle cohorts.

Research-only acceleration. Tests compare its output with the original scalar
detector; this module changes neither thresholds nor the frozen-range clock.
"""
import numpy as np
import pandas as pd

from backtesting.range_support_entry import RangeSupportSettings


def m15_groups(frame,opening,closing):
    if frame.empty:return {}
    f=frame.copy();f['timestamp']=pd.to_datetime(f.timestamp,utc=True)
    if f.duplicated(['symbol','timestamp']).any():raise ValueError('Duplicate raw candle')
    values=f[['open','high','low','close','volume']].apply(pd.to_numeric,errors='coerce')
    elapsed=(f.timestamp-pd.Timestamp(opening)).dt.total_seconds()
    valid=(f.timestamp.ge(opening)&f.timestamp.lt(closing)&elapsed.mod(300).eq(0)
        &np.isfinite(values).all(axis=1)&values.gt(0).all(axis=1)
        &values.high.ge(values[['open','close','low']].max(axis=1))
        &values.low.le(values[['open','close','high']].min(axis=1)))
    f=f.loc[valid].copy();f[values.columns]=values.loc[valid]
    f['slot']=(elapsed.loc[valid]//300).astype(int);f['bucket']=f.slot//3
    f=f.sort_values('timestamp')
    a=f.groupby(['symbol','bucket'],sort=False).agg(open=('open','first'),high=('high','max'),
        low=('low','min'),close=('close','last'),volume=('volume','sum'),count=('slot','size'),
        first=('slot','min'),last=('slot','max')).reset_index()
    a=a[a['count'].eq(3)&a['first'].eq(a.bucket*3)&a['last'].eq(a.bucket*3+2)]
    a['timestamp_ns']=pd.Timestamp(opening).value+a.bucket*900_000_000_000
    return {s:(g.timestamp_ns.to_numpy(np.int64),g[['open','high','low','close','volume']].to_numpy(float))
        for s,g in a.sort_values('bucket').groupby('symbol',sort=False)}


def freeze_many(matrix,frozen_at,settings=RangeSupportSettings()):
    """Same Wilder seed, impulse, width, and spaced contacts as freeze_range."""
    c=settings;n=c.atr_bars+c.impulse_bars+c.range_bars
    a=np.asarray(matrix,float)
    if a.ndim!=3 or a.shape[1]!=n or a.shape[2]<4:raise ValueError('Invalid A2 context shape')
    if not np.isfinite(a).all():raise ValueError('Nonfinite A2 context')
    if not len(a):return [],[]
    o,h,l,cl=[a[:,:,i] for i in range(4)]
    previous=np.concatenate([cl[:,:1],cl[:,:-1]],axis=1)
    tr=np.maximum.reduce([h-l,np.abs(h-previous),np.abs(l-previous)])
    atr=tr[:,:c.atr_bars].mean(axis=1);reference=atr.copy()
    for i in range(c.atr_bars,n):atr=(atr*(c.atr_bars-1)+tr[:,i])/c.atr_bars
    with np.errstate(divide='ignore',invalid='ignore'):
        impulse=(cl[:,-c.range_bars-1]-o[:,c.atr_bars])/reference
        lo=l[:,-c.range_bars:].min(axis=1);hi=h[:,-c.range_bars:].max(axis=1);width=(hi-lo)/atr
    tolerance=np.maximum(c.touch_atr*atr,c.touch_floor)
    counts=[]
    for mask in [l[:,-c.range_bars:]<=lo[:,None]+tolerance[:,None],
                 h[:,-c.range_bars:]>=hi[:,None]-tolerance[:,None]]:
        last=np.full(len(a),-c.touch_spacing);count=np.zeros(len(a),int)
        for i in range(c.range_bars):
            hit=mask[:,i]&((i-last)>=c.touch_spacing);count+=hit;last=np.where(hit,i,last)
        counts.append(count)
    reasons=np.full(len(a),'RANGE_READY',dtype=object)
    reasons[np.minimum(*counts)<c.min_touches]='INSUFFICIENT_SPACED_TOUCHES'
    reasons[(width<c.width_min_atr)|(width>c.width_max_atr)]='RANGE_WIDTH_OUTSIDE_FIXED_BOUNDS'
    reasons[impulse<c.impulse_atr]='NO_BULLISH_PRE_RANGE_IMPULSE'
    reasons[(np.minimum(reference,atr)<=0)|~np.isfinite(atr)]='INVALID_ATR'
    zones=[None]*len(a)
    for i in np.flatnonzero(reasons=='RANGE_READY'):
        zones[i]=dict(low=float(lo[i]),high=float(hi[i]),atr=float(atr[i]),tolerance=float(tolerance[i]),
            impulse_atr=float(impulse[i]),frozen_at=pd.Timestamp(frozen_at).isoformat(),
            low_touches=int(counts[0][i]),high_touches=int(counts[1][i]))
    return zones,reasons.tolist()


def as_candles(group,opening,closing):
    """Only the contiguous prefix; a later gap cannot invalidate an earlier hit."""
    columns=['timestamp','end','open','high','low','close','volume']
    if group is None:return pd.DataFrame(columns=columns)
    times,values=group;expected=pd.date_range(opening,closing,freq='15min',inclusive='left').asi8
    length=0
    for actual,wanted in zip(times,expected):
        if actual!=wanted:break
        length+=1
    f=pd.DataFrame(values[:length],columns=['open','high','low','close','volume'])
    f['timestamp']=pd.to_datetime(times[:length],utc=True);f['end']=f.timestamp+pd.Timedelta(minutes=15)
    return f[columns]
