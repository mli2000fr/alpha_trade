"""Scalar native SL3/TP7/TR3/open11 exits, cash, signal and metric checks."""
from datetime import date,timedelta
from pathlib import Path
import math
import numpy as np
import pandas as pd
from common.market_calendar import get_market_calendar
from scripts.research.us_winner_bottom_rank_filter_20261022 import read,digest,verify,save_new
from scripts.research.us_winner_bottom_rank_filter_audit_20261022 import event_cash


def near(a,b):
    if not math.isclose(float(a),float(b),abs_tol=1e-7,rel_tol=1e-10):raise AssertionError(f'{a} != {b}')


def scalar_exit(path,entry_time,entry,due,sl=.03,tp=.07,trail=.03):
    """Match documented phases, not the runtime/helper resolving implementation."""
    peak=float(entry);stop=round(entry*(1-sl),2);target=round(entry*(1+tp),2) if tp else None
    previous=None
    for b in path.itertuples():
        if b.bar_timestamp<entry_time:continue
        stamp=b.bar_timestamp
        # Prequeued deadline cancels protections before the opening auction.
        if stamp==due:return stamp,float(b.open),'HORIZON_OPEN'
        if b.open<=stop:return stamp,float(b.open),'STOP_GAP'
        if target is not None and b.open>=target:return stamp,target,'TP_GAP_CAPPED'
        # At a new bar only a previously completed high can tighten the stop.
        if previous is not None:
            peak=max(peak,float(previous.high))
            newstop=max(stop,round(peak*(1-trail),2)) if trail else stop
            if newstop>stop and b.open<=newstop:return stamp,float(b.open),'TIGHTENED_STOP_GAP'
            stop=newstop
        if b.low<=stop:return b.bar_end_timestamp,stop,'STOP'
        if target is not None and b.high>=target:return b.bar_end_timestamp,target,'TP'
        previous=b
        # End-of-session reconciliation observes the completed final high.
        nyend=b.bar_end_timestamp.tz_convert('America/New_York')
        next_same_session=False
        # Caller supplies session close for early-close days too.
        if hasattr(b,'session_close') and b.bar_end_timestamp==b.session_close:
            peak=max(peak,float(b.high));newstop=max(stop,round(peak*(1-trail),2)) if trail else stop
            if newstop>stop and b.close<=newstop:return b.bar_end_timestamp,float(b.close),'TIGHTENED_STOP_GAP'
            stop=newstop;previous=None
    return None


def audit(root):
    root=Path(root);p=read(root/'protocol.json');verify(p['sources'])
    report=read(root/'report.json');verify({str(root/k):v for k,v in report['files'].items()})
    parent=Path(p['parent']);snap=read(parent/'snapshot.json')
    raw={x['symbol']:pd.read_parquet(parent/x['file']) for x in snap['receipts']}
    cal=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    schedule=[s for s in cal.sessions(date(2024,12,15),date(2026,12,31)) if s.is_open]
    days=[s.session_date for s in schedule];indices={d:i for i,d in enumerate(days)}
    closes={pd.Timestamp(s.session_date):pd.Timestamp(s.close_at_utc) for s in schedule}
    for s,f in raw.items():f['session_close']=pd.to_datetime(f.trade_date).map(closes)
    qualified=pd.read_parquet(parent/'qualified-signals.parquet')
    rows=[];exit_checks=entry_checks=0
    for case in report['cases']:
        folder=root/f"{case['year']}-{case['arm']}";verify({str(folder/k):v for k,v in case['files'].items()})
        events=pd.read_csv(folder/'events.csv',low_memory=False);events=events[events.event.notna()]
        cash,fees,held=event_cash(events)
        near(cash,case['settled_cash']);near(fees,case['costs'])
        if held!={x['symbol']:x['qty'] for x in case['open_positions']}:raise AssertionError('End positions')
        near(case['final_equity'],cash+sum(x['qty']*x['mark'] for x in case['open_positions']))
        near(case['return_pct'],100*(case['final_equity']/4000-1))
        curve=pd.read_parquet(folder/'equity-5m.parquet');eq=np.r_[4000.,curve.equity.to_numpy()]
        near(case['max_drawdown_pct'],100*np.min(eq/np.maximum.accumulate(eq)-1))
        near(case['average_gross_capital'],curve.gross.mean())
        t=pd.read_parquet(folder/'trades.parquet');win_sessions=[];loss_sessions=[]
        for x in t.itertuples():
            f=raw[x.symbol];day=x.entry_date.tz_convert('America/New_York').date()
            due=pd.Timestamp(schedule[indices[day]+10].open_at_utc)
            result=scalar_exit(f[f.bar_timestamp.ge(x.entry_date)],x.entry_date,float(x.entry_price),due)
            if result is None:raise AssertionError('Closed trade has no scalar exit')
            stamp,price,reason=result
            if stamp!=x.exit_date or reason!=x.exit_reason:raise AssertionError(f'Scalar lifecycle {x.symbol}: {result} != {(x.exit_date,x.exit_price,x.exit_reason)}')
            near(price,x.exit_price);near(x.pnl,x.quantity*(x.exit_price-x.entry_price)-x.entry_fees-x.exit_fees+x.dividends)
            exit_checks+=1
            count=indices[x.exit_date.tz_convert('America/New_York').date()]-indices[day]+1
            (win_sessions if x.pnl>0 else loss_sessions).append(count)
        for b in events[events.event.eq('BUY_FILL')].itertuples():
            stamp=pd.Timestamp(b.time);day=stamp.tz_convert('America/New_York').date()
            f=raw[b.symbol];g=f[pd.to_datetime(f.trade_date).eq(pd.Timestamp(day))].reset_index(drop=True)
            found=np.flatnonzero(g.bar_timestamp.eq(stamp).to_numpy())
            if len(found)!=1 or found[0]<3:raise AssertionError('No completed entry confirmation')
            i=int(found[0]);prev=f[pd.to_datetime(f.trade_date).eq(pd.Timestamp(days[indices[day]-1]))]
            level=prev.high.max();c=g.close
            if not (c.iloc[i-3]<=level and c.iloc[i-2]>level and c.iloc[i-1]>level):raise AssertionError('False entry confirmation')
            near(b.price,g.open.iloc[i]);near(b.costs,b.price*b.quantity*.0008)
            eligible=qualified[qualified.year.eq(case['year'])&qualified.symbol.eq(b.symbol)&qualified.common_eligible&qualified.WINNER_ONLY]
            if not any(1<=indices[day]-indices[pd.Timestamp(d).date()]<=20 for d in eligible.date):raise AssertionError('No eligible source signal')
            entry_checks+=1
        near(int(t.pnl.gt(0).sum()),case['winners']);near(int(t.pnl.lt(0).sum()),case['losers'])
        row={k:v for k,v in case.items() if not isinstance(v,(dict,list))}
        row.update(average_winning_holding_sessions=float(np.mean(win_sessions)) if win_sessions else None,
            average_losing_holding_sessions=float(np.mean(loss_sessions)) if loss_sessions else None)
        rows.append(row)
    pd.DataFrame(rows).to_csv(root/'variant-metrics-audited.csv',index=False)
    save_new(root/'final-audit.json',dict(status='PASS_SCALAR_TP_SL_TRAILING_OPEN11_CASH_FEES_AND_SIGNALS',
        accounts=len(rows),actual_buy_checks=entry_checks,scalar_exit_checks=exit_checks,
        report_sha256=digest(root/'report.json'),auditor_sha256=digest(__file__),
        metrics_sha256=digest(root/'variant-metrics-audited.csv'),independent_human_review=False))
