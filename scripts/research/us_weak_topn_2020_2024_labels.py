"""Offline targets for original TOP20/TOP50 retests; no SQL, broker or provider.

E2 keeps its terminal H3 target. P-MATH/VOL use full-universe terminal H20
deciles. Reconstructed E3 explicitly corrects entry-day ATR leakage and the
skipped entry candle of the historical helper. All membership precedes labels.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import hashlib

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

from modelFactory.oracle.build_labels import nyse_sessions
from modelFactory.oracle.security_continuity import load_security_discontinuities, DEFAULT_REGISTRY_PATH

LINEAGE = ['instrument_id', 'data_source', 'data_adjustment']
ROOT = Path('artifacts/research/us_weak_topn_2020_2024/20261029-v1')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(2**20),b''):h.update(chunk)
    return h.hexdigest()


def write(path,value):
    temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value,indent=2,default=str,allow_nan=False),encoding='utf-8')
    temporary.replace(path)


def checked_keys(frame):
    out=frame.copy()
    out['date']=pd.to_datetime(out.date).dt.normalize()
    if out[['date','symbol']].isna().any().any() or out.duplicated(['date','symbol']).any():
        raise ValueError('Missing/duplicate date/symbol')
    return out


def price_grid(bars,calendar):
    bars=checked_keys(bars)
    if bars.symbol.nunique()!=1:raise ValueError('One symbol required')
    grid=bars.set_index('date').reindex(calendar)
    raw=grid[['open','high','low','close','adj_close','volume','is_filled']].apply(pd.to_numeric,errors='coerce')
    factor=raw.adj_close.where(raw.adj_close.notna(),raw.close)/raw.close
    good=(np.isfinite(raw[['open','high','low','close']]).all(axis=1)
        & raw[['open','high','low','close']].gt(0).all(axis=1)
        & raw.high.ge(raw[['open','low','close']].max(axis=1))
        & raw.low.le(raw[['open','high','close']].min(axis=1))
        & np.isfinite(factor)&factor.gt(0)&np.isfinite(raw.volume)&raw.volume.gt(0)&raw.is_filled.eq(0))
    codes={}
    for col in LINEAGE:
        if col not in grid:raise ValueError('Missing price lineage '+col)
        code=pd.factorize(grid[col])[0]
        valid=code>=0
        if col=='instrument_id':valid &= pd.to_numeric(grid[col],errors='coerce').gt(0).fillna(False).to_numpy(dtype=bool)
        else:valid &= ~grid[col].astype(str).str.upper().isin(['UNKNOWN','','NONE','NAN']).to_numpy()
        good &= valid
        codes[col]=code
    adjusted=raw[['open','high','low','close']].mul(factor,axis=0)
    return adjusted,good.fillna(False).to_numpy(dtype=bool),codes


def window_reasons(adjusted,good,codes,calendar,horizon,symbol,registry):
    width=horizon+1
    n=len(calendar)-horizon
    reasons=np.full(n,'',dtype=object)
    def reject(mask,reason):reasons[(reasons=='') & mask]=reason
    reject(~sliding_window_view(good,width).all(axis=1),'INVALID_OR_MISSING_PATH')
    for col,code in codes.items():
        windows=sliding_window_view(code,width)
        reject(~((windows==windows[:,:1]).all(axis=1)&(windows[:,0]>=0)), 'CHANGED_'+col.upper())
    close=sliding_window_view(adjusted.close.to_numpy(),width)
    with np.errstate(divide='ignore',invalid='ignore'):ratios=close[:,1:]/close[:,:-1]
    reject(((ratios>=20)|(ratios<=.05)).any(axis=1),'UNEXPLAINED_20X_PRICE_BREAK')
    for event in registry.get(symbol,()):
        reject((calendar[:n]<=event.last_predecessor_date)&(calendar[horizon:]>=event.first_successor_date),
            'KNOWN_IDENTITY_BREAK')
    available=pd.Series(calendar).shift(-(horizon+1)).iloc[:n].to_numpy()
    reject(pd.isna(available),'IMMATURE_WINDOW')
    return reasons,available


def symbol_terminal(bars,calendar,horizon,registry):
    symbol=str(bars.symbol.iloc[0])
    adjusted,good,codes=price_grid(bars,calendar)
    reasons,available=window_reasons(adjusted,good,codes,calendar,horizon,symbol,registry)
    n=len(reasons)
    close=adjusted.close.to_numpy()
    with np.errstate(divide='ignore',invalid='ignore'):returns=close[horizon:]/close[:n]-1
    return pd.DataFrame(dict(date=calendar[:n],symbol=symbol,
        **{f'terminal_return_h{horizon}':np.where(reasons=='',returns,np.nan),
           f'available_h{horizon}':available,f'terminal_quality_h{horizon}':reasons}))


def global_deciles(labels,eligibility,min_universe=20,min_coverage=.95):
    """Only J-observable feature keys define the denominator; never TOP keys."""
    result=checked_keys(eligibility[['date','symbol']]).merge(checked_keys(labels),on=['date','symbol'],
        how='left',validate='one_to_one')
    count=result.groupby('date').symbol.transform('size')
    known=result.terminal_return_h20.notna()
    coverage=known.groupby(result.date).transform('sum')/count
    ranks=result.terminal_return_h20.groupby(result.date).rank(method='max',pct=True)
    distinct=result.groupby('date').terminal_return_h20.transform('nunique')
    result['oracle_decile']=np.ceil(ranks*10).clip(1,10).where(
        count.ge(min_universe)&coverage.ge(min_coverage)&distinct.gt(1)&known)
    result['global_label_count_h20']=count
    result['global_label_coverage_h20']=coverage
    return result


def causal_wilder_atr(adjusted,good,codes,window=14):
    """Prefix-invariant Wilder ATR; a hole/identity change starts a fresh block."""
    result=np.full(len(good),np.nan)
    prev=None; block=[]; value=np.nan
    high,low,close=(adjusted[c].to_numpy() for c in ['high','low','close'])
    for i in range(len(good)):
        same=i>0 and good[i-1] and all(code[i]==code[i-1] for code in codes.values())
        if not good[i] or not same:
            block=[];prev=None;value=np.nan
        if not good[i]:continue
        tr=high[i]-low[i] if prev is None else max(high[i]-low[i],abs(high[i]-prev),abs(low[i]-prev))
        block.append(tr)
        if len(block)==window:value=float(np.mean(block))
        elif len(block)>window:value=(value*(window-1)+tr)/window
        result[i]=value
        prev=close[i]
    return result


def symbol_e3(bars,calendar,registry,held=20):
    symbol=str(bars.symbol.iloc[0])
    adjusted,good,codes=price_grid(bars,calendar)
    reasons,available=window_reasons(adjusted,good,codes,calendar,held,symbol,registry)
    n=len(reasons)
    # A reviewed issuer break can exist even when vendor IDs remain unchanged.
    # Its successor begins a new ATR block; predecessor prices never leak in.
    boundaries=pd.DatetimeIndex(sorted(event.first_successor_date for event in registry.get(symbol,())))
    epochs=np.searchsorted(boundaries.asi8,calendar.asi8,side='right')
    atr=causal_wilder_atr(adjusted,good,{**codes,'known_identity_epoch':epochs})[:n]
    windows={c:sliding_window_view(adjusted[c].to_numpy(),held+1)[:,1:] for c in ['open','high','low','close']}
    entry=windows['open'][:,0]
    with np.errstate(divide='ignore',invalid='ignore'):gap=np.abs(entry/adjusted.close.to_numpy()[:n]-1)
    reasons[(reasons=='') & (~np.isfinite(atr)|(atr<=0))]='MISSING_J_ATR'
    reasons[(reasons=='') & (~np.isfinite(gap)|((gap>.03)&~np.isclose(gap,.03,rtol=0,atol=1e-12)))]= 'ENTRY_GAP_OVER_3PCT'
    atr=np.maximum(atr,.001*entry)
    sl=entry-2.5*atr
    tp=entry+np.minimum(3*atr,.07*entry)
    reasons[(reasons=='') & (sl<=0)]='INVALID_STOP'
    # Open is chronologically before intrabar; within a bar SL has priority.
    events=np.where(windows['open']<=sl[:,None],2,
        np.where(windows['open']>=tp[:,None],1,
        np.where(windows['low']<=sl[:,None],2,np.where(windows['high']>=tp[:,None],1,0))))
    touched=(events!=0).any(axis=1)
    first=np.argmax(events!=0,axis=1);row=np.arange(n)
    kind=np.where(touched,events[row,first],0)
    gap_stop=(kind==2)&(windows['open'][row,first]<=sl)
    price=np.where(kind==0,windows['close'][:,-1],np.where(kind==1,tp,
        np.where(gap_stop,windows['open'][row,first],sl)))
    with np.errstate(divide='ignore',invalid='ignore'):net=price/entry-1-.0016
    valid=reasons==''
    return pd.DataFrame(dict(date=calendar[:n],symbol=symbol,e3_long_target=np.where(valid,(net>0).astype(float),np.nan),
        e3_long_net_return=np.where(valid,net,np.nan),available_e3=available,e3_quality=reasons,
        e3_exit_reason=np.where(valid,np.array(['TIME_EXIT','TP','SL'])[kind],'UNQUALIFIED'),
        e3_atr_j=atr,e3_entry_price=entry,e3_stop_price=sl,e3_tp_price=tp))


def run(root=ROOT):
    root=Path(root);source=root/'dataset';output=root/'labels'
    output.mkdir(parents=True,exist_ok=False)
    files={name:source/name for name in ['top50-features.parquet','feature-eligibility.parquet','adjusted-prices.parquet','manifest.json']}
    cfg=Path('config/research/us_weak_topn_2020_2024_20261029.json')
    manifest=json.loads(files['manifest.json'].read_text(encoding='utf-8'))
    if manifest.get('status') not in ('COMPLETED','COMPLETED_EXPLORATORY','COMPLETED_DATASET'):
        raise ValueError('Dataset is not completed')
    for name,sha in manifest['files'].items():
        if digest(source/name)!=sha:raise ValueError('Dataset checksum changed '+name)
    hashes={str(p):digest(p) for p in [*files.values(),cfg,Path(__file__),DEFAULT_REGISTRY_PATH,
        Path('modelFactory/oracle/security_continuity.py'),Path('modelFactory/oracle/build_labels.py')]}
    prices=checked_keys(pd.read_parquet(files['adjusted-prices.parquet']))
    candidates=checked_keys(pd.read_parquet(files['top50-features.parquet']))
    eligibility=checked_keys(pd.read_parquet(files['feature-eligibility.parquet']))
    calendar=pd.DatetimeIndex(nyse_sessions(prices.date.min().date(),prices.date.max().date()))
    pd.DataFrame({'date':calendar}).to_parquet(output/'calendar.parquet',index=False)
    hashes[str(output/'calendar.parquet')]=digest(output/'calendar.parquet')
    write(output/'protocol.json',dict(sources=hashes,config=json.loads(cfg.read_text(encoding='utf-8')),
        no_training=True,no_SQL=True,no_API=True,no_orders=True))
    registry=load_security_discontinuities()
    wanted=set(eligibility.symbol);selected=set(candidates.symbol)
    pieces={3:[],20:[]};e3=[]
    for i,(symbol,bars) in enumerate(prices.groupby('symbol',sort=True)):
        if symbol not in wanted:continue
        write(output/'progress.json',dict(status='RUNNING',phase='labels',symbol=symbol,completed=i,total=len(wanted)))
        for h in (3,20):
            part=symbol_terminal(bars,calendar,h,registry)
            pieces[h].append(part[part.date.between(eligibility.date.min(),eligibility.date.max())])
        if symbol in selected:
            part=symbol_e3(bars,calendar,registry)
            e3.append(part[part.date.between(candidates.date.min(),candidates.date.max())])
    global_labels=global_deciles(pd.concat(pieces[20],ignore_index=True),eligibility)
    coverage=global_labels.groupby('date').agg(global_count=('symbol','size'),
        known=('terminal_return_h20','count'),decile_known=('oracle_decile','count'),
        coverage=('global_label_coverage_h20','first')).reset_index()
    coverage.to_parquet(output/'global-label-coverage.parquet',index=False)
    panel=candidates.merge(global_labels,on=['date','symbol'],how='left',validate='one_to_one')
    panel=panel.merge(pd.concat(pieces[3],ignore_index=True),on=['date','symbol'],how='left',validate='one_to_one')
    panel=panel.merge(pd.concat(e3,ignore_index=True),on=['date','symbol'],how='left',validate='one_to_one')
    # Entry data failure is a documented rejection; never replace by rank N+1.
    if 'selected' in panel:
        invalid=~panel.selected.fillna(False)
        panel.loc[invalid,['terminal_return_h3','terminal_return_h20','oracle_decile','e3_long_target','e3_long_net_return']]=np.nan
    panel.to_parquet(output/'panel.parquet',index=False)
    yearly=[]
    for n in (20,50):
        sub=panel[panel.oracle_rank.le(n)]
        for year,g in sub.groupby(sub.date.dt.year):
            yearly.append(dict(top=n,year=int(year),dates=int(g.date.nunique()),rows=len(g),
                vol60_known=int(g.rolling_volatility_60.notna().sum()),
                h3_known=int(g.terminal_return_h3.notna().sum()),h20_decile_known=int(g.oracle_decile.notna().sum()),
                e3_known=int(g.e3_long_target.notna().sum())))
    for path,sha in hashes.items():
        if digest(path)!=sha:raise ValueError('Source changed during label calculation '+path)
    write(output/'report.json',dict(status='COMPLETED_LABELS',coverage=yearly,sources=hashes,
        files={p.name:digest(p) for p in output.iterdir() if p.is_file() and p.name not in ('report.json','progress.json')},
        no_future_reselection=True,new_E3_causal_correction=True,production_changed=False))
    write(output/'progress.json',dict(status='COMPLETED_LABELS',rows=len(panel)))
    print(json.dumps(dict(status='COMPLETED_LABELS',rows=len(panel),coverage=yearly)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    run(parser.parse_args().root)
