"""Offline post-run checks, no GPT, SQL, training or broker access."""
import argparse
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import digest,verify_hashes,atomic_json
from modelFactory.oracle.build_labels import nyse_sessions


def audit(root):
    root=Path(root)
    p=json.loads((root/'ready.json').read_text(encoding='utf-8'))
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,p['files'])
    report=json.loads((root/'report.json').read_text(encoding='utf-8'))
    if report['status']!='COMPLETED' or len(report['reports'])!=6:raise ValueError('Six completed cases required')
    candidates=pd.read_parquet(root/'candidates.parquet')
    if candidates[candidates.bullish].shape[0]!=913:raise ValueError('Original bullish membership changed')
    cases=[]
    for item in report['reports']:
        folder=root/f'{item["year"]}-{item["arm"]}'
        verify_hashes(folder,item['files'])
        days=nyse_sessions('2023-01-01',item['terminal_session'])
        trades=pd.read_parquet(folder/'trades.parquet');daily=pd.read_parquet(folder/'daily.parquet')
        signals=candidates[candidates.date.dt.year.eq(item['year'])&candidates[item['arm']]]
        allowed={(days[days.get_loc(r.date)+1],r.symbol) for r in signals.itertuples() if days.get_loc(r.date)+1<len(days)}
        executions=json.loads((folder/'executions.json').read_text(encoding='utf-8'))
        opened=[(pd.Timestamp(e['date']),symbol) for e in executions for symbol in e['opened']]
        if any(key not in allowed for key in opened):raise ValueError('Unexpected entry')
        expiries=trades[trades.exit_reason.eq('expiry_open')]
        for trade in expiries.itertuples():
            if days.get_loc(trade.exit_date)-days.get_loc(trade.entry_date)!=20:raise ValueError('Incorrect expiry age')
        if not trades.side.eq('buy').all():raise ValueError('Unexpected short')
        if not np.isclose(trades.replay_initial_stop_price,trades.entry_price*.95,rtol=1e-7,atol=1e-6).all():
            raise ValueError('Wrong SL')
        if not np.isclose(trades.replay_take_profit_price,trades.entry_price*1.20,rtol=1e-7,atol=1e-6).all():
            raise ValueError('Wrong TP')
        if trades.exit_reason.str.contains('terminal_close|trailing',regex=True).any():raise ValueError('Unexpected terminal/trailing exit')
        realized=float(trades.pnl.sum());latent=sum(v['unrealized_pnl_usd'] for v in item['open_positions'])
        expected=4000+realized+latent-item['margin_interest']
        if not np.isclose(expected,daily.equity.iloc[-1],atol=1e-6):raise ValueError('Wealth reconciliation failed')
        for position in item['open_positions']:
            if days.get_loc(days[-1])-days.get_loc(position['entry_date'])>=20:raise ValueError('Expired position not closed')
        terminal=daily[pd.to_datetime(daily.date).le(f'{item["year"]}-12-31' if item['year']<2026 else '2026-09-30')].iloc[-1]
        cases.append(dict(year=item['year'],arm=item['arm'],actual_entries=len(opened),closed_positions=item['closed_positions'],
            open_positions=len(item['open_positions']),expiry_trades=len(expiries),
            calendar_end_capital_usd=float(terminal.equity),calendar_end_positions=int(terminal.positions),
            calendar_return_pct=item['calendar_end_return_pct'],cohort_final_capital_usd=item['final_capital_usd'],
            cohort_return_pct=item['net_return_pct'],max_drawdown_pct=item['max_drawdown_pct'],
            calendar_drawdown_pct=item['calendar_end_drawdown_pct'],winning_pct=item['winning_pct'],
            winning_positions=item['winning_positions'],losing_positions=item['losing_positions'],
            mean_gross_leverage=item['mean_gross_leverage'],all_checks_passed=True))
    comparisons=[]
    for year in (2024,2025,2026):
        long=next(c for c in cases if c['year']==year and c['arm']=='GPT_BULLISH_ONLY')
        control=next(c for c in cases if c['year']==year and c['arm']=='ORACLE_TOP20_ALL_LONG')
        comparisons.append(dict(year=year,calendar_equity_advantage_usd=long['calendar_end_capital_usd']-control['calendar_end_capital_usd'],
            cohort_equity_advantage_usd=long['cohort_final_capital_usd']-control['cohort_final_capital_usd'],
            calendar_return_advantage_points=long['calendar_return_pct']-control['calendar_return_pct'],
            max_drawdown_reduction_points=long['max_drawdown_pct']-control['max_drawdown_pct'],
            exposure_matched=False))
    value=dict(status='AUDITED_EXPLORATORY_NOT_PIT',cases=cases,comparisons=comparisons,
        no_new_gpt_calls=True,sql_writes=False,independent_holdout=False,
        verdict='NO_UNIFORM_RETURN_DOMINANCE; lower observed drawdowns, lower exposure confounds selection advantage',
        files={name:digest(root/name) for name in ['report.json','ready.json','sql-snapshots.json','candidates.parquet']})
    atomic_json(root/'audit.json',value);return value


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.output)
    print(json.dumps({key:value for key,value in result.items() if key!='files'}))
