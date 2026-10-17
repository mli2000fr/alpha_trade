"""Offline accounting, signal and parity audit of nine matched TP10/SL10 LONG cases."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from modelFactory.oracle.build_labels import nyse_sessions
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes

ARMS=('GPT_BEARISH_AS_LONG','GPT_BULLISH_AS_LONG','ORACLE_TOP20_ALL_LONG')


def close(actual,expected,label):
    if not np.allclose(actual,expected,atol=1e-6,rtol=1e-9):raise ValueError(label)


def verify_case(item,folder,panel,prices):
    verify_hashes(folder,item['files']);year=item['year'];arm=item['arm']
    days=nyse_sessions('2023-01-01',item['terminal_session']);bars=prices.set_index(['symbol','date'])
    by_signal=panel.set_index(['date','symbol'])
    daily=pd.read_parquet(folder/'daily.parquet');trades=pd.read_parquet(folder/'trades.parquet')
    if list(daily.date)!=list(days[days>=pd.Timestamp(item['first_session'])]):raise ValueError('Incomplete timeline')
    ca=json.loads((folder/'corporate-actions.json').read_text(encoding='utf-8'))
    if any(r['status'] not in ('NO_POSITION','UNEXECUTED_ENTRY_CANCELLED') or r.get('cash_credit',0)!=0 for r in ca):
        raise ValueError('Held corporate action requires additional allocation audit')
    signals=panel[panel.date.dt.year.eq(year)&panel[arm]]
    allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in signals.itertuples() if days.get_loc(r.date)+1<len(days)}
    executions=json.loads((folder/'executions.json').read_text(encoding='utf-8'))
    opened=[(pd.Timestamp(e['date']),s) for e in executions for s in e['opened']]
    if len(set(opened))!=len(opened) or any(pair not in allowed for pair in opened):raise ValueError('Unexpected entry')
    if len(opened)!=item['actual_entries'] or int(signals.shape[0])!=item['candidate_days']:raise ValueError('Wrong count')
    if trades.empty:
        trades=pd.DataFrame({key:pd.Series(dtype='object') for key in ['symbol','entry_date','exit_date','pnl']})
        for key in ['entry_date','exit_date']:trades[key]=pd.to_datetime(trades[key])
    lots=[]
    maintenance={pd.Timestamp(r['date']):r for r in json.loads((folder/'maintenance.json').read_text(encoding='utf-8'))}
    for trade in trades.itertuples():
        entry,exit=pd.Timestamp(trade.entry_date),pd.Timestamp(trade.exit_date)
        signal=by_signal.loc[(pd.Timestamp(trade.signal_date),trade.symbol)]
        if not signal[arm] or trade.side!='buy' or trade.quantity<=0 or not np.isfinite(trade.quantity):
            raise ValueError('Wrong direction/selection/quantity')
        close(trade.score,signal.proba_extreme,'Not the original Oracle score')
        age=days.get_loc(exit)-days.get_loc(entry);bar=bars.loc[(trade.symbol,exit)]
        if not 0<=age<=20:raise ValueError('Wrong holding period')
        close(trade.entry_price,bars.at[(trade.symbol,entry),'open'],'Wrong entry open')
        stop,target=trade.entry_price*.9,trade.entry_price*1.1
        close(trade.replay_initial_stop_price,stop,'Wrong SL10');close(trade.replay_take_profit_price,target,'Wrong TP10')
        close(trade.borrow_cost,0.,'SHORT borrowing on LONG');close(trade.pnl,trade.proceeds-trade.entry_cost,'Wrong trade cash flow')
        if trade.exit_reason=='expiry_open':
            if age!=20:raise ValueError('Wrong expiry age')
            close(trade.exit_price,bar.open,'Wrong expiry open')
        elif trade.exit_reason=='initial_stop_gap_open':
            if age<=0 or bar.open>stop:raise ValueError('Wrong gap stop')
            close(trade.exit_price,bar.open,'Wrong gap fill')
        elif trade.exit_reason=='take_profit_gap_limit':
            if bar.open<target:raise ValueError('Wrong TP gap')
            close(trade.exit_price,target,'Wrong TP limit')
        elif trade.exit_reason=='initial_stop':
            if bar.low>stop:raise ValueError('Stop not touched')
            close(trade.exit_price,stop,'Wrong SL fill')
        elif trade.exit_reason=='take_profit':
            if bar.high<target or bar.low<=stop:raise ValueError('Wrong TP/collision')
            close(trade.exit_price,target,'Wrong TP fill')
        elif trade.exit_reason in ('regime_reduce','regime_liquidate','learned_exit_next_open'):
            close(trade.exit_price,bar.open,'Wrong next-open exit')
            if trade.exit_reason=='learned_exit_next_open' and not maintenance[days[days.get_loc(exit)-1]]['breach']:
                raise ValueError('Unjustified margin exit')
        else:raise ValueError('Unexpected exit '+trade.exit_reason)
        lots.append(dict(symbol=trade.symbol,quantity=trade.quantity,entry=entry,exit=exit,cost=trade.entry_cost))
    open_keys=set()
    for pos in item['open_positions']:
        entry=pd.Timestamp(pos['entry_date']);open_keys.add((pos['symbol'],entry))
        if days.get_loc(days[-1])-days.get_loc(entry)>=20:raise ValueError('Expired open position')
        close(pos['mark'],bars.at[(pos['symbol'],days[-1]),'close'],'Wrong terminal mark')
        lots.append(dict(symbol=pos['symbol'],quantity=pos['quantity'],entry=entry,exit=days[-1]+pd.Timedelta(days=1),
            cost=pos['quantity']*pos['mark']-pos['unrealized_pnl_usd']))
    if (set(zip(trades.symbol,trades.entry_date))|open_keys)!={(s,d) for d,s in opened}:raise ValueError('Unaccounted lot')
    interest=0.
    for row in daily.itertuples():
        day=pd.Timestamp(row.date);active=[lot for lot in lots if lot['entry']<=day<lot['exit']]
        mark=sum(lot['quantity']*bars.at[(lot['symbol'],day),'close'] for lot in active)
        realized=float(trades.loc[trades.exit_date.le(day),'pnl'].sum());interest+=float(row.margin_interest)
        close(row.positions,len({lot['symbol'] for lot in active}),'Wrong daily position count')
        close(row.gross_notional,mark,'Wrong daily MTM')
        close(row.settled_cash+row.unsettled_cash,4000+realized-interest-sum(lot['cost'] for lot in active),'Daily cash mismatch')
        close(row.equity,row.settled_cash+row.unsettled_cash+mark,'Daily wealth mismatch')
    pnl=trades.groupby(['symbol','entry_date']).pnl.sum();closed=pnl[[key not in open_keys for key in pnl.index]]
    if int(closed.gt(0).sum())!=item['winning_positions'] or int(closed.lt(0).sum())!=item['losing_positions']:
        raise ValueError('Wrong win/loss count')
    close(interest,item['margin_interest'],'Wrong funding total');close(daily.equity.iloc[-1],item['final_capital_usd'],'Wrong final capital')
    calendar=daily[daily.date.le(f'{year}-12-31' if year<2026 else '2026-09-30')]
    curve=pd.concat([pd.Series([4000.]),calendar.equity],ignore_index=True)
    close(curve.iloc[-1],item['calendar_end_capital_usd'],'Wrong calendar capital')
    close(100*(curve.iloc[-1]/4000-1),item['calendar_end_return_pct'],'Wrong calendar return')
    close(100*(curve/curve.cummax()-1).min(),item['calendar_end_drawdown_pct'],'Wrong calendar DD')
    if year<2026 and open_keys:raise ValueError('Incomplete old-year expiry tail')
    return dict(year=year,arm=arm,reused=item['reused'],source_folder=str(folder),
        actual_entries=len(opened),closed_positions=len(closed),open_positions=len(open_keys),
        winning_positions=int(closed.gt(0).sum()),losing_positions=int(closed.lt(0).sum()),
        winning_pct=item['winning_pct'],losing_pct=item['losing_pct'],
        positive_pnl_usd=item['positive_closed_pnl_usd'],negative_pnl_usd=item['negative_closed_pnl_usd'],
        calendar_capital=item['calendar_end_capital_usd'],calendar_return_pct=item['calendar_end_return_pct'],
        calendar_dd_pct=item['calendar_end_drawdown_pct'],calendar_open_positions=item['calendar_end_positions'],
        cohort_capital=item['final_capital_usd'],cohort_return_pct=item['net_return_pct'],
        mean_gross_leverage=item['mean_gross_leverage'],funding_usd=interest,checks_passed=True)


def audit(root):
    root=Path(root);read=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
    p=read(root/'ready.json');report=read(root/'report.json')
    if p!=read(root/'protocol.json') or report['status']!='COMPLETED' or len(report['reports'])!=9:
        raise ValueError('Complete nine-case comparison required')
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files'])
    legacy=read(Path(p['bearish_source'])/'ready.json');equivalence=[]
    for name,expected in legacy['sources'].items():
        path=Path(name);raw=path.read_bytes();actual=hashlib.sha256(raw).hexdigest()
        if p['sources'][name]!=actual:raise ValueError('Current source not pinned')
        if actual==expected:continue
        if path.suffix!='.py' or hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()!=expected:
            raise ValueError('Unqualified legacy source drift')
        equivalence.append(dict(path=name,original_sha256=expected,current_sha256=actual,
            normalized_lf_sha256=expected,change='PYTHON_CRLF_ONLY_NO_CONTENT_CHANGE'))
    if p['legacy_source_newline_equivalence']!=equivalence or read(root/'source-line-endings.json')['equivalent_python_paths']!=equivalence:
        raise ValueError('Incorrect source equivalence attestation')
    panel=pd.read_parquet(root/'candidates.parquet');old=pd.read_parquet(Path(p['bearish_source'])/'candidates.parquet')
    pd.testing.assert_frame_equal(panel[old.columns],old)
    for arm,decision in [(ARMS[0],'BEARISH'),(ARMS[1],'BULLISH')]:
        if not panel[arm].eq(panel.selected&panel.decision.eq(decision)&panel.technical_status.eq('VALID')).all():
            raise ValueError('Selection changed')
    if not panel[ARMS[2]].eq(panel.selected).all():raise ValueError('Unfiltered control excludes unknowns')
    prices=pd.read_parquet(p['prices']);seen=set();cases=[]
    for item in report['reports']:
        key=(item['year'],item['arm'])
        if key in seen or item['batch_id']!=p['models'][str(item['year'])]:raise ValueError('Repeated case/wrong model')
        seen.add(key)
        if (item['tp'],item['sl'],item['side'])!=(.1,.1,'LONG') or item['new_gpt_calls'] or item['database_writes'] or item['training']:
            raise ValueError('Unmatched rules/side effects')
        expected=Path(p['bearish_source'])/str(item['year']) if item['reused'] else root/f'{item["year"]}-{item["arm"]}'
        if Path(item['source_folder']).resolve()!=expected.resolve():raise ValueError('Wrong result origin')
        saved=read(expected/'case-report.json')
        reconstructed=dict(saved,arm=ARMS[0],source_folder=str(expected),reused=True,raw_candidate_days=saved['raw_bearish_days']) if item['reused'] else saved
        if reconstructed!=item:raise ValueError('Reused/new report differs')
        cases.append(verify_case(item,expected,panel,prices))
    if seen!={(year,arm) for year in (2024,2025,2026) for arm in ARMS}:raise ValueError('Missing case')
    comparisons=[]
    for year in (2024,2025,2026):
        inverted=next(c for c in cases if (c['year'],c['arm'])==(year,ARMS[0]))
        for arm in ARMS[1:]:
            control=next(c for c in cases if (c['year'],c['arm'])==(year,arm))
            comparisons.append(dict(year=year,control=arm,
                calendar_return_advantage_points=inverted['calendar_return_pct']-control['calendar_return_pct'],
                calendar_capital_advantage_usd=inverted['calendar_capital']-control['calendar_capital'],
                calendar_dd_difference_points=inverted['calendar_dd_pct']-control['calendar_dd_pct'],
                cohort_return_advantage_points=inverted['cohort_return_pct']-control['cohort_return_pct'],
                exposure_matched=False))
    value=dict(status='AUDITED_MATCHED_RULES_EXPLORATORY_NOT_PIT',cases=cases,comparisons=comparisons,
        new_cases=6,reused_cases=3,no_new_gpt_calls=True,sql_writes=False,production_changes=False,
        exposure_matched=False,independent_holdout=False,
        files={name:digest(root/name) for name in ['ready.json','report.json','candidates.parquet']},
        audit_script_sha256=digest(Path(__file__)))
    atomic_json(root/'audit.json',value);return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    print(json.dumps(audit(parser.parse_args().output)))
