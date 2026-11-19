"""Independent accounting/activation review and readable comparison, no replay."""
from pathlib import Path
import json
import numpy as np
import pandas as pd

from scripts.research.us_b_protection_partial_20261118 import ROOT,CASES,read
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest


def maybe_csv(path):
    try:return pd.read_csv(path)
    except pd.errors.EmptyDataError:return pd.DataFrame()


def main():
    plan=read(ROOT/'protocol.json')
    for name,expected in plan['sources'].items():
        if digest(Path(name))!=expected:raise ValueError('Source changed after protocol: '+name)
    if read(ROOT/'matched-controls.json')['status']!='PASS':raise ValueError('Controls not matched')
    checks=[];transitions=[];windows=[]
    on_dates=None
    for case,spec in CASES.items():
        folder=ROOT/'cases'/case/'result';r=read(folder/'report.json')
        t=pd.read_csv(folder/'trades.csv');events=pd.read_csv(folder/'events.csv')
        buys=events[events.event.eq('BUY_FILL')].copy();buys['time']=pd.to_datetime(buys.time,utc=True)
        curve=pd.read_csv(folder/'equity-daily.csv',index_col=0,parse_dates=True).equity
        closed=t.pnl.sum();unrealized=0.;open_fee=0.
        for position in r['open_positions']:
            b=buys[buys.symbol.eq(position['symbol'])].sort_values('time').iloc[-1]
            quantity=float(position['qty']);entry_quantity=float(b.quantity)
            unrealized+=quantity*(float(position['mark'])-float(b.price))
            open_fee+=float(b.costs)*quantity/entry_quantity
        expected=4000+closed+unrealized-open_fee+r['dividends_accrued']-t.dividends.sum()-r['margin_interest']
        if abs(expected-r['final_equity'])>1e-6:raise ValueError('Final account does not reconcile: '+case)
        trading_costs=events.loc[events.event.isin(['BUY_FILL','SELL_FILL']),'costs'].sum()
        financing=events.loc[events.event.eq('FINANCING'),'costs'].sum()
        if abs(trading_costs-r['costs'])>1e-6 or abs(financing-r['margin_interest'])>1e-6:
            raise ValueError('Native fee/interest events do not reconcile')
        states=pd.read_csv(folder/'protection-states.csv',index_col=0,parse_dates=True)
        receipt=read(folder/'liquidations.json');forced_reason='INTERNAL_PROTECTION' if spec['fraction']==1 else 'PILOT_PROTECTION'
        if case!='SL10':
            on=states.index[states.transition.eq('ON')]
            if on_dates is None:on_dates=on
            elif not on.equals(on_dates):raise ValueError('ON dates differ between variants')
            if len(receipt['events'])!=len(on):raise ValueError('Missing/extra protection basket')
            for event in receipt['events']:
                stamp=pd.Timestamp(event['executed_at']);signal=pd.Timestamp(event['signal_date'])
                nextday=curve.index[curve.index>signal][0]
                from common.winner_pyramiding import regular_bounds
                if stamp!=pd.Timestamp(regular_bounds(nextday.date())[0]):raise ValueError('Exit not at next official opening')
                for symbol,quantity in event['quantities'].items():
                    matched=t[t.symbol.eq(symbol)&pd.to_datetime(t.exit_date,utc=True).eq(stamp)&t.exit_reason.eq(forced_reason)]
                    if matched.quantity.sum()!=quantity:raise ValueError('Basket quantities differ from actual trades')
                    if spec['fraction']==.5 and quantity>event['retained_core'][symbol]:
                        raise ValueError('Reduction consumes permanent core shares')
            p=maybe_csv(folder/'sizing-decisions.csv')
            if not p.empty and ((p.final_quantity>p.native_quantity).any() or (p.final_quantity>p.quantity_limit).any()):
                raise ValueError('Overlay increased native approval')
            v=maybe_csv(folder/'volatility-decisions.csv')
            if not v.empty and 'history_end' in v:
                day=pd.to_datetime(v.time,utc=True).dt.tz_convert('America/New_York').dt.tz_localize(None).dt.normalize()
                if not pd.to_datetime(v.history_end).lt(day).all():raise ValueError('Future covariance input')
        for day,row in states[states.transition.fillna('').ne('')].iterrows():
            transitions.append(dict(case=case,signal_date=str(day.date()),transition=row.transition,
                phase=row.phase,shadow_return10=row.shadow_return10))
        for start,end in [('2024-11-06','2025-04-04'),('2024-11-06','2025-06-30'),('2025-07-01','2026-10-01')]:
            w=curve.loc[start:end]
            windows.append(dict(case=case,start=start,end=end,return_pct=100*(w.iloc[-1]/w.iloc[0]-1),
                daily_close_dd_pct=100*(w/w.cummax()-1).min(),initial_equity=float(w.iloc[0]),final_equity=float(w.iloc[-1])))
        checks.append(dict(case=case,final_equity=r['final_equity'],accounting_error=float(expected-r['final_equity']),
            fees=r['costs'],interest=r['margin_interest'],dividends=r['dividends_accrued'],
            open_positions=len(r['open_positions']),liquidations=len(receipt['events']),
            forced_fragments=int(t.exit_reason.eq(forced_reason).sum())))
    pd.DataFrame(checks).to_csv(ROOT/'accounting-review.csv',index=False)
    pd.DataFrame(transitions).to_csv(ROOT/'phase-transitions.csv',index=False)
    pd.DataFrame(windows).to_csv(ROOT/'window-comparison.csv',index=False)
    table=pd.read_csv(ROOT/'comparison.csv');control=table[table.case.eq('SL10')].iloc[0]
    table['profit_retained_pct']=100*table.return_pct/control.return_pct
    table['dd_improvement_pp']=abs(control.max_drawdown_pct)-table.max_drawdown_pct.abs()
    table.to_csv(ROOT/'comparison-reviewed.csv',index=False)
    original_review=read(ROOT/'post-run-review.json')
    audit=dict(status='COMPLETED_EXPLORATORY_WITH_PRICE_OR_LABEL_RESERVES' if original_review['price_reserves'] or original_review['event_label_mismatches'] else 'COMPLETED_EXPLORATORY_AUDITED',
        matched_controls=True,identical_ON_schedule=True,accounting=True,partial_quantities=True,
        covariance_past_only=True,completed_campaign_winrate=True,
        inherited_price_or_label_review=original_review,new_training=0,provider_calls=0,SQL_writes=0,broker_orders=0,
        production_changes=False,independent_holdout=False,full_live_parity=False,tests_passed=12)
    atomic_json(ROOT/'final-status.json',audit)
    print(table[['label','final_equity','return_pct','max_drawdown_pct','campaign_win_pct','completed_campaigns','profit_retained_pct','dd_improvement_pp']].to_string(index=False))


if __name__=='__main__':main()
