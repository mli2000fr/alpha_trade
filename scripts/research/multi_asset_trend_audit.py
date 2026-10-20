"""Independent arithmetic replay of saved ETF research ledgers; offline only."""
import argparse
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.multi_asset_trend_data import READ
from scripts.research.us_concentrated_historical_tapes import atomic_json, digest, verify_hashes


def near(actual, expected, message):
    if not np.isclose(actual,expected,rtol=1e-9,atol=1e-7):
        raise ValueError(f'{message}: {actual} != {expected}')


def audit_scenario(folder, prices, dividends, cfg):
    daily=pd.read_parquet(folder/'daily.parquet');orders=pd.read_parquet(folder/'orders.parquet')
    decisions=pd.read_parquet(folder/'decisions.parquet');claims_saved=pd.read_parquet(folder/'distributions.parquet')
    annual=pd.read_parquet(folder/'annual.parquet');summary=READ(folder/'summary.json')
    symbols=cfg['symbols'];fee=summary['cost_bps']/10000.
    closes=prices.pivot(index='date',columns='symbol',values='close').sort_index()
    opens=prices.pivot(index='date',columns='symbol',values='open').sort_index()
    # Independent TR recurrence, rather than importing the simulation's signal.
    tr=pd.DataFrame(1.,index=closes.index,columns=symbols)
    for s in symbols:
        events=dividends[dividends.symbol.eq(s)].set_index('ex_date').amount
        for i in range(1,len(closes)):
            day=closes.index[i];prior=closes.index[i-1]
            tr.loc[day,s]=tr.loc[prior,s]*(closes.loc[day,s]+events.get(day,0))/closes.loc[prior,s]
    expected_dates=closes.index[(closes.index>=cfg['start'])&(closes.index<=cfg['end'])]
    if daily.date.tolist()!=expected_dates.tolist():raise ValueError('Incomplete saved daily ledger')
    if not set(orders.fill_date).issubset(set(daily.date)):raise ValueError('Out-of-window fill')
    first_months=daily.groupby(daily.date.dt.to_period('M')).date.first().tolist()
    if summary['strategy']=='EQUAL_WEIGHT_BUY_AND_HOLD':first_months=[daily.date.iloc[0]]
    if sorted(decisions.fill_date.unique())!=first_months:raise ValueError('Rebalance schedule')
    positions={s:0. for s in symbols};cash=float(cfg['initial_capital_usd']);claims=[]
    prior_nav=cash
    for row in daily.itertuples():
        day=row.date;prior=closes.index[closes.index.get_loc(day)-1]
        d=decisions[decisions.fill_date.eq(day)]
        for dec in d.itertuples():
            if dec.decision_date!=prior:raise ValueError('Non-prior-close decision')
            near(dec.prior_nav,prior_nav,'Decision NAV');near(dec.prior_close,closes.loc[prior,dec.symbol],'Decision close')
            near(dec.target_quantity,dec.target_weight*prior_nav/dec.prior_close,'Prior-close quantity')
            if summary['strategy']=='TREND_2_OF_3':
                i=tr.index.get_loc(prior)
                if i<max(cfg['lookbacks_sessions']):raise ValueError('Warmup not available')
                votes=0
                for n in cfg['lookbacks_sessions']:
                    m=tr.loc[prior,dec.symbol]/tr.iloc[i-n][dec.symbol]-1
                    near(getattr(dec,f'momentum_{n}'),m,'Momentum')
                    votes+=m>0
                expected=.25 if votes>=2 else 0.
            else:expected=.25
            near(dec.target_weight,expected,'Target weight')
        accrued=0.;paid=0.
        for event in dividends[dividends.ex_date.eq(day)].itertuples():
            amount=positions[event.symbol]*event.amount
            if amount>0:
                claims.append(dict(symbol=event.symbol,ex_date=day,pay_date=event.pay_date,amount=amount,
                    shares=positions[event.symbol],paid=False,cash_day=None));accrued+=amount
        for claim in claims:
            if not claim['paid'] and claim['pay_date']<=day:
                cash+=claim['amount'];paid+=claim['amount'];claim['paid']=True;claim['cash_day']=day
        current=orders[orders.fill_date.eq(day)];cost=0.
        if len(current) and d.empty:raise ValueError('Order outside rebalance')
        if current.side.tolist()!=sorted(current.side.tolist(),reverse=True):raise ValueError('Sells not first')
        for order in current.itertuples():
            if order.decision_date!=prior:raise ValueError('Order decision date')
            near(order.price,opens.loc[day,order.symbol],'Execution open')
            near(order.notional,order.price*order.quantity,'Notional')
            near(order.cost,order.notional*fee,'Cost')
            if order.quantity<=0 or order.cost<0:raise ValueError('Invalid trade')
            if order.side=='SELL':
                positions[order.symbol]-=order.quantity;cash+=order.notional-order.cost
            elif order.side=='BUY':
                positions[order.symbol]+=order.quantity;cash-=order.notional+order.cost
            else:raise ValueError('Invalid order side')
            cost+=order.cost
            if cash< -1e-7 or min(positions.values())< -1e-9:raise ValueError('Intraday borrow/short')
        for dec in d.itertuples():
            before_buy=current[current.symbol.eq(dec.symbol)]
            if len(before_buy)>1:raise ValueError('Duplicate same-symbol rebalance')
            # Target can remain unfilled ONLY via the recorded common cash clip.
            if not before_buy.empty and before_buy.iloc[0].side=='BUY':
                order=before_buy.iloc[0];old=positions[dec.symbol]-order.quantity
                near(order.quantity,(dec.target_quantity-old)*order.cash_clip_scale,'Clipped quantity')
                if not 0<=order.cash_clip_scale<=1:raise ValueError('Invalid cash clip')
            elif not before_buy.empty:
                near(positions[dec.symbol],dec.target_quantity,'Sell target')
        receivable=sum(c['amount'] for c in claims if not c['paid'])
        market=sum(positions[s]*closes.loc[day,s] for s in symbols)
        near(row.cash,cash,'Cash ledger');near(row.receivable,receivable,'Receivable ledger')
        near(row.market_value,market,'Marked positions');near(row.equity,cash+market+receivable,'NAV')
        near(row.cost,cost,'Daily costs');near(row.dividends_accrued,accrued,'Dividend entitlement')
        near(row.dividends_paid,paid,'Dividend payment')
        for s in symbols:near(getattr(row,f'quantity_{s}'),positions[s],'Saved positions')
        prior_nav=row.equity
    if len(claims)!=len(claims_saved):raise ValueError('Dividend receipt count')
    for actual,saved in zip(claims,claims_saved.itertuples()):
        if actual['symbol']!=saved.symbol or actual['ex_date']!=saved.ex_date or actual['pay_date']!=saved.pay_date:
            raise ValueError('Dividend receipt identity')
        near(saved.amount,actual['amount'],'Receipt amount');near(saved.shares,actual['shares'],'Receipt shares')
        if bool(saved.paid)!=actual['paid']:raise ValueError('Receipt paid status')
        if actual['paid'] and saved.cash_day!=actual['cash_day']:raise ValueError('Receipt payment day')
    near(summary['final_nav_usd'],daily.equity.iloc[-1],'Final NAV')
    near(summary['costs_usd'],orders.cost.sum(),'Total fees')
    near(summary['return_pct'],(daily.equity.iloc[-1]/cfg['initial_capital_usd']-1)*100,'Total return')
    values=np.r_[cfg['initial_capital_usd'],daily.equity.to_numpy()]
    near(summary['max_drawdown_pct'],(values/np.maximum.accumulate(values)-1).min()*100,'Max DD')
    initial=cfg['initial_capital_usd']
    for a in annual.itertuples():
        g=daily[daily.date.dt.year.eq(a.year)]
        near(a.initial_capital_usd,initial,'Annual initial NAV');near(a.final_nav_usd,g.equity.iloc[-1],'Annual final NAV')
        near(a.return_pct,(g.equity.iloc[-1]/initial-1)*100,'Annual return');initial=g.equity.iloc[-1]
    return dict(strategy=summary['strategy'],cost_bps=summary['cost_bps'],sessions=len(daily),
        orders=len(orders),decisions=len(decisions),claims=len(claims),status='PASS')


