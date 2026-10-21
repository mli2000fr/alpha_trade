"""Exploratory five-deal ledger, supplier payment proxy explicit, no live parity."""
import argparse
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_cash_merger_completion import READ
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

SCENARIOS=[
    dict(name='PRIMARY',cash_yield=.04,entry_bps=10,payment_delay_sessions=0),
    dict(name='CASH_ZERO',cash_yield=0.,entry_bps=10,payment_delay_sessions=0),
    dict(name='CASH_FIVE',cash_yield=.05,entry_bps=10,payment_delay_sessions=0),
    dict(name='ENTRY_ZERO_BPS',cash_yield=.04,entry_bps=0,payment_delay_sessions=0),
    dict(name='ENTRY_25_BPS',cash_yield=.04,entry_bps=25,payment_delay_sessions=0),
    dict(name='CREDIT_PLUS_2_SESSIONS',cash_yield=.04,entry_bps=10,payment_delay_sessions=2),
    dict(name='CREDIT_PLUS_5_SESSIONS',cash_yield=.04,entry_bps=10,payment_delay_sessions=5)]


def payment_day(provider_date,delay):
    if provider_date is None:raise ValueError('Missing provider payment date, no T+2 imputation')
    if delay<0:raise ValueError('Negative cash delay')
    days=mcal.get_calendar('NYSE').valid_days(start_date=provider_date,end_date=pd.Timestamp(provider_date)+pd.Timedelta(days=60))
    return pd.Timestamp(days[delay]).tz_localize(None).normalize()


