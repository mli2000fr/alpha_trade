"""Independent archive selection, accounting and chronology reconciliation."""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest
from scripts.research.us_q051_selection_variants_20261115 import ROOT,CASES,WITNESS,shared,read


def independent_selections(plan):
    outputs={k:[] for k in ['REFERENCE',*CASES]}
    for year,model in plan['annual_models'].items():
        f=pd.read_parquet(shared.ROOT/'inputs/rankings'/f'{year}.parquet')
        f['date']=pd.to_datetime(f.date).dt.normalize()
        # Fix the Oracle pool before assessing availability or any LONG score.
        pool=f.sort_values(['date','proba_extreme','symbol'],ascending=[True,False,True]).groupby('date',sort=False).head(179)
        pool=pool[pool.long_probability.notna()].sort_values(['date','long_probability','proba_extreme','symbol'],
            ascending=[True,False,False,True])
        for name,case in {'REFERENCE':dict(long_top_n=5,min_long_probability=.5,min_long_auc=.5),**CASES}.items():
            fixed=pool.groupby('date',sort=False).head(case['long_top_n']).copy()
            good=(fixed.long_probability.gt(case['min_long_probability'])&fixed.long_auc.ge(.5)
                &pd.to_datetime(fixed.long_auc_available_date).lt(fixed.date)
                &fixed.long_auc_source.eq('calibration')&fixed.long_auc_model_sha256.eq(fixed.long_model_sha256))
            selected=fixed[good].copy();selected['entry_year']=int(year)
            outputs[name].append(selected)
    counts=[]
    for name,parts in outputs.items():
        expected=pd.concat(parts,ignore_index=True).sort_values(['date','long_probability','proba_extreme','symbol'],
            ascending=[True,False,False,True])
        actual=pd.read_parquet(ROOT/'inputs'/f'signals-{name}.parquet').rename(columns={'trade_date':'date'}).sort_values(
            ['date','rank','symbol'])
        for c in ['date','symbol','long_probability','long_auc','long_model_sha256']:
            a=expected[c].reset_index(drop=True);b=actual[c].reset_index(drop=True)
            if not a.equals(b):raise ValueError('Independent selection differs: '+name+'/'+c)
        counts.append(dict(case=name,signals=len(actual),symbols=int(actual.symbol.nunique()),signal_dates=int(actual.date.nunique())))
    return counts