def run(root):
    out=root/'ledger-audit-v1'
    if out.exists():raise ValueError('Immutable audit directory')
    b=root/'backtest-v1';q=root/'qualified-v1';cfg=READ(root/'protocol.json')['config']
    for folder in [b,q]:
        verify_hashes(folder,READ(folder/'report.json')['files'])
        verify_hashes(Path('.'),READ(folder/'protocol.json')['sources'])
    p=pd.read_parquet(q/'prices.parquet');d=pd.read_parquet(q/'dividends.parquet')
    results=[]
    for folder in sorted(b.iterdir()):
        if folder.is_dir():results.append(audit_scenario(folder,p,d,cfg));print(folder.name,'PASS',flush=True)
    if len(results)!=9:raise ValueError('Expected nine scenarios')
    out.mkdir()
    atomic_json(out/'report.json',dict(status='PASS_ARITHMETIC_AND_TIMING_REPLAY',created_at_utc=datetime.now(timezone.utc).isoformat(),
        results=results,sources={str(p):digest(p) for p in [Path(__file__),Path('tests/test_multi_asset_trend_audit.py'),b/'report.json',q/'report.json']},
        scope='Independent arithmetic replay by same assistant, NOT independent human review or source certification. No live parity or strategy promotion.',
        no_sql_writes=True,no_orders=True))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    run(p.parse_args().root)
