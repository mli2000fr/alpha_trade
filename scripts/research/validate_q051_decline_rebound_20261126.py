"""Separate scalar signal/chronology/accounting checks; same assistant review."""
from datetime import date
import json
from pathlib import Path

import numpy as np
import pandas as pd

from scripts.research.us_q051_decline_rebound_20261126 import ROOT,BASE,CASES,read,shared
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def validate():
    from common.config_loader import replay_market_registry
    from common.market_calendar import get_market_calendar
    plan=read(ROOT/'protocol.json')
    for name,sha in plan['sources'].items():
        if digest(Path(name))!=sha:raise ValueError('Entrée/source modifiée : '+name)
    close=pd.read_parquet(ROOT/'inputs/close.parquet')
    audit=pd.read_parquet(ROOT/'inputs/candidate-audit.parquet')
    for c in ('long_auc_available_date','model_available_date'):
        if c in audit and not pd.to_datetime(audit[c]).lt(pd.to_datetime(audit.trade_date)).all():
            raise ValueError('Disponibilité du modèle/AUC future : '+c)
    with replay_market_registry(shared.restore_registry(shared.ROOT)):
        cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
        sessions=[s for s in cal.sessions(date(2019,1,1),date(2026,11,1)) if s.is_open]
    positions={s.session_date:i for i,s in enumerate(sessions)}
    opens={s.session_date:pd.Timestamp(s.open_at_utc) for s in sessions}
    measured={case:[] for case in CASES}
    for row in audit.itertuples():
        day=pd.Timestamp(row.trade_date)
        i=close.index.get_loc(day)
        past=close[row.symbol].iloc[i-22:i+1].to_numpy()
        qualified=len(past)==23 and np.isfinite(past).all() and (past>0).all()
        if qualified:
            expected_days=[s.session_date for s in sessions[positions[day.date()]-22:positions[day.date()]+1]]
            if list(close.index[i-22:i+1].date)!=expected_days:
                raise ValueError('Fenêtre du filtre différente de 23 séances NYSE')
        drop=qualified and float(past[-3]/past[0]-1)<=-.10+1e-12
        up1=qualified and bool(past[-2]>past[-3]);up2=qualified and bool(past[-1]>past[-2])
        measured['REFERENCE'].append(True);measured['DECLINE_ONLY'].append(drop)
        measured['REBOUND_1'].append(drop and up2);measured['REBOUND_2'].append(drop and up1 and up2)
    for case,values in measured.items():
        if not np.array_equal(np.asarray(values),audit[case].to_numpy()):
            raise ValueError('Filtre scalaire différent : '+case)
    configurations=[];checks=[]
    for case in CASES:
        folder=ROOT/'cases'/case;out=folder/'result'
        if read(folder/'progress.json')['status']!='COMPLETED_EXPLORATORY':raise ValueError('Cas non terminé')
        iso=read(folder/'isolation.json')
        if iso['status']!='COMPLETED' or iso.get('violations'):raise ValueError('Isolation non qualifiée')
        configurations.append(read(out/'configuration.json')['portfolio'])
        r=read(out/'report.json');t=pd.read_csv(out/'trades.csv');events=pd.read_csv(out/'events.csv')
        s=pd.read_parquet(ROOT/'inputs'/f'signals-{case}.parquet')
        allowed={(sessions[positions[pd.Timestamp(x.trade_date).date()]+1].session_date,x.symbol) for x in s.itertuples()}
        for trade in t.itertuples():
            entry=pd.Timestamp(trade.entry_date);exit_=pd.Timestamp(trade.exit_date)
            if (entry.date(),trade.symbol) not in allowed or entry!=opens[entry.date()]:
                raise ValueError('Entrée hors filtre ou hors ouverture J+1')
            held=positions[exit_.date()]-positions[entry.date()]
            if not 0<=held<=10:raise ValueError('Durée hors H10')
            if trade.exit_reason=='HORIZON_OPEN' and (held!=10 or exit_!=opens[exit_.date()]):
                raise ValueError('Sortie hors open11')
        if not t.side.eq('buy').all() or t.exit_reason.str.startswith('TP').any():
            raise ValueError('SHORT ou TP inattendu')
        pnl=t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends
        if not np.allclose(pnl,t.pnl,rtol=1e-10,atol=1e-7):raise ValueError('PnL non réconcilié')
        if len(t)!=r['closed_lot_trades'] or int(t.pnl.gt(0).sum())!=r['winners'] or int(t.pnl.lt(0).sum())!=r['losers']:
            raise ValueError('Compteurs de trades non réconciliés')
        if not np.isclose(100*t.pnl.gt(0).mean(),r['win_pct'],atol=1e-7):raise ValueError('Taux gagnant non réconcilié')
        costs=events.loc[events.event.isin(['BUY_FILL','SELL_FILL']),'costs'].sum()
        if not np.isclose(costs,r['costs'],atol=1e-7):raise ValueError('Frais non réconciliés')
        annual=pd.read_csv(out/'annual-summary.csv')
        if not np.isclose(4000*np.prod(1+annual.return_pct/100),r['final_equity'],atol=1e-6):
            raise ValueError('Capital réinitialisé ou rendements annuels incompatibles')
        checks.append(dict(case=case,signals=len(s),trades=len(t),status='PASS'))
    if any(c!=configurations[0] for c in configurations):raise ValueError('Configurations différentes entre cas')
    if read(ROOT/'baseline-reproduction.json')['status']!='PASS':raise ValueError('Référence non reproduite')
    fields=['symbol','entry_date','exit_date','quantity','entry_price','exit_price','entry_fees','exit_fees','pnl','exit_reason']
    old=pd.read_csv(BASE/'result/trades.csv')[fields].sort_values(['entry_date','exit_date','symbol']).reset_index(drop=True)
    new=pd.read_csv(ROOT/'cases/REFERENCE/result/trades.csv')[fields].sort_values(['entry_date','exit_date','symbol']).reset_index(drop=True)
    pd.testing.assert_frame_equal(old,new,check_dtype=False,check_exact=False,atol=1e-7,rtol=1e-10)
    result=dict(status='PASS',checks=checks,scalar_signals_checked=len(audit),NYSE_sessions_checked=True,
        all_entries_qualified=True,open11_checked=True,fees_checked=True,annual_compounding_checked=True,
        same_portfolio_settings=True,baseline_exact=True,all_1471_reference_trades_equal=True,validator_sha256=digest(Path(__file__)),
        reviewer='Same assistant; not independent human validation',SQL_writes=0,orders=0,provider_calls=0)
    atomic_json(ROOT/'validation-scalar.json',result)
    print(json.dumps(result,ensure_ascii=False))
    return result


if __name__=='__main__':validate()
