"""Post-run exposure and recovery diagnostics; no strategy changes."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

from scripts.research.us_b_protection_partial_20261118 import ROOT as PRIMARY,CASES,read
from scripts.research.us_b_protection_timing_replay_20261118 import ROOT,CASE


def main():
    reference=pd.read_csv(PRIMARY/'cases/SL10/result/equity-daily.csv',index_col=0,parse_dates=True).equity
    exposures=[];recoveries=[];checks=[]
    for root,case in [(PRIMARY,key) for key in CASES]+[(ROOT,CASE)]:
        folder=root/'cases'/case/'result';report=read(folder/'report.json')
        curve=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity
        events=pd.read_csv(folder/'events.csv');flows=events[events.event.isin(['BUY_FILL','SELL_FILL'])].copy()
        flows['day']=pd.to_datetime(flows.time,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        flows['delta']=flows.quantity*np.where(flows.event.eq('BUY_FILL'),1,-1)
        changes=flows.pivot_table(index='day',columns='symbol',values='delta',aggfunc='sum',fill_value=0)
        positions=changes.reindex(curve.index,fill_value=0).cumsum()
        if positions.lt(-1e-7).any().any():raise ValueError('Oversold position in event ledger')
        observed={s:int(q) for s,q in positions.iloc[-1].items() if q>0}
        expected={p['symbol']:int(p['qty']) for p in report['open_positions']}
        if observed!=expected:raise ValueError('Ending event holdings do not reconcile')
        count=positions.gt(0).sum(axis=1)
        if count.max()>20:raise ValueError('More than20 held stocks')
        states=pd.read_csv(folder/'protection-states.csv',index_col=0,parse_dates=True)
        marks=pd.read_parquet(folder/'equity-5m.parquet')
        marks['day']=pd.to_datetime(marks.timestamp,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
        index=states.index.searchsorted(pd.DatetimeIndex(marks.day),side='left')-1
        if (index<0).any():raise ValueError('Missing causal exposure phase')
        marks['phase']=states.phase.to_numpy()[index]
        marks['exposure']=marks.gross/marks.equity
        for phase,g in marks.groupby('phase'):
            days=pd.DatetimeIndex(g.day.unique())
            exposures.append(dict(case=case,phase=phase,marks=len(g),sessions=len(days),
                average_exposure_pct=float(100*g.exposure.mean()),average_gross=float(g.gross.mean()),
                mean_held_stocks=float(count.reindex(days).mean()),maximum_held_stocks=int(count.reindex(days).max())))
        for day,row in states[states.transition.fillna('').eq('OFF')].iterrows():
            future=curve.index[curve.index>day][:10]
            if len(future)<10 or day not in curve.index:continue
            g=marks[marks.day.isin(future)]
            recoveries.append(dict(case=case,signal_date=str(day.date()),
                return10_pct=float(100*(curve.loc[future[-1]]/curve.loc[day]-1)),
                reference_return10_pct=float(100*(reference.loc[future[-1]]/reference.loc[day]-1)),
                mean_exposure10_pct=float(100*g.exposure.mean()),mean_held_stocks10=float(count.loc[future].mean())))
        first_on=states.index[states.transition.eq('ON')]
        before=curve.loc[:first_on[0]] if len(first_on) else curve
        if not np.allclose(before,reference.reindex(before.index),atol=1e-8,rtol=0):
            raise ValueError('Capital diverged before first actionable protection')
        checks.append(dict(case=case,ending_holdings_reconciled=True,no_oversell=True,
            max_positions=int(count.max()),identical_before_first_ON=True,
            first_ON=str(first_on[0].date()) if len(first_on) else None))
    pd.DataFrame(exposures).to_csv(ROOT/'phase-exposure-all.csv',index=False)
    pd.DataFrame(recoveries).to_csv(ROOT/'off-recovery-all.csv',index=False)
    (ROOT/'exposure-validation.json').write_text(json.dumps(dict(status='PASS',checks=checks,
        scope='Actual total exposure;50%per-position partition is not a50%account exposure ceiling'),indent=2),encoding='utf-8')
    print(pd.DataFrame(exposures).to_string(index=False))


if __name__=='__main__':main()
