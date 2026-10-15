"""Independent offline accounting/selection checks for BEARISH-as-LONG TP10/SL10."""
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
    root=Path(root);read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
    protocol=read(root/'ready.json');report=read(root/'report.json')
    if protocol!=read(root/'protocol.json') or report['status']!='COMPLETED' or len(report['reports'])!=3:
        raise ValueError('Complete three-case protocol required')
    if protocol['side']!='LONG' or protocol['tp']!=.1 or protocol['sl']!=.1 or not protocol['no_extra_confidence_threshold']:
        raise ValueError('Wrong inversion contract')
    verify_hashes(Path('.'),protocol['sources']);verify_hashes(root,protocol['files'])
    panel=pd.read_parquet(root/'candidates.parquet')
    source=Path('artifacts/research/us_news_gpt_bearish_portfolio/20261015-v1')
    original=pd.read_parquet(source/'candidates.parquet')
    pd.testing.assert_frame_equal(panel.drop(columns='GPT_BEARISH_AS_LONG'),original)
    valid=panel.decision.eq('BEARISH')&panel.technical_status.eq('VALID')
    if int(valid.sum())!=734 or not panel.GPT_BEARISH_AS_LONG.eq(panel.selected&valid).all():
        raise ValueError('Wrong BEARISH admission')
    raw=read(source/'sql-bearish-validation.json')
    if len(raw)!=734 or {r['cache_key'] for r in raw}!=set(panel.loc[valid,'cache_key']):
        raise ValueError('Wrong raw SQL response membership')
    prices=pd.read_parquet(protocol['prices']);bars=prices.set_index(['symbol','date']);cases=[]
    by_signal=panel.set_index(['date','symbol'])
    if {r['year'] for r in report['reports']}!={2024,2025,2026}:raise ValueError('Wrong years')
    for item in report['reports']:
        year=item['year'];folder=root/str(year)
        if read(folder/'case-report.json')!=item or not item['status'].startswith('COMPLETED'):
            raise ValueError('Incomplete or changed case')
        verify_hashes(folder,item['files'])
        if item['batch_id']!=protocol['models'][str(year)] or item['training'] or item['database_writes']:
            raise ValueError('Wrong model or side effects')
        ca=read(folder/'corporate-actions.json')
        if any(row['status'] not in ('NO_POSITION','UNEXECUTED_ENTRY_CANCELLED') or row.get('cash_credit',0)!=0 for row in ca):
            raise ValueError('Held corporate action needs additional accounting checks')
        days=nyse_sessions('2023-01-01',item['terminal_session'])
        daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
        if list(daily.date)!=list(days[days>=pd.Timestamp(item['first_session'])]):raise ValueError('Incomplete curve')
        if trades.empty:
            trades=pd.DataFrame({name:pd.Series(dtype='object') for name in ['symbol','entry_date','exit_date','pnl']})
            for name in ('entry_date','exit_date'):trades[name]=pd.to_datetime(trades[name])
        signals=panel[panel.date.dt.year.eq(year)&panel.GPT_BEARISH_AS_LONG]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in signals.itertuples() if days.get_loc(r.date)+1<len(days)}
        opened=[(pd.Timestamp(e['date']),s) for e in read(folder/'executions.json') for s in e['opened']]
        if len(set(opened))!=len(opened) or any(pair not in allowed for pair in opened):raise ValueError('Unexpected entry')
        if len(opened)!=item['actual_entries']:raise ValueError('Wrong entry count')
        maintenance={pd.Timestamp(r['date']):r for r in read(folder/'maintenance.json')}
        lots=[]
        for trade in trades.itertuples():
            entry,exit=pd.Timestamp(trade.entry_date),pd.Timestamp(trade.exit_date)
            age=days.get_loc(exit)-days.get_loc(entry);bar=bars.loc[(trade.symbol,exit)]
            if trade.side!='buy' or not np.isfinite(trade.quantity) or trade.quantity<=0 or not 0<=age<=20:
                raise ValueError('Wrong side, quantity or age')
            signal=by_signal.loc[(pd.Timestamp(trade.signal_date),trade.symbol)]
            if signal.decision!='BEARISH' or signal.technical_status!='VALID':raise ValueError('Not a valid BEARISH entry')
            close(trade.entry_price,bars.at[(trade.symbol,entry),'open'],'Wrong entry price')
            stop,target=trade.entry_price*.9,trade.entry_price*1.1
            close(trade.replay_initial_stop_price,stop,'Wrong SL10');close(trade.replay_take_profit_price,target,'Wrong TP10')
            close(trade.borrow_cost,0.,'Unexpected borrowing fee on LONG')
            close(trade.pnl,trade.proceeds-trade.entry_cost,'Wrong LONG cash flow')
            if trade.exit_reason=='expiry_open':
                if age!=20:raise ValueError('Wrong expiry age')
                close(trade.exit_price,bar.open,'Wrong expiry open')
            elif trade.exit_reason=='initial_stop_gap_open':
                if age<=0 or bar.open>stop:raise ValueError('Wrong stop gap trigger')
                close(trade.exit_price,bar.open,'Wrong stop gap fill')
            elif trade.exit_reason=='take_profit_gap_limit':
                if bar.open<target:raise ValueError('Wrong TP gap trigger')
                close(trade.exit_price,target,'Wrong TP gap limit')
            elif trade.exit_reason=='initial_stop':
                if bar.low>stop:raise ValueError('Stop not touched')
                close(trade.exit_price,stop,'Wrong stop fill')
            elif trade.exit_reason=='take_profit':
                if bar.high<target or bar.low<=stop:raise ValueError('TP not touched or stop collision ignored')
                close(trade.exit_price,target,'Wrong target fill')
            elif trade.exit_reason in ('regime_reduce','regime_liquidate','learned_exit_next_open'):
                close(trade.exit_price,bar.open,'Wrong next-open queued exit')
                if trade.exit_reason=='learned_exit_next_open' and not maintenance[days[days.get_loc(exit)-1]]['breach']:
                    raise ValueError('Margin exit without previous breach')
            else:raise ValueError('Unexpected exit '+trade.exit_reason)
            lots.append(dict(symbol=trade.symbol,quantity=trade.quantity,entry=entry,exit=exit,cost=trade.entry_cost))
        open_keys=set()
        for pos in item['open_positions']:
            entry=pd.Timestamp(pos['entry_date']);open_keys.add((pos['symbol'],entry))
            if days.get_loc(days[-1])-days.get_loc(entry)>=20:raise ValueError('Expired open lot')
            close(pos['mark'],bars.at[(pos['symbol'],days[-1]),'close'],'Wrong terminal mark')
            lots.append(dict(symbol=pos['symbol'],quantity=pos['quantity'],entry=entry,exit=days[-1]+pd.Timedelta(days=1),
                             cost=pos['quantity']*pos['mark']-pos['unrealized_pnl_usd']))
        if (set(zip(trades.symbol,trades.entry_date))|open_keys)!={(symbol,day) for day,symbol in opened}:
            raise ValueError('Opened lots not accounted for')
        interest=0.
        for row in daily.itertuples():
            day=pd.Timestamp(row.date);active=[lot for lot in lots if lot['entry']<=day<lot['exit']]
            mark=sum(lot['quantity']*bars.at[(lot['symbol'],day),'close'] for lot in active)
            realized=float(trades.loc[trades.exit_date.le(day),'pnl'].sum());interest+=float(row.margin_interest)
            close(row.positions,len({lot['symbol'] for lot in active}),'Wrong position count')
            close(row.gross_notional,mark,'Wrong MTM')
            close(row.settled_cash+row.unsettled_cash,4000+realized-interest-sum(lot['cost'] for lot in active),'Daily cash mismatch')
            close(row.equity,row.settled_cash+row.unsettled_cash+mark,'Daily wealth mismatch')
        pnl=trades.groupby(['symbol','entry_date']).pnl.sum()
        closed=pnl[[key not in open_keys for key in pnl.index]]
        if int(closed.gt(0).sum())!=item['winning_positions'] or int(closed.lt(0).sum())!=item['losing_positions']:
            raise ValueError('Wrong winning/losing counts')
        close(item['margin_interest'],interest,'Wrong funding total');close(item['final_capital_usd'],daily.equity.iloc[-1],'Wrong final capital')
        calendar=daily[daily.date.le(f'{year}-12-31' if year<2026 else '2026-09-30')]
        curve=pd.concat([pd.Series([4000.]),calendar.equity],ignore_index=True)
        close(item['calendar_end_capital_usd'],curve.iloc[-1],'Wrong calendar capital')
        close(item['calendar_end_return_pct'],100*(curve.iloc[-1]/4000-1),'Wrong calendar return')
        close(item['calendar_end_drawdown_pct'],100*(curve/curve.cummax()-1).min(),'Wrong drawdown')
        if year<2026 and item['open_positions']:raise ValueError('Incomplete expiry tail')
        cases.append(dict(year=year,actual_entries=len(opened),closed_positions=len(closed),wins=int(closed.gt(0).sum()),
            losses=int(closed.lt(0).sum()),open_positions=len(open_keys),capital=item['calendar_end_capital_usd'],
            return_pct=item['calendar_end_return_pct'],dd_pct=item['calendar_end_drawdown_pct'],checks_passed=True))
    value=dict(status='AUDITED_EXPLORATORY_NOT_PIT',cases=cases,api_calls=0,sql_writes=False,training=False,
        production_changes=False,files={name:digest(root/name) for name in ['ready.json','report.json','candidates.parquet']},
        audit_script_sha256=digest(Path(__file__)))
    atomic_json(root/'audit.json',value);return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(audit(parser.parse_args().output)))
