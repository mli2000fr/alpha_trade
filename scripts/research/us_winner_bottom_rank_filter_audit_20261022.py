"""Independent signal, shared cash, fee, chronology and result audit of Winner veto."""
from collections import defaultdict
from pathlib import Path
from datetime import date,timedelta
import math
import pandas as pd
import numpy as np
from common.market_calendar import get_market_calendar
from scripts.research.us_winner_bottom_rank_filter_20261022 import read,digest,verify,save_new,ARMS,INITIAL

ROOT=Path('artifacts/research/us_winner_bottom_rank_filter/20261022-v2')


def close(a,b,label):
    if not math.isclose(float(a),float(b),abs_tol=1e-7,rel_tol=1e-10):
        raise AssertionError(f'{label}: {a} != {b}')


def event_cash(events):
    cash=INITIAL;fees=0.;positions=defaultdict(float);buy_price={}
    for r in events.itertuples():
        kind=getattr(r,'event',None)
        if kind=='BUY_FILL':
            if positions[r.symbol]:raise AssertionError('Repeated buy of held symbol')
            if not float(r.quantity).is_integer():raise AssertionError('Fractional fill')
            cash-=r.quantity*r.price+r.costs;fees+=r.costs;positions[r.symbol]+=r.quantity
            buy_price[r.symbol]=r.price
        elif kind=='SELL_FILL':
            if r.quantity>positions[r.symbol]:raise AssertionError('Oversell')
            cash+=r.quantity*r.price-r.costs;fees+=r.costs;positions[r.symbol]-=r.quantity
        elif kind=='FINANCING':cash-=r.costs
    return cash,fees,{s:q for s,q in positions.items() if q}


