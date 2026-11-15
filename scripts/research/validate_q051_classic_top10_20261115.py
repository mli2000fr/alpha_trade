"""Reconcile classic Q051 TOP10 and exact economic reproduction of blue TOP5."""
from datetime import date
from pathlib import Path
import json

import numpy as np
import pandas as pd

from scripts.research.us_q051_classic_top10_20261115 import ROOT,OLD,SELECTION,CASES,shared,meaningful,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def validate():
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    plan=read(ROOT/'protocol.json')
    for p,h in plan['sources'].items():
        if digest(Path(p))!=h:raise ValueError('Changed source: '+p)
    market_files=0
    for p,h in plan['market_manifests'].items():
        manifest=Path(p)
        if digest(manifest)!=h:raise ValueError('Changed market manifest')
        for relative,sha in read(manifest)['files'].items():
            if digest(manifest.parent/relative)!=sha:raise ValueError('Changed frozen market file: '+relative)
            market_files+=1
    with replay_market_registry(shared.restore_registry(shared.ROOT)):
        cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s for s in cal.sessions(date(2020,12,1),date(2026,11,1)) if s.is_open]
    idx={s.session_date:i for i,s in enumerate(sessions)};opens={s.session_date:pd.Timestamp(s.open_at_utc) for s in sessions}
    rows=[];configs=[]
    for name,selection in CASES.items():
        folder=ROOT/'cases'/name;out=folder/'result';r=read(out/'report.json')
        if read(folder/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Incomplete case')
        iso=read(folder/'isolation.json')
        if iso['status']!='COMPLETED' or iso.get('violations'):raise ValueError('Isolation violation')
        cfg=read(out/'configuration.json')['portfolio'];configs.append(cfg)
        if meaningful(cfg)!=meaningful(read(OLD/'result/configuration.json')['portfolio']):raise ValueError('Classic configuration changed')
        if cfg['risk_overlay']['regime_filter']['enabled'] or cfg['risk_overlay']['target_annual_vol'] is not None:
            raise ValueError('Unexpected regime/volatility overlay')
        if cfg['winner_drawdown_controller_enabled'] or cfg['winner_global_drawdown_halt']:raise ValueError('Unexpected DD liquidation')
        t=pd.read_csv(out/'trades.csv');e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
        m=pd.read_parquet(out/'equity-5m.parquet');a=pd.read_csv(out/'annual-summary.csv')
        v=pd.concat([pd.Series([4000.]),m.equity],ignore_index=True);dd=100*(v/v.cummax()-1).min()
        checks=[(e.iloc[-1],r['final_equity']),(100*(e.iloc[-1]/4000-1),r['return_pct']),
            (dd,r['max_drawdown_pct']),(4000*np.prod(1+a.return_pct/100),r['final_equity']),
            (m.gross.mean(),r['average_gross_capital']),((m.gross/m.equity).mean(),r['average_gross_equity_ratio']),
            (r['settled_cash']+r['unsettled_cash']+r['gross']+r.get('dividends_receivable',0),r['final_equity'])]
        if len(e)!=1443 or not all(np.isclose(x,y,atol=1e-6,rtol=1e-10) for x,y in checks):raise ValueError('Accounting or drawdown mismatch')
        if (len(t)!=r['closed_lot_trades'] or int(t.pnl.gt(0).sum())!=r['winners']
                or int(t.pnl.lt(0).sum())!=r['losers']):raise ValueError('Trade counts mismatch')
        expected=t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends
        if not np.allclose(expected,t.pnl,rtol=1e-10,atol=1e-7):raise ValueError('PnL mismatch')
        events=pd.read_csv(out/'events.csv');fees=events.loc[events.event.isin(['BUY_FILL','SELL_FILL']),'costs'].sum()
        if not np.isclose(fees,r['costs'],atol=1e-7):raise ValueError('Fee mismatch')
        signals=pd.read_parquet(SELECTION/'inputs'/f'signals-{selection}.parquet')
        allowed={(sessions[idx[pd.Timestamp(x.trade_date).date()]+1].session_date,x.symbol) for x in signals.itertuples()}
        for trade in t.itertuples():
            entry=pd.Timestamp(trade.entry_date);exit_=pd.Timestamp(trade.exit_date)
            if (entry.date(),trade.symbol) not in allowed or entry!=opens[entry.date()]:raise ValueError('Non-selected or non-open entry')
            held=idx[exit_.date()]-idx[entry.date()]
            if not 0<=held<=10:raise ValueError('Holding beyond open11')
            if trade.exit_reason=='HORIZON_OPEN' and (held!=10 or exit_!=opens[exit_.date()]):raise ValueError('Wrong horizon')
        if t.exit_reason.str.startswith('TP').any() or not t.side.eq('buy').all():raise ValueError('Unexpected TP or SHORT')
        run_id=read(folder/'ihm.json')['run_id']
        ui=read(Path('artifacts/ihm_backtesting_runs/run')/run_id/'artifacts/report.json')['summary']
        if not np.isclose(ui['total_return_pct'],r['return_pct'],atol=1e-7):raise ValueError('IHM mismatch')
        rows.append(dict(case=name,status='PASS',sessions=len(e),trades=len(t),return_pct=r['return_pct'],
            final_equity=r['final_equity'],max_drawdown_pct=r['max_drawdown_pct'],win_pct=r['win_pct'],
            accounting_and_chronology=True,fees_reconciled=float(fees),IHM=run_id))
    if configs[0]!=configs[1]:raise ValueError('Portfolio configurations differ between control and variant')
    original=read(OLD/'result/report.json');control=read(ROOT/'cases/CONTROL_TOP5/result/report.json')
    keys=['final_equity','return_pct','max_drawdown_pct','closed_lot_trades','winners','losers','costs','average_gross_capital']
    diffs={k:[original[k],control[k]] for k in keys if not np.isclose(original[k],control[k],rtol=1e-10,atol=1e-6)}
    old_curve=pd.read_csv(OLD/'result/equity-daily.csv',index_col=0,parse_dates=True).equity
    new_curve=pd.read_csv(ROOT/'cases/CONTROL_TOP5/result/equity-daily.csv',index_col=0,parse_dates=True).equity
    curve_match=old_curve.index.equals(new_curve.index) and np.allclose(old_curve,new_curve,rtol=1e-10,atol=1e-6)
    atomic_json(ROOT/'baseline-reproduction.json',dict(status='PASS' if not diffs and curve_match else 'DIFFERENT',
        differences=diffs,every_daily_equity_equal=curve_match))
    if diffs or not curve_match:raise ValueError('Old economic witness differs; diagnose before attributing selection improvement')
    result=dict(status='PASS',cases=rows,old_20651_witness_reproduced=True,every_daily_equity_equal=True,
        identical_portfolio_configs=True,only_long_selection_count_changed=True,market_files_verified=market_files,
        SQL_writes=0,provider_calls=0,orders=0)
    atomic_json(ROOT/'validation-independent.json',result)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',validation='PASS'))
    return result


if __name__=='__main__':print(json.dumps(validate(),ensure_ascii=False))
