"""Audit three LONG >=0.90 TP20/SL10 replays offline, without API/SQL."""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def close(actual,expected,label):
    if not np.allclose(actual,expected,atol=1e-6,rtol=1e-9):raise ValueError(label)


def audit(root):
    root=Path(root); read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
    p=read(root/'ready.json'); result=read(root/'report.json')
    if p!=read(root/'protocol.json') or result['status']!='COMPLETED' or len(result['reports'])!=3:
        raise ValueError('Complete three-year protocol required')
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files'])
    panel=pd.read_parquet(root/'candidates.parquet')
    valid=panel.decision.eq('BULLISH')&panel.technical_status.eq('VALID')&panel.confidence.ge(.90)
    if int(valid.sum())!=163 or not panel.bullish_confident.eq(valid).all():raise ValueError('Wrong threshold')
    if not panel.GPT_BULLISH_CONFIDENCE_GE_090.eq(panel.selected&valid).all():raise ValueError('Wrong admission')
    prices=pd.read_parquet(p['prices']);bars=prices.set_index(['symbol','date']);cases=[]
    if {r['year'] for r in result['reports']}!={2024,2025,2026}:raise ValueError('Wrong year membership')
    for item in result['reports']:
        year=item['year'];folder=root/str(year)
        if item!=read(folder/'case-report.json') or not item['status'].startswith('COMPLETED'):
            raise ValueError('Case report differs')
        verify_hashes(folder,item['files'])
        if item['batch_id']!=p['models'][str(year)] or item['training'] or item['database_writes']:
            raise ValueError('Wrong model or side effect')
        days=nyse_sessions('2023-01-01',item['terminal_session'])
        daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        ca=read(folder/'corporate-actions.json')
        if any(row['status'] not in ('NO_POSITION','UNEXECUTED_ENTRY_CANCELLED')
               or row.get('cash_credit',0)!=0 for row in ca):
            raise ValueError('Held corporate action requires additional daily allocation audit')
        if list(daily.date)!=list(days[days>=pd.Timestamp(item['first_session'])]):raise ValueError('Incomplete curve')
        signals=panel[panel.date.dt.year.eq(year)&panel.GPT_BULLISH_CONFIDENCE_GE_090]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in signals.itertuples()
                 if days.get_loc(r.date)+1<len(days)}
        opened=[(pd.Timestamp(e['date']),s) for e in read(folder/'executions.json') for s in e['opened']]
        if len(set(opened))!=len(opened) or any(pair not in allowed for pair in opened):raise ValueError('Wrong entry')
        if len(opened)!=item['actual_entries']:raise ValueError('Wrong entry count')
        maintenance={pd.Timestamp(row['date']):row for row in read(folder/'maintenance.json')}
        lots=[]
        for row in trades.itertuples():
            entry,exit=pd.Timestamp(row.entry_date),pd.Timestamp(row.exit_date)
            age=days.get_loc(exit)-days.get_loc(entry);bar=bars.loc[(row.symbol,exit)]
            if row.side!='buy' or row.quantity<=0 or not 0<=age<=20:raise ValueError('Wrong side/age/quantity')
            close(row.entry_price,bars.at[(row.symbol,entry),'open'],'Wrong entry open')
            stop,target=row.entry_price*.90,row.entry_price*1.20
            close(row.replay_initial_stop_price,stop,'Wrong SL10');close(row.replay_take_profit_price,target,'Wrong TP20')
            close(row.pnl,row.proceeds-row.entry_cost-row.borrow_cost,'Wrong LONG net cash flows')
            if row.exit_reason=='expiry_open':
                if age!=20:raise ValueError('Wrong expiry age')
                close(row.exit_price,bar.open,'Wrong expiry open')
            elif row.exit_reason=='initial_stop_gap_open':
                if age<=0 or bar.open>stop:raise ValueError('Wrong gap stop trigger')
                close(row.exit_price,bar.open,'Wrong gap fill')
            elif row.exit_reason=='take_profit_gap_limit':
                if bar.open<target:raise ValueError('Wrong gap TP trigger')
                close(row.exit_price,target,'Wrong TP limit')
            elif row.exit_reason=='initial_stop':
                if bar.low>stop:raise ValueError('Stop not touched')
                close(row.exit_price,stop,'Wrong SL fill')
            elif row.exit_reason=='take_profit':
                if bar.high<target or bar.low<=stop:raise ValueError('TP not touched or stop collision ignored')
                close(row.exit_price,target,'Wrong TP fill')
            elif row.exit_reason in ('regime_reduce','regime_liquidate','learned_exit_next_open'):
                close(row.exit_price,bar.open,'Wrong queued exit open')
                if row.exit_reason=='learned_exit_next_open' and not maintenance[days[days.get_loc(exit)-1]]['breach']:
                    raise ValueError('Margin exit without previous breach')
            else:raise ValueError('Unexpected exit reason '+row.exit_reason)
            lots.append(dict(symbol=row.symbol,quantity=row.quantity,entry=entry,exit=exit,cost=row.entry_cost))
        open_keys=set()
        for pos in item['open_positions']:
            entry=pd.Timestamp(pos['entry_date']);open_keys.add((pos['symbol'],entry))
            if days.get_loc(days[-1])-days.get_loc(entry)>=20:raise ValueError('Expired open lot')
            cost=pos['quantity']*pos['mark']-pos['unrealized_pnl_usd']
            lots.append(dict(symbol=pos['symbol'],quantity=pos['quantity'],entry=entry,
                             exit=days[-1]+pd.Timedelta(days=1),cost=cost))
        position_keys=set(zip(trades.symbol,pd.to_datetime(trades.entry_date)))|open_keys
        if position_keys!={(symbol,day) for day,symbol in opened}:raise ValueError('Unaccounted entry')
        interest=0.
        for row in daily.itertuples():
            day=pd.Timestamp(row.date);active=[lot for lot in lots if lot['entry']<=day<lot['exit']]
            mark=sum(lot['quantity']*bars.at[(lot['symbol'],day),'close'] for lot in active)
            realized=float(trades.loc[trades.exit_date.le(day),'pnl'].sum());interest+=float(row.margin_interest)
            close(row.positions,len({lot['symbol'] for lot in active}),'Wrong position count')
            close(row.gross_notional,mark,'Wrong mark')
            close(row.settled_cash+row.unsettled_cash,4000+realized-interest-sum(lot['cost'] for lot in active),'Daily cash mismatch')
            close(row.equity,row.settled_cash+row.unsettled_cash+mark,'Daily wealth mismatch')
        pnl=trades.groupby(['symbol','entry_date']).pnl.sum()
        closed=pnl[[key not in open_keys for key in pnl.index]]
        if int(closed.gt(0).sum())!=item['winning_positions'] or int(closed.lt(0).sum())!=item['losing_positions']:
            raise ValueError('Wrong closed win/loss count')
        close(interest,item['margin_interest'],'Interest mismatch')
        close(daily.equity.iloc[-1],item['final_capital_usd'],'Final capital mismatch')
        calendar=daily[daily.date.le(f'{year}-12-31' if year<2026 else '2026-09-30')]
        curve=pd.concat([pd.Series([4000.]),calendar.equity],ignore_index=True)
        close(curve.iloc[-1],item['calendar_end_capital_usd'],'Wrong calendar capital')
        close(100*(curve/curve.cummax()-1).min(),item['calendar_end_drawdown_pct'],'Wrong DD')
        if year<2026 and item['open_positions']:raise ValueError('Incomplete old-year tail')
        cases.append(dict(year=year,positions=len(opened),wins=int(closed.gt(0).sum()),losses=int(closed.lt(0).sum()),
            open_positions=len(open_keys),capital=item['calendar_end_capital_usd'],return_pct=item['calendar_end_return_pct'],
            dd_pct=item['calendar_end_drawdown_pct'],checks_passed=True))
    value=dict(status='AUDITED_EXPLORATORY_NOT_PIT',cases=cases,no_new_gpt_calls=True,sql_writes=False,
        no_training=True,production_changes=False,
        files={name:digest(root/name) for name in ['ready.json','report.json','candidates.parquet']},
        audit_script_sha256=digest(Path(__file__)))
    atomic_json(root/'audit.json',value);return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(audit(parser.parse_args().output)))
