"""Separate scalar exits and vector cash/valuation reconstruction, offline."""
import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json


def scalar_exit(path,entry,expiry,c,maintenance=None):
    """No calls to the native engine, core.direction or its exit resolver."""
    sign=1 if c['side']=='buy' else -1
    entry_price=float(path.open.iloc[entry])
    initial=round(entry_price*(1-sign*c['sl']),4)
    extreme=entry_price
    for i,r in enumerate(path.iloc[entry:].itertuples(),start=entry):
        stop=initial
        if c['trailing'] is not None:
            tr=round(extreme*(1-sign*c['trailing']),4)
            stop=max(stop,tr) if sign==1 else min(stop,tr)
        target=round(entry_price*(1+sign*c['tp']),4) if c['tp'] is not None else None
        if maintenance is not None and r.bar_timestamp==maintenance:
            return i,float(r.open),'OPEN'
        if (r.open<=stop if sign==1 else r.open>=stop):return i,float(r.open),'OPEN'
        if target is not None and (r.open>=target if sign==1 else r.open<=target):return i,float(target),'OPEN'
        if r.bar_timestamp>=expiry:return i,float(r.open),'OPEN'
        # Conservative ambiguity: stop precedes target; high cannot tighten same-bar stop.
        if (r.low<=stop if sign==1 else r.high>=stop):return i,float(stop),'INTRABAR'
        if target is not None and (r.high>=target if sign==1 else r.low<=target):return i,float(target),'INTRABAR'
        extreme=max(extreme,r.high) if sign==1 else min(extreme,r.low)
    return None


def audit_case(out,c,tape):
    import json
    trades=pd.read_parquet(out/'trades.parquet')
    marks=pd.read_parquet(out/'marks.parquet')
    opened=json.loads((out/'open-positions.json').read_text(encoding='utf-8'))
    maintenance=json.loads((out/'maintenance.json').read_text(encoding='utf-8'))
    n=len(marks);cash_delta=np.zeros(n);value=np.zeros(n);gross=np.zeros(n)
    days=pd.DatetimeIndex(tape['calendar'].date)
    ts_to_index={ts:i for i,(ts,d,last) in enumerate(tape['timeline'])}
    close_by_symbol={}
    signed=1 if c['side']=='buy' else -1
    max_error=0.;fee=.0008
    records=trades.to_dict('records')+opened
    spans={}
    # Cache plain numpy marks rather than rebuilding DataFrames for each trade.
    for r in records:
        s=r['symbol']
        if s not in close_by_symbol:
            close_by_symbol[s]=np.array([b.get(s,(np.nan,)*4)[3] for b in tape['bars']],dtype=float)
        entry=int(r['entry_bar']);closed='exit_bar' in r
        end=int(r['exit_bar']) if closed else n
        if not 0<=entry<=end<=n:raise ValueError('Invalid holding bounds')
        for a,b in spans.setdefault(s,[]):
            if max(a,entry)<min(b,end):raise ValueError('Duplicate held symbol')
        spans[s].append((entry,end))
        q=float(r['qty']);p=float(r['entry_price']);pid=int(r['pair_id'])
        source=tape['paths'][pid]
        yearpath=source[source.bar_timestamp.dt.tz_convert('America/New_York').dt.year.eq(c['year'])].reset_index(drop=True)
        start=np.flatnonzero(yearpath.bar_timestamp.eq(pd.Timestamp(r['entry_timestamp'])))
        if len(start)!=1 or not np.isclose(p,yearpath.open.iloc[start[0]],atol=1e-10):raise ValueError('Uncausal entry price')
        expiry=pd.Timestamp(r['expiry'])
        maint=pd.Timestamp(r['exit_timestamp']) if closed and r['exit_reason']=='MAINTENANCE_NEXT_OPEN' else None
        if maint is not None:
            day=pd.Timestamp(maint.tz_convert('America/New_York').date())
            di=days.get_loc(day)
            if not di or not maintenance[di-1]['breach'] or maint!=tape['calendar'].set_index('date').at[day,'market_open']:
                raise ValueError('Unjustified margin liquidation')
        expected_exit=scalar_exit(yearpath,int(start[0]),expiry,c,maint)
        if closed:
            if expected_exit is None:raise ValueError('Exit not found')
            j,px,phase=expected_exit
            if (ts_to_index[yearpath.bar_timestamp.iloc[j]]!=end or phase!=r['exit_phase']
                or not np.isclose(px,r['exit_price'],atol=1e-8,rtol=1e-12)):
                raise ValueError(f"Different scalar exit: {s}/{pid}")
        elif expected_exit is not None:raise ValueError('Unclosed position already hit an exit')
        cash_delta[entry]+=-signed*q*p-q*p*fee
        prices=close_by_symbol[s][entry:end]
        if not np.isfinite(prices).all():raise ValueError('Missing held valuation')
        value[entry:end]+=signed*q*prices
        gross[entry:end]+=q*prices
        if closed:
            exitday=pd.Timestamp(r['exit_date']);entryday=pd.Timestamp(r['entry_date'])
            duration=days.get_loc(exitday)-days.get_loc(entryday)
            borrow=q*p*.003*duration/252 if signed==-1 else 0.
            pnl=signed*q*(float(r['exit_price'])-p)-fee*q*(p+float(r['exit_price']))-borrow
            if not np.isclose(pnl,r['pnl'],atol=1e-7) or not np.isclose(borrow,r['borrow_cost'],atol=1e-8):
                raise ValueError('Trade fee/borrow/PnL mismatch')
            if r['holding_sessions']!=duration+1:raise ValueError('Holding session count mismatch')
            cash_delta[end]+=signed*q*r['exit_price']-q*r['exit_price']*fee-borrow
        else:
            duration=days.get_loc(days[-1])-days.get_loc(pd.Timestamp(r['entry_timestamp']).tz_convert('America/New_York').normalize().tz_localize(None))
            borrow=q*p*.003*duration/252 if signed==-1 else 0.
            cash_delta[-1]-=borrow
    cash=4000+np.cumsum(cash_delta)
    charges={pd.Timestamp(r['date']):float(r['interest']) for r in maintenance}
    cumulative_interest=0.
    for i,(ts,day,last) in enumerate(tape['timeline']):
        if last:
            j=days.get_loc(day)
            boundary=days[j+1] if j+1<len(days) else day+pd.Timedelta(days=1)
            # Last-mark loan accrual is separate from the EOD debit financing base.
            pending=sum(r.get('borrow_accrued_usd',0.) for r in opened) if i==n-1 else 0.
            expected=max(-(cash[i]-cumulative_interest+pending),0.)*.065*(boundary-day).days/360
            if not np.isclose(expected,charges[day],atol=1e-7):raise ValueError('ACT/360 interest mismatch')
            cumulative_interest+=expected
        cash[i]-=cumulative_interest
    for label,actual,expected in [('cash',marks.cash.to_numpy(),cash),
                                 ('gross',marks.gross.to_numpy(),gross),
                                 ('equity',marks.equity.to_numpy(),cash+value)]:
        err=float(np.max(np.abs(actual-expected)));max_error=max(max_error,err)
        if err>1e-6:raise ValueError(f'{label} reconstruction mismatch: {err}')
    audit=dict(status='PASS_SCALAR_EXITS_AND_CASH',closed_trades=len(trades),open_positions=len(opened),
        marks=n,max_absolute_reconstruction_error_usd=max_error,independent_human_review=False)
    atomic_json(out/'audit.json',audit)
    return audit