def simulate(bars,events,config,scenario):
    prices=bars.copy();prices['date']=pd.to_datetime(prices.date)
    if prices.duplicated(['symbol','date']).any():raise ValueError('Duplicate executable price')
    close=prices.set_index(['symbol','date']).c.to_dict();opens=prices.set_index(['symbol','date']).o.to_dict()
    symbols=[e['symbol'] for e in events]
    if len(set(symbols))!=len(symbols):raise ValueError('One economic cash event per issuer required')
    dates={s:sorted(prices.loc[prices.symbol.eq(s),'date']) for s in symbols}
    session_days={pd.Timestamp(d).tz_localize(None).normalize() for d in mcal.get_calendar('NYSE').valid_days(
        start_date=config['start'],end_date=config['end'])}
    budget=config['initial_capital_usd']*config['slot_weight'];cash=float(config['initial_capital_usd']);benchmark=cash
    fee_bps=scenario['entry_bps']/10000;fixed=config['commission_per_buy_usd'];actionfee=config['cash_action_fee_usd']
    interest_rate=(1+scenario['cash_yield'])**(1/365)-1
    prepared=[]
    for e in events:
        if not dates[e['symbol']]:raise ValueError('No complete entry tape')
        legal=pd.Timestamp(e['sec_legal_closing']);pay=payment_day(e['provider_payable_date'],scenario['payment_delay_sessions'])
        if pay<legal:raise ValueError('Cash cannot precede legal cash right')
        prepared.append(dict(**e,entry_day=dates[e['symbol']][0],legal_day=legal,payment_day=pay))
    state={};trades=[];daily=[];flows=[]
    for day in pd.date_range(config['start'],config['end']):
        before=cash;entry_cost=0.;interest=0.;event_count=0
        # Cash right replaces stock once, never multiplied by provider-row count.
        for e in prepared:
            s=e['symbol']
            if e['legal_day']==day and s in state:
                position=state[s]
                if position['phase']!='STOCK':raise ValueError('Duplicate legal conversion')
                position.update(phase='RECEIVABLE',claim=position['quantity']*e['cash_per_share_usd'])
                flows.append(dict(date=day,symbol=s,type='LEGAL_STOCK_TO_CASH_RIGHT',amount=position['claim']))
            if e['payment_day']==day and s in state:
                position=state[s]
                if position['phase']!='RECEIVABLE':raise ValueError('Duplicate or premature cash payment')
                cash+=position['claim']-actionfee;position['phase']='PAID';event_count+=1
                flows.append(dict(date=day,symbol=s,type='PROXY_CASH_PAYMENT',amount=position['claim']-actionfee))
        for e in sorted(prepared,key=lambda e:e['symbol']):
            s=e['symbol']
            if e['entry_day']!=day:continue
            if day not in session_days:raise ValueError('Non-session entry')
            if s in state:raise ValueError('Repeat issuer entry')
            if cash+1e-8<budget:raise ValueError('Insufficient cash: never borrow or drop issuer silently')
            price=float(opens[(s,day)])
            if not np.isfinite(price) or price<=0 or budget<=fixed:raise ValueError('Invalid entry/sizing')
            notional=(budget-fixed)/(1+fee_bps);quantity=notional/price;fees=fixed+notional*fee_bps
            cash-=notional+fees;entry_cost+=fees
            state[s]=dict(phase='STOCK',quantity=quantity,last_close=price,claim=0.)
            trade=dict(symbol=s,entry_date=day,entry_open_proxy=price,quantity=quantity,entry_notional_usd=notional,
                cash_budget_usd=budget,entry_cost_usd=fees,legal_closing=e['legal_day'],proxy_payment_date=e['payment_day'],
                cash_per_share_usd=e['cash_per_share_usd'],gross_cash_right_usd=quantity*e['cash_per_share_usd'],
                cash_action_fee_usd=actionfee,
                net_trade_profit_usd=quantity*e['cash_per_share_usd']-actionfee-budget)
            trades.append(trade);flows.append(dict(date=day,symbol=s,type='BUY_BUDGET_AND_COSTS',amount=-budget))
        market=0.;receivable=0.;held=0
        for s,position in state.items():
            if position['phase']=='STOCK':
                if day in session_days:
                    if (s,day) not in close:raise ValueError('Missing held-position session; do not forward fill')
                    position['last_close']=float(close[(s,day)])
                market+=position['quantity']*position['last_close'];held+=1
            elif position['phase']=='RECEIVABLE':receivable+=position['claim']
        if cash< -1e-7:raise ValueError('Borrowing prohibited')
        cash=max(0.,cash);interest=cash*interest_rate;cash+=interest;benchmark*=1+interest_rate
        nav=cash+market+receivable
        daily.append(dict(date=day,cash=cash,market_value=market,receivable=receivable,equity=nav,
            cash_benchmark=benchmark,interest=interest,entry_cost=entry_cost,held_stocks=held,payments=event_count))
    d=pd.DataFrame(daily);t=pd.DataFrame(trades);f=pd.DataFrame(flows)
    expected_entries=sum(pd.Timestamp(config['start'])<=e['entry_day']<=pd.Timestamp(config['end']) for e in prepared)
    if len(t)!=expected_entries:raise ValueError('Missing selected deal')
    initial=config['initial_capital_usd'];values=np.r_[initial,d.equity.to_numpy()]
    summary=dict(**scenario,initial_capital_usd=initial,final_nav_usd=float(d.equity.iloc[-1]),
        portfolio_profit_usd=float(d.equity.iloc[-1]-initial),return_pct=float((d.equity.iloc[-1]/initial-1)*100),
        cash_benchmark_final_usd=float(d.cash_benchmark.iloc[-1]),cash_benchmark_profit_usd=float(d.cash_benchmark.iloc[-1]-initial),
        excess_vs_cash_usd=float(d.equity.iloc[-1]-d.cash_benchmark.iloc[-1]),
        max_drawdown_pct=float((values/np.maximum.accumulate(values)-1).min()*100),
        trades=len(t),winning_trades=int(t.net_trade_profit_usd.gt(1e-8).sum()),
        losing_trades=int(t.net_trade_profit_usd.lt(-1e-8).sum()),flat_trades=int(t.net_trade_profit_usd.abs().le(1e-8).sum()),
        sum_net_trade_profit_usd=float(t.net_trade_profit_usd.sum()),
        total_entry_costs_usd=float(t.entry_cost_usd.sum()),cash_interest_usd=float(d.interest.sum()),
        mean_invested_pct=float((d.market_value/d.equity).mean()*100),max_held_stocks=int(d.held_stocks.max()),
        final_receivables_usd=float(d.receivable.iloc[-1]),proxy_cash_payments=int(d.payments.sum()),
        broker_credit_proven=False,no_live_parity=True)
    if summary['proxy_cash_payments']==len(events):
        if summary['final_receivables_usd']!=0 or d.market_value.iloc[-1]!=0:raise ValueError('Unreconciled terminal positions')
        if not np.isclose(summary['portfolio_profit_usd'],summary['sum_net_trade_profit_usd']+summary['cash_interest_usd'],atol=1e-7):
            raise ValueError('Profit/interest/cash reconciliation failed')
    return d,t,f,summary


