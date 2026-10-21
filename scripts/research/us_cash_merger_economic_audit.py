"""Analytical cash-flow/mark replay of every frozen merger scenario, offline."""
import argparse
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_cash_merger_completion import READ
from scripts.research.us_cash_merger_economic_pilot import payment_day
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def near(a,b,label):
    if not np.isclose(a,b,atol=1e-7,rtol=1e-9):raise ValueError(f'Replay mismatch {label}')


def run(root):
    economic=root/'economic-v1';out=root/'economic-audit-v1'
    if out.exists():raise ValueError('Immutable replay output')
    p=READ(economic/'protocol.json');r=READ(economic/'report.json')
    verify_hashes(Path('.'),p['sources']);verify_hashes(economic,r['files'])
    cfg=p['config'];bars=pd.read_parquet(root/'tapes-v1/pre-closing-bars.parquet');bars.date=pd.to_datetime(bars.date)
    source={e['symbol']:e for e in READ(root/'tapes-v1/cash-action-reconciliation.json')}
    cal={d.date() for d in mcal.get_calendar('NYSE').valid_days(start_date=cfg['start'],end_date=cfg['end'])}
    results=[]
    for scenario in p['scenarios']:
        folder=economic/scenario['name'];d=pd.read_parquet(folder/'daily.parquet');t=pd.read_parquet(folder/'trades.parquet')
        f=pd.read_parquet(folder/'cash-flows.parquet');summary=READ(folder/'summary.json')
        if set(t.symbol)!=set(source) or t.symbol.duplicated().any():raise ValueError('Selected issuer omitted/duplicated')
        expected=[];budget=cfg['initial_capital_usd']*cfg['slot_weight']
        for trade in t.itertuples():
            e=source[trade.symbol];frame=bars[bars.symbol.eq(trade.symbol)].sort_values('date')
            first=frame.iloc[0];entry=first.date;legal=pd.Timestamp(e['sec_legal_closing'])
            pay=payment_day(e['provider_payable_date'],scenario['payment_delay_sessions'])
            amount=(budget-cfg['commission_per_buy_usd'])/(1+scenario['entry_bps']/10000)
            quantity=amount/float(first.o);claim=quantity*e['cash_per_share_usd']
            if trade.entry_date!=entry or trade.legal_closing!=legal or trade.proxy_payment_date!=pay:raise ValueError('Trade chronology')
            near(trade.quantity,quantity,'sizing');near(trade.entry_open_proxy,first.o,'entry open')
            near(trade.entry_cost_usd,budget-amount,'fees');near(trade.net_trade_profit_usd,claim-cfg['cash_action_fee_usd']-budget,'net trade')
            expected.append(dict(symbol=trade.symbol,entry=entry,legal=legal,pay=pay,quantity=quantity,claim=claim,frame=frame))
        for typ in ['BUY_BUDGET_AND_COSTS','LEGAL_STOCK_TO_CASH_RIGHT','PROXY_CASH_PAYMENT']:
            if (f.type.eq(typ)).sum()!=5:raise ValueError('Exactly one buy/right/payment per deal required')
        rate=(1+scenario['cash_yield'])**(1/365)-1;cash=float(cfg['initial_capital_usd']);benchmark=cash
        expected_dates=pd.date_range(cfg['start'],cfg['end'])
        if d.date.tolist()!=expected_dates.tolist():raise ValueError('Incomplete calendar ledger')
        for day,row in zip(expected_dates,d.itertuples()):
            netflow=sum(e['claim']-cfg['cash_action_fee_usd'] for e in expected if e['pay']==day)
            netflow-=sum(budget for e in expected if e['entry']==day)
            prior_to_interest=cash+netflow
            if prior_to_interest< -1e-7:raise ValueError('Borrowed cash')
            interest=prior_to_interest*rate;cash=prior_to_interest+interest;benchmark*=1+rate
            claims=sum(e['claim'] for e in expected if e['legal']<=day<e['pay'])
            market=0
            for e in expected:
                if e['entry']<=day<e['legal']:
                    frame=e['frame'];available=frame[frame.date.le(day)]
                    if day.date() in cal and not frame.date.eq(day).any():raise ValueError('Missing held-session price')
                    market+=e['quantity']*float(available.iloc[-1].c)
            near(row.cash,cash,'cash');near(row.interest,interest,'cash interest')
            near(row.receivable,claims,'legal cash right');near(row.market_value,market,'raw marked stock')
            near(row.equity,cash+claims+market,'NAV');near(row.cash_benchmark,benchmark,'cash reference')
        near(summary['excess_vs_cash_usd'],d.equity.iloc[-1]-d.cash_benchmark.iloc[-1],'excess vs cash')
        near(summary['portfolio_profit_usd'],d.equity.iloc[-1]-cfg['initial_capital_usd'],'net portfolio gain')
        near(summary['sum_net_trade_profit_usd'],t.net_trade_profit_usd.sum(),'trade aggregate')
        if summary['broker_credit_proven'] or not summary['no_live_parity']:raise ValueError('Unproven broker qualification')
        results.append(dict(name=scenario['name'],status='PASS_DAILY_ANALYTICAL_REPLAY',deals=len(t),calendar_days=len(d)))
    if len(results)!=7:raise ValueError('Fixed sensitivities changed')
    out.mkdir()
    atomic_json(out/'report.json',dict(status='PASS_SEVEN_EXPLORATORY_SCENARIOS_NOT_STRATEGY_PROMOTION',
        created_at_utc=datetime.now(timezone.utc).isoformat(),results=results,
        sources={str(f):digest(f) for f in [Path(__file__),economic/'protocol.json',economic/'report.json']},
        same_assistant_not_independent_human_review=True,no_sql_writes=True,no_orders=True))
    print('PASS',len(results),'daily analytical replays',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    run(p.parse_args().root)