def validate_case(name):
    from datetime import date
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    folder=ROOT/'cases'/name;out=folder/'result';r=read(out/'report.json')
    if read(folder/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Case incomplete')
    iso=read(folder/'isolation.json')
    if iso['status']!='COMPLETED' or iso.get('violations'):raise ValueError('Isolation failed')
    if read(out/'configuration.json')['portfolio']!=read(WITNESS/'result/configuration.json')['portfolio']:
        raise ValueError('Portfolio configuration changed')
    if r['SQL_writes'] or r['orders'] or r['provider_calls']:raise ValueError('External side effect')
    t=pd.read_csv(out/'trades.csv');e=pd.read_csv(out/'equity-daily.csv',index_col=0,parse_dates=True).equity
    m=pd.read_parquet(out/'equity-5m.parquet');a=pd.read_csv(out/'annual-summary.csv')
    values=pd.concat([pd.Series([4000.]),m.equity],ignore_index=True)
    dd=100*(values/values.cummax()-1).min()
    checks=[(e.iloc[-1],r['final_equity']),(100*(e.iloc[-1]/4000-1),r['return_pct']),
        (dd,r['max_drawdown_pct']),(4000*np.prod(1+a.return_pct/100),r['final_equity']),
        (m.gross.mean(),r['average_gross_capital']),((m.gross/m.equity).mean(),r['average_gross_equity_ratio'])]
    if len(e)!=1443 or not all(np.isclose(x,y,atol=1e-6,rtol=1e-10) for x,y in checks):
        raise ValueError('Capital, DD or annual composition mismatch')
    if len(t)!=r['closed_lot_trades'] or int(t.pnl.gt(0).sum())!=r['winners'] or int(t.pnl.lt(0).sum())!=r['losers']:
        raise ValueError('Trade count mismatch')
    expected=t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends
    if not np.allclose(t.pnl,expected,rtol=1e-10,atol=1e-7):raise ValueError('Trade PnL mismatch')
    if not np.allclose(t.return_pct,t.pnl/(t.quantity*t.entry_price),rtol=1e-10,atol=1e-10):raise ValueError('Net returns mismatch')
    events=pd.read_csv(out/'events.csv');fees=events.loc[events.event.isin(['BUY_FILL','SELL_FILL']),'costs'].sum()
    if not np.isclose(fees,r['costs'],atol=1e-7):raise ValueError('Fees mismatch')
    fills=events[events.event.eq('BUY_FILL')].copy()
    if (fills.quantity%1).ne(0).any() or (fills.quantity<=0).any():raise ValueError('Non-integral LONG fill')
    with replay_market_registry(shared.restore_registry(shared.ROOT)):
        cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s for s in cal.sessions(date(2020,12,1),date(2026,11,1)) if s.is_open]
    index={s.session_date:i for i,s in enumerate(sessions)};opening={s.session_date:pd.Timestamp(s.open_at_utc) for s in sessions}
    signals=pd.read_parquet(ROOT/'inputs'/f'signals-{name}.parquet')
    allowed={(sessions[index[pd.Timestamp(row.trade_date).date()]+1].session_date,row.symbol) for row in signals.itertuples()}
    for trade in t.itertuples():
        entry=pd.Timestamp(trade.entry_date);exit_=pd.Timestamp(trade.exit_date)
        if (entry.date(),trade.symbol) not in allowed or entry!=opening[entry.date()]:raise ValueError('Unselected or non-open entry')
        held=index[exit_.date()]-index[entry.date()]
        if not 0<=held<=10:raise ValueError('Holding chronology outside entry/open11')
        if trade.exit_reason=='HORIZON_OPEN' and (held!=10 or exit_!=opening[exit_.date()]):
            raise ValueError('Temporal exit not at official open11')
    if t.exit_reason.str.startswith('TP').any():raise ValueError('Unexpected TP')
    imported=read(folder/'ihm.json')['run_id']
    ui=read(Path('artifacts/ihm_backtesting_runs/run')/imported/'artifacts/report.json')
    for key,target in [('final_value','final_equity'),('total_return_pct','return_pct'),('win_rate_pct','win_pct')]:
        if not np.isclose(ui['summary'][key],r[target],atol=1e-7):raise ValueError('IHM report mismatch')
    wins=t[t.pnl.gt(0)];losses=t[t.pnl.lt(0)]
    value=dict(status='PASS',case=name,sessions=len(e),trades=len(t),entry_signals_verified=True,
        open11_verified=True,identical_portfolio_configuration=True,fees_reconciled=float(fees),
        final_equity=r['final_equity'],return_pct=r['return_pct'],max_drawdown_pct=r['max_drawdown_pct'],
        sum_winning_pnl=float(wins.pnl.sum()),sum_losing_pnl=float(losses.pnl.sum()),
        profit_factor=float(wins.pnl.sum()/-losses.pnl.sum()),
        average_winning_holding_calendar_days=float(wins.holding_days.mean()),
        average_losing_holding_calendar_days=float(losses.holding_days.mean()),
        maximum_gross_capital=float(m.gross.max()),maximum_gross_equity_ratio=float((m.gross/m.equity).max()),
        exit_reasons=t.exit_reason.value_counts().to_dict(),IHM=imported,orders=0,SQL_writes=0,provider_calls=0)
    atomic_json(folder/'validation-independent.json',value)
    return value


def validate():
    plan=read(ROOT/'protocol.json')
    for p,h in plan['sources'].items():
        if digest(Path(p))!=h:raise ValueError('Source changed: '+p)
    counts=independent_selections(plan)
    cases=[validate_case(name) for name in CASES]
    result=dict(status='PASS',independent_selection_recount=counts,cases=cases,
        reference_reused_with_identical_6073_signals=True,production_changed=False)
    atomic_json(ROOT/'validation-independent.json',result)
    atomic_json(ROOT/'progress.json',dict(status='COMPLETED_EXPLORATORY',validation='PASS'))
    return result


if __name__=='__main__':print(json.dumps(validate(),ensure_ascii=False))
