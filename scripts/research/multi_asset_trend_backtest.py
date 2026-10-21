"""Fixed ETF trend research ledger. Offline, long/cash, no Oracle or live orders."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.multi_asset_trend_data import prepare, READ
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes

STRATEGIES=['TREND_2_OF_3','EQUAL_WEIGHT_BUY_AND_HOLD','EQUAL_WEIGHT_MONTHLY']


def total_return_signal(closes, dividends):
    """Ex-date reinvestment is an index convention ONLY, never portfolio cash."""
    cash=pd.DataFrame(0.,index=closes.index,columns=closes.columns)
    for row in dividends.itertuples():
        if row.symbol in cash.columns and row.ex_date in cash.index:
            cash.loc[row.ex_date,row.symbol]+=row.amount
    gross=(closes+cash)/closes.shift(1)
    gross.iloc[0]=1.
    if gross.isna().any().any() or (gross<=0).any().any(): raise ValueError('Invalid TR signal')
    return gross.cumprod()


def signal_weights(index, cfg):
    lookbacks=cfg['lookbacks_sessions']
    momenta={n:index/index.shift(n)-1 for n in lookbacks}
    votes=sum((f>0).astype(int) for f in momenta.values())
    valid=pd.concat(momenta.values(),axis=1).notna().all(axis=1)
    weights=(votes>=cfg['positive_votes_required']).astype(float)*cfg['weight_per_active_asset']
    weights.loc[~valid,:]=np.nan
    return weights, momenta


def drawdown(equity, initial):
    values=np.r_[initial,np.asarray(equity,dtype=float)]
    return float((values/np.maximum.accumulate(values)-1).min()*100)


def metrics(daily, orders, initial, period_start, period_end):
    values=daily.equity.to_numpy(); returns=values/np.r_[initial,values[:-1]]-1
    years=(pd.Timestamp(period_end)-pd.Timestamp(period_start)).days/365.25
    vol=float(np.std(returns,ddof=1)*np.sqrt(252)) if len(values)>1 else 0.
    return dict(initial_capital_usd=float(initial),final_nav_usd=float(values[-1]),
        profit_usd=float(values[-1]-initial),return_pct=float((values[-1]/initial-1)*100),
        cagr_pct=float(((values[-1]/initial)**(1/years)-1)*100) if years>0 else None,
        max_drawdown_pct=drawdown(values,initial),annualized_volatility_pct=vol*100,
        sharpe_zero_cash=float(np.mean(returns)*252/vol) if vol>0 else None,
        mean_invested_pct=float((daily.market_value/daily.equity).mean()*100),
        mean_cash_pct=float((daily.cash/daily.equity).mean()*100),
        costs_usd=float(daily.cost.sum()),orders=len(orders),
        one_way_traded_notional_usd=float(orders.notional.sum()) if len(orders) else 0.,
        paid_dividends_usd=float(daily.dividends_paid.sum()),
        final_receivables_usd=float(daily.receivable.iloc[-1]))


def simulate(prices, dividends, cfg, strategy, cost_bps):
    if strategy not in STRATEGIES: raise ValueError('Unknown strategy')
    symbols=cfg['symbols']; close=prices.pivot(index='date',columns='symbol',values='close')[symbols].sort_index()
    opens=prices.pivot(index='date',columns='symbol',values='open')[symbols].sort_index()
    if (opens<=0).any().any() or (close<=0).any().any() or opens.isna().any().any() or close.isna().any().any():
        raise ValueError('Missing/invalid execution prices')
    tri=total_return_signal(close,dividends); weights,momenta=signal_weights(tri,cfg)
    positions=np.zeros(len(symbols)); cash=float(cfg['initial_capital_usd']); claims=[]
    fee=cost_bps/10000.; daily=[]; orders=[]; distributions=[]; decisions=[]
    if fee<0: raise ValueError('Negative fees')
    days=close.index[(close.index>=pd.Timestamp(cfg['start']))&(close.index<=pd.Timestamp(cfg['end']))]
    if not len(days): raise ValueError('No simulation sessions')
    exgroups={day:list(group.itertuples()) for day,group in dividends.groupby('ex_date')}
    previous_nav=cash; last_month=None
    for day in days:
        loc=close.index.get_loc(day)
        if loc==0: raise ValueError('Prior close unavailable')
        prior=close.index[loc-1]; accrued=0.; paid=0.; cost=0.
        # Ex-date entitlement refers to holdings overnight, BEFORE today's trades.
        for row in exgroups.get(day,[]):
            quantity=positions[symbols.index(row.symbol)]; amount=quantity*row.amount
            if amount>0:
                claim=dict(symbol=row.symbol,ex_date=day,pay_date=row.pay_date,amount=amount,
                    shares=quantity,per_share=row.amount,paid=False)
                claims.append(claim); distributions.append(claim);accrued+=amount
        for claim in claims:
            if not claim['paid'] and claim['pay_date']<=day:
                cash+=claim['amount'];paid+=claim['amount'];claim['paid']=True;claim['cash_day']=day
        month=(day.year,day.month); rebalance=month!=last_month
        if strategy=='EQUAL_WEIGHT_BUY_AND_HOLD':rebalance=day==days[0]
        if rebalance:
            desired_weights=weights.loc[prior].to_numpy(dtype=float) if strategy=='TREND_2_OF_3' else np.full(len(symbols),.25)
            if not np.isfinite(desired_weights).all():raise ValueError('Insufficient warmup for frozen trend')
            if desired_weights.sum()>1+1e-12 or (desired_weights<0).any():raise ValueError('Invalid leverage/short target')
            # Prior-close shares are fixed BEFORE learning today's open or ex-date.
            desired=desired_weights*previous_nav/close.loc[prior].to_numpy(dtype=float)
            fill=opens.loc[day].to_numpy(dtype=float)
            differences=desired-positions
            for i in np.where(differences < -1e-10)[0]:
                quantity=-differences[i];notional=quantity*fill[i];expense=notional*fee
                positions[i]-=quantity;cash+=notional-expense;cost+=expense
                orders.append(dict(decision_date=prior,fill_date=day,symbol=symbols[i],side='SELL',
                    quantity=quantity,price=fill[i],notional=notional,cost=expense,cash_clip_scale=1.))
            buy=np.maximum(differences,0.);need=float(np.sum(buy*fill)*(1+fee))
            scale=min(1.,max(0.,cash)/need) if need>0 else 1.
            for i in np.where(buy>1e-10)[0]:
                quantity=buy[i]*scale
                if quantity<1e-12:continue
                notional=quantity*fill[i];expense=notional*fee
                positions[i]+=quantity;cash-=notional+expense;cost+=expense
                orders.append(dict(decision_date=prior,fill_date=day,symbol=symbols[i],side='BUY',
                    quantity=quantity,price=fill[i],notional=notional,cost=expense,cash_clip_scale=scale))
            for i,symbol in enumerate(symbols):
                decisions.append(dict(decision_date=prior,fill_date=day,symbol=symbol,
                    prior_nav=previous_nav,prior_close=float(close.loc[prior,symbol]),
                    target_weight=desired_weights[i],target_quantity=desired[i],
                    **{f'momentum_{n}':float(f.loc[prior,symbol]) for n,f in momenta.items()}))
        last_month=month
        if cash< -1e-7 or positions.min()< -1e-9:raise ValueError('Borrowing/shorting prohibited')
        cash=max(0.,cash);receivable=sum(c['amount'] for c in claims if not c['paid'])
        market=float(positions@close.loc[day].to_numpy(dtype=float));nav=cash+receivable+market
        if nav<=0 or market>nav+1e-7:raise ValueError('Invalid NAV/gross leverage')
        row=dict(date=day,equity=nav,cash=cash,receivable=receivable,market_value=market,
            cost=cost,dividends_accrued=accrued,dividends_paid=paid)
        row.update({f'quantity_{s}':q for s,q in zip(symbols,positions)})
        daily.append(row);previous_nav=nav
    d=pd.DataFrame(daily);o=pd.DataFrame(orders,columns=['decision_date','fill_date','symbol','side','quantity','price','notional','cost','cash_clip_scale'])
    annual=[];initial=float(cfg['initial_capital_usd'])
    for year,g in d.groupby(d.date.dt.year):
        subset=o[o.fill_date.dt.year.eq(year)] if len(o) else o
        row=metrics(g,subset,initial,f'{year}-01-01',g.date.iloc[-1])
        row.update(year=int(year),partial_year=year==pd.Timestamp(cfg['end']).year and cfg['end'][5:]!='12-31')
        annual.append(row);initial=g.equity.iloc[-1]
    summary=metrics(d,o,cfg['initial_capital_usd'],cfg['start'],cfg['end'])
    summary.update(strategy=strategy,cost_bps=cost_bps)
    return d,o,pd.DataFrame(distributions),pd.DataFrame(decisions),pd.DataFrame(annual),summary


def run(root):
    cfg=prepare(root)['config'];q=root/'qualified-v1';out=root/'backtest-v1'
    if out.exists():raise ValueError('Immutable backtest output; use explicit new version')
    if READ(q/'report.json')['status']!='QUALIFIED_EXPLORATORY_RECONSTRUCTION':raise ValueError('Unqualified data')
    verify_hashes(q,READ(q/'report.json')['files']);verify_hashes(Path('.'),READ(q/'protocol.json')['sources'])
    prices=pd.read_parquet(q/'prices.parquet');dividends=pd.read_parquet(q/'dividends.parquet')
    out.mkdir()
    atomic_json(out/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),
        sources={str(p):digest(p) for p in [Path(__file__),Path('tests/test_multi_asset_trend_backtest.py'),q/'report.json',root/'protocol.json']},
        cost_primary=cfg['primary_cost_bps_per_traded_notional'],primary_and_two_sensitivities_no_optimization=True,
        fractional_shares_assumed=True,no_production_or_live_parity=True,sql_writes=False,orders=False))
    summaries=[];annual=[]
    for bps in [cfg['primary_cost_bps_per_traded_notional']]+cfg['cost_sensitivities_bps']:
        for strategy in STRATEGIES:
            d,o,c,de,a,s=simulate(prices,dividends,cfg,strategy,bps)
            folder=out/f'{strategy}-{bps}bps';folder.mkdir()
            for name,frame in [('daily',d),('orders',o),('distributions',c),('decisions',de),('annual',a)]:
                frame.to_parquet(folder/f'{name}.parquet',index=False)
            atomic_json(folder/'summary.json',s);summaries.append(s)
            annual.append(a.assign(strategy=strategy,cost_bps=bps));print(strategy,bps,'DONE',flush=True)
    pd.DataFrame(summaries).to_csv(out/'summary.csv',index=False)
    pd.concat(annual,ignore_index=True).to_csv(out/'annual.csv',index=False)
    report=dict(status='CALCULATED_PENDING_LEDGER_AUDIT',scenarios=len(summaries),results=summaries,
        primary_bps=cfg['primary_cost_bps_per_traded_notional'],
        caveats=['Exploratory current historical versions, not vintage PIT',
            'EODHD-only warmup and four in-test dividends, three uncorroborated by Alpaca adjustments',
            'Fixed four ETF basket: ex-post asset selection bias not ruled out; no untouched holdout',
            'No FX, taxes, funding or cash interest; ETF internal expenses embedded in prices',
            'Fractional fills/open prices/friction hypotheses, no verified live portfolio parity',
            'No forced ending liquidation; NAV includes marked holdings and unpaid receivables',
            'This LONG/cash ETF strategy is not diversified futures LONG/SHORT trend replication'],
        files={str(p.relative_to(out)):digest(p) for p in out.rglob('*') if p.is_file()})
    atomic_json(out/'report.json',report)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    run(p.parse_args().root)
