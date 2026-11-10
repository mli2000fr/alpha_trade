"""Causal covariance budget shared by the replay and US PAPER Q051. No I/O."""
import math
import numpy as np
import pandas as pd


def portfolio_limit(returns, *, prior_day, positions, pending, symbol, price, equity,
                    proposed, target=.20, lookback=60):
    if (not math.isfinite(equity) or equity<=0 or not math.isfinite(price) or price<=0
            or not math.isfinite(target) or target<=0 or proposed<0):
        raise ValueError('Invalid portfolio risk budget inputs')
    weights={symbol:0.}
    for item in positions:
        if item['side'] not in ('long','buy'):
            raise ValueError('LONG-only covariance research')
        value=float(item['quantity'])*float(item['mark'])
        if not math.isfinite(value) or value<=0:raise ValueError('Invalid held notional')
        weights[item['symbol']]=weights.get(item['symbol'],0.)+value/equity
    for item in pending:
        if item['side'] not in ('long','buy'):raise ValueError('LONG-only pending exposure')
        value=float(item['notional'])
        if not math.isfinite(value) or value<=0:raise ValueError('Invalid pending notional')
        weights[item['symbol']]=weights.get(item['symbol'],0.)+value/equity
    names=sorted(weights)
    if not set(names)<=set(returns):raise ValueError('Portfolio return history missing symbols')
    day=pd.Timestamp(prior_day)
    history=returns.loc[:day,names].tail(lookback).astype(float)
    if (len(history)!=lookback or history.index[-1]!=day
            or not np.isfinite(history.to_numpy()).all()):
        raise ValueError('Need 60 complete prior-session returns for every exposure')
    cov=history.cov().to_numpy()*252.
    if not np.isfinite(cov).all() or np.linalg.eigvalsh(cov).min() < -1e-10:
        raise ValueError('Invalid portfolio covariance')
    w=np.array([weights[n] for n in names]);j=names.index(symbol)
    current=max(float(w@cov@w),0.)
    candidate=proposed*price/equity
    full=w.copy();full[j]+=candidate
    predicted=max(float(full@cov@full),0.)
    if current>=target*target:
        quantity=0;reason='EXISTING_RISK_AT_OR_ABOVE_BUDGET'
    elif predicted<=target*target:
        quantity=proposed;reason='WITHIN_BUDGET'
    else:
        a=max(float(cov[j,j]),0.);b=2.*float(cov[j]@w);c=current-target*target
        if a<=1e-18:
            limit=-c/b if b>0 else candidate
        else:
            limit=(-b+math.sqrt(max(b*b-4*a*c,0.)))/(2*a)
        quantity=min(proposed,max(0,math.floor(max(limit,0.)*equity/price)))
        reason='CANDIDATE_REDUCED_TO_PORTFOLIO_VOL_BUDGET'
    after=w.copy();after[j]+=quantity*price/equity
    forecast=math.sqrt(max(float(after@cov@after),0.))
    if quantity and forecast>target+1e-10:raise ValueError('Forecast volatility exceeds sizing limit')
    return dict(quantity=quantity,reason=reason,prior_day=str(day.date()),
        history_start=str(history.index[0].date()),history_end=str(history.index[-1].date()),
        lookback=lookback,target=target,current_vol=math.sqrt(current),
        proposed_vol=math.sqrt(predicted),approved_vol=forecast)