def run(root=ROOT):
    p=read(root/'protocol.json');verify(p['sources'])
    r=read(root/'report.json')
    verify({str(root/k):v for k,v in r['files'].items()})
    snap=read(root/'snapshot.json');verify({str(root/k):v for k,v in snap['files'].items()})
    signals=pd.read_parquet(root/'frozen-signals.parquet')
    qualified=pd.read_parquet(root/'qualified-signals.parquet')
    for (year,day),g in signals.groupby(['year','date']):
        ranked=sorted(g.itertuples(),key=lambda x:(x.vol_ratio_20_60 if x.aux_known else math.inf,x.oracle_rank,x.symbol))
        for rank,row in enumerate(ranked,1):
            if row.estimated_trend_rank!=rank:raise AssertionError('Frozen score ranking mismatch')
            for arm,n in ARMS.items():
                if getattr(row,arm)!=bool(row.aux_known and rank<=n):raise AssertionError('Veto uses wrong side or rank')
    if len(qualified)!=len(signals):raise AssertionError('Candidate population lost')
    if any(x['status']!='COMPLETED_EXPLORATORY' for x in r['cases']):
        raise ValueError('Some accounts failed/incomplete; no complete financial verdict')
    raw={};calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    for item in snap['receipts']:
        raw[item['symbol']]=pd.read_parquet(root/item['file'])
    rows=[];fill_checks=0;horizon_checks=0
    for case in r['cases']:
        folder=root/f"{case['year']}-{case['arm']}"
        verify({str(folder/k):v for k,v in case['files'].items()})
        events=pd.read_csv(folder/'events.csv',low_memory=False)
        events=events[events.event.notna()].copy()
        cash,fees,held=event_cash(events)
        close(cash,case['settled_cash'],'cash');close(fees,case['costs'],'fees')
        if case['dividends_accrued'] or case['dividends_receivable'] or case['unsettled_cash']:
            raise AssertionError('Reserved CA/settlement convention unexpectedly active')
        actual={x['symbol']:x['qty'] for x in case['open_positions']}
        if held!=actual:raise AssertionError('Final positions differ from cash flows')
        gross=sum(x['qty']*x['mark'] for x in case['open_positions'])
        close(gross,case['gross'],'gross');close(cash+gross,case['final_equity'],'final equity')
        close(100*(case['final_equity']/INITIAL-1),case['return_pct'],'annual return')
        curve=pd.read_parquet(folder/'equity-5m.parquet')
        values=np.r_[INITIAL,curve.equity.to_numpy(float)]
        close(100*np.min(values/np.maximum.accumulate(values)-1),case['max_drawdown_pct'],'DD')
        close(curve.gross.mean(),case['average_gross_capital'],'capital average')
        trades=pd.read_parquet(folder/'trades.parquet')
        returns=[];sessions=[]
        if not trades.empty:
            for t in trades.itertuples():
                pnl=t.quantity*(t.exit_price-t.entry_price)-t.entry_fees-t.exit_fees+t.dividends
                close(pnl,t.pnl,'trade pnl');close(pnl/(t.quantity*t.entry_price),t.return_pct,'unit return')
                entry=pd.Timestamp(t.entry_date).tz_convert('America/New_York').date()
                exit_day=pd.Timestamp(t.exit_date).tz_convert('America/New_York').date()
                sessions.append(sum(x.is_open for x in calendar.sessions(entry,exit_day)))
                returns.append(100*t.return_pct)
                if t.exit_reason=='HORIZON_OPEN':
                    official=[x for x in calendar.sessions(entry,entry+timedelta(days=100)) if x.is_open]
                    if pd.Timestamp(t.exit_date)!=pd.Timestamp(official[20].open_at_utc):raise AssertionError('Horizon is not 21st holding-session open')
                    horizon_checks+=1
        # Verify every actual buy uses a retained signal and the fresh two-close rule.
        for event in events[events.event.eq('BUY_FILL')].itertuples():
            stamp=pd.Timestamp(event.time);day=stamp.tz_convert('America/New_York').date()
            f=raw[event.symbol];current=f[f.trade_date.eq(pd.Timestamp(day))].reset_index(drop=True)
            start=pd.to_datetime(current.bar_timestamp,utc=True)
            i=np.flatnonzero(start.eq(stamp).to_numpy())
            if len(i)!=1 or i[0]<3:raise AssertionError('Buy precedes completed confirmation')
            k=int(i[0]);prior=calendar.previous_session(day)
            prev=f[f.trade_date.eq(pd.Timestamp(prior))]
            threshold=float(prev.high.max());cl=current.close.to_numpy(float)
            if not (cl[k-3]<=threshold and cl[k-2]>threshold and cl[k-1]>threshold):raise AssertionError('Buy without fresh two-close breakout')
            close(event.price,float(current.open.iloc[k]),'actual raw open fill')
            eligible=qualified[(qualified.year==case['year'])&qualified.symbol.eq(event.symbol)
                &qualified.common_eligible&qualified[case['arm']]]
            valid=False
            for signal in eligible.date:
                official=[x.session_date for x in calendar.sessions(signal.date(),day) if x.is_open]
                if len(official)>=2 and len(official)<=21 and official[-1]==day:
                    valid=True;break
            if not valid:raise AssertionError('Buy has no retained unexpired source signal')
            fill_checks+=1
        pnl=trades.pnl if not trades.empty else pd.Series(dtype=float)
        wins=pnl.gt(0).to_numpy();losses=pnl.lt(0).to_numpy()
        if int(wins.sum())!=case['winners'] or int(losses.sum())!=case['losers']:raise AssertionError('Win/loss counts')
        row={k:v for k,v in case.items() if not isinstance(v,(list,dict))}
        row.update(average_winning_return_pct=float(np.mean(np.array(returns)[wins])) if wins.any() else None,
            average_losing_return_pct=float(np.mean(np.array(returns)[losses])) if losses.any() else None,
            average_winning_holding_sessions=float(np.mean(np.array(sessions)[wins])) if wins.any() else None,
            average_losing_holding_sessions=float(np.mean(np.array(sessions)[losses])) if losses.any() else None,
            cash_reconciliation_error=abs(cash-case['settled_cash']))
        rows.append(row)
    enriched=pd.DataFrame(rows)
    baseline=enriched[enriched.arm.eq('WINNER_ONLY')].set_index('year')
    enriched['return_delta_vs_winner_pp']=[x.return_pct-baseline.loc[x.year,'return_pct'] for x in enriched.itertuples()]
    enriched.to_csv(root/'annual-metrics-audited.csv',index=False)
    result=dict(status='PASS_RETAINED_SIGNALS_FRESH_BREAKOUT_SHARED_CASH_FEES_AND_HORIZON',accounts=len(rows),
        actual_buy_checks=fill_checks,horizon_checks=horizon_checks,independent_human_review=False,
        report_sha256=digest(root/'report.json'),auditor_sha256=digest(__file__),
        annual_metrics_sha256=digest(root/'annual-metrics-audited.csv'))
    save_new(root/'final-audit.json',result)
    return result


if __name__=='__main__':print(run())