def prepare(root):
    data=root/'tapes-v1';out=root/'economic-v1'
    if (out/'protocol.json').exists():
        p=READ(out/'protocol.json');verify_hashes(Path('.'),p['sources']);return out,p
    if out.exists():raise ValueError('Fresh immutable economic output required')
    report=READ(data/'report.json');verify_hashes(data,report['files']);verify_hashes(Path('.'),READ(data/'protocol.json')['sources'])
    if report['pre_closing_bars']!=94 or report['term_eligible']!=5:raise ValueError('Fixed candidate population changed')
    out.mkdir()
    config=dict(start='2024-01-01',end='2024-06-30',initial_capital_usd=4000.,slot_weight=.2,
        commission_per_buy_usd=1.,cash_action_fee_usd=0.,fractional_shares=True,leverage=False,short=False)
    paths=[Path(__file__),Path('tests/test_us_cash_merger_economic_pilot.py'),data/'report.json',data/'cash-action-reconciliation.json',data/'pre-closing-bars.parquet']
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),config=config,scenarios=SCENARIOS,
        sources={str(f):digest(f) for f in paths},
        rule='Fixed5slots,20%INITIAL capital per market-acquired public eligible deal, next-session open after initial tender filing; no price/spread ranking, TP, SL, leverage, replacement or tuning.',
        fees='1USD per BUY plus10bps one-way entry friction primary. Cash merger is NOT a market sale: no fictitious exit spread, corporate-action fee0USD assumption; not broker-certified tariff.',
        cash='Base credits at SUPPLIER payable_date, not actual broker proof. +2/+5NYSEsession sensitivities. Legal receivable at SEC closing earns no interest, cannot buy before proxy payment. Exactly one payment per economic event.',
        interest='4%effective annual hypothetical cash yield, ACT365 daily end-of-day post-flow cash, same cash-only benchmark.0/5% sensitivities; NOT actual historical Treasury/broker rates.',
        marks='Daily calendar ledger: last close carried only over non-trading days, never missing trading sessions or delisted stock. No ending forced sale; all payments assessed at fixedJun30.',
        interpretation='Exploratory known5completed deals, NOT untouched validation or estimate of merger-break risk. No annualization of six-month result. No causal claim or live parity.',
        no_new_data=True,no_sql_writes=True,no_orders=True,no_training=True,no_llm=True)
    atomic_json(out/'protocol.json',p);return out,p


def run(root):
    out,p=prepare(root)
    if (out/'report.json').exists():raise ValueError('Immutable economic results')
    bars=pd.read_parquet(root/'tapes-v1/pre-closing-bars.parquet');events=READ(root/'tapes-v1/cash-action-reconciliation.json')
    results=[]
    for scenario in p['scenarios']:
        d,t,f,s=simulate(bars,events,p['config'],scenario);folder=out/scenario['name'];folder.mkdir()
        for name,frame in [('daily',d),('trades',t),('cash-flows',f)]:frame.to_parquet(folder/f'{name}.parquet',index=False)
        atomic_json(folder/'summary.json',s);results.append(s);print(scenario['name'],'COMPLETE',flush=True)
    pd.DataFrame(results).to_csv(out/'summary.csv',index=False)
    pd.read_parquet(out/'PRIMARY/trades.parquet').to_csv(out/'trades.csv',index=False)
    atomic_json(out/'report.json',dict(status='EXPLORATORY_CALCULATED_PENDING_REPLAY_AUDIT',results=results,
        primary='PRIMARY',fixed_scenarios_not_best_parameter_selection=True,
        files={str(f.relative_to(out)):digest(f) for f in out.rglob('*') if f.is_file()}))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    p.add_argument('--phase',choices=['prepare','run'],required=True);a=p.parse_args()
    globals()[a.phase](a.root)
