"""Independent cash/exit reconstruction plus actual-production risk trace replay."""
import numpy as np
import pandas as pd

from backtesting.production_risk_replay import ProductionRiskController
from scripts.research.us_concentrated_historical_tapes import atomic_json
from scripts.research.us_intraday_protection_grid import READ
from scripts.research.us_intraday_protection_grid_audit import scalar_exit


def audit_case(out,c,tape):
    trades=pd.read_parquet(out/'trades.parquet')
    marks=pd.read_parquet(out/'marks.parquet')
    opened=READ(out/'open-positions.json');maintenance=READ(out/'maintenance.json')
    events=READ(out/'production-risk-events.json')
    root=out.parent.parent;profile=READ(root/'production-risk.json')
    contexts={r.date:r for r in pd.read_parquet(root/'risk-regimes.parquet').itertuples()}
    days=pd.DatetimeIndex(tape['calendar'].date)
    schedule=tape['calendar'].set_index('date')
    n=len(marks);cash_delta=np.zeros(n);value=np.zeros(n);gross=np.zeros(n)
    natural_open_flows=np.zeros(n)
    clock={ts:i for i,(ts,day,last) in enumerate(tape['timeline'])}
    caches={};spans={};sign=1 if c['side']=='buy' else -1
    records=trades.to_dict('records')+opened
    forced={}
    for e in events:
        for s in e['forced_symbols']:forced[(s,int(e['bar_number']))]=e
    verified_forced=0
    for r in records:
        s=r['symbol'];entry=int(r['entry_bar']);closed='exit_bar' in r
        end=int(r['exit_bar']) if closed else n
        if not 0<=entry<=end<=n:raise ValueError('Invalid position span')
        for a,b in spans.setdefault(s,[]):
            if max(a,entry)<min(b,end):raise ValueError('Overlapping same-symbol positions')
        spans[s].append((entry,end))
        if s not in caches:caches[s]=np.array([b.get(s,(np.nan,)*4)[3] for b in tape['bars']],dtype=float)
        q=float(r['qty']);p=float(r['entry_price'])
        source=tape['paths'][int(r['pair_id'])]
        path=source[source.bar_timestamp.dt.tz_convert('America/New_York').dt.year.eq(c['year'])].reset_index(drop=True)
        match=np.flatnonzero(path.bar_timestamp.eq(pd.Timestamp(r['entry_timestamp'])))
        if len(match)!=1 or not np.isclose(p,path.open.iloc[match[0]],atol=1e-10):raise ValueError('Entry price/time mismatch')
        mandatory=None
        if closed and r['exit_reason'] in ('MAINTENANCE_NEXT_OPEN','PRODUCTION_BREAKER_FORCE'):
            mandatory=pd.Timestamp(r['exit_timestamp'])
            day=pd.Timestamp(mandatory.tz_convert('America/New_York').date())
            if mandatory!=schedule.at[day,'market_open']:raise ValueError('Non-opening forced exit')
            if r['exit_reason']=='PRODUCTION_BREAKER_FORCE':
                if (s,end) not in forced:raise ValueError('Forced exit not approved by risk event')
                verified_forced+=1
            else:
                di=days.get_loc(day)
                if not di or not maintenance[di-1]['breach']:raise ValueError('Unjustified maintenance exit')
            natural=scalar_exit(path,int(match[0]),pd.Timestamp(r['expiry']),c)
            if natural is not None:
                ni,nprice,nphase=natural;actual_i=clock[path.bar_timestamp.iloc[ni]]
                if actual_i<end or actual_i==end and nphase=='OPEN':raise ValueError('Standing protection should precede forced order')
        resolution=scalar_exit(path,int(match[0]),pd.Timestamp(r['expiry']),c,mandatory)
        if closed:
            if resolution is None:raise ValueError('Exit not found')
            k,px,phase=resolution
            if clock[path.bar_timestamp.iloc[k]]!=end or phase!=r['exit_phase'] or not np.isclose(px,r['exit_price'],atol=1e-8):
                raise ValueError('Scalar exit differs')
        elif resolution is not None:raise ValueError('Position should already be closed')
        cash_delta[entry]+=-sign*q*p-q*p*.0008
        held_prices=caches[s][entry:end]
        if not np.isfinite(held_prices).all():raise ValueError('Missing held marks')
        value[entry:end]+=sign*q*held_prices;gross[entry:end]+=q*held_prices
        if closed:
            duration=days.get_loc(pd.Timestamp(r['exit_date']))-days.get_loc(pd.Timestamp(r['entry_date']))
            borrow=q*p*.003*duration/252 if sign==-1 else 0.
            flow=sign*q*r['exit_price']-q*r['exit_price']*.0008-borrow
            pnl=sign*q*(r['exit_price']-p)-q*(p+r['exit_price'])*.0008-borrow
            if not np.isclose(pnl,r['pnl'],atol=1e-7) or not np.isclose(borrow,r['borrow_cost'],atol=1e-8):raise ValueError('Cashflow/borrow/PnL mismatch')
            if r['holding_sessions']!=duration+1:raise ValueError('Sessions counted as bars')
            cash_delta[end]+=flow
            if r['exit_phase']=='OPEN' and r['exit_reason'] not in ('PRODUCTION_BREAKER_FORCE','MAINTENANCE_NEXT_OPEN'):
                natural_open_flows[end]+=flow
        else:
            duration=days.get_loc(days[-1])-days.get_loc(pd.Timestamp(r['entry_timestamp']).tz_convert('America/New_York').normalize().tz_localize(None))
            cash_delta[-1]-=q*p*.003*duration/252 if sign==-1 else 0.
    if verified_forced!=len(forced):raise ValueError('Missing approved risk exits')
    cash=4000+np.cumsum(cash_delta);total_interest=0.
    charges={pd.Timestamp(r['date']):r['interest'] for r in maintenance}
    pending=sum(r.get('borrow_accrued_usd',0.) for r in opened)
    for i,(ts,day,last) in enumerate(tape['timeline']):
        if last:
            di=days.get_loc(day);boundary=days[di+1] if di+1<len(days) else day+pd.Timedelta(days=1)
            finance_base=cash[i]-total_interest+(pending if i==n-1 else 0.)
            interest=max(-finance_base,0.)*.065*(boundary-day).days/360
            if not np.isclose(interest,charges[day],atol=1e-7):raise ValueError('Financing mismatch')
            total_interest+=interest
        cash[i]-=total_interest
    max_error=0.
    for label,a,b in [('cash',marks.cash.to_numpy(),cash),('gross',marks.gross.to_numpy(),gross),('equity',marks.equity.to_numpy(),cash+value)]:
        err=float(np.max(np.abs(a-b)));max_error=max(max_error,err)
        if err>1e-6:raise ValueError(f'{label} reconstruction failed:{err}')
    # Reconstruct every risk opening snapshot, not merely its saved status.
    replay=ProductionRiskController(profile['guard_fields'])
    if len(events)!=len(days):raise ValueError('Risk not evaluated once per daily session')
    for day,e in zip(days,events):
        i=int(e['bar_number']);ts=tape['timeline'][i][0]
        if pd.Timestamp(e['date'])!=day or ts!=schedule.at[day,'market_open']:raise ValueError('Risk clock mismatch')
        before_cash=(cash[i-1] if i else 4000.)+natural_open_flows[i]
        holdings={}
        for r in records:
            if int(r['entry_bar'])>=i:continue
            exit_i=int(r.get('exit_bar',n))
            at_risk=(exit_i>i or exit_i==i and (r['exit_phase']=='INTRABAR' or r['exit_reason'] in ('PRODUCTION_BREAKER_FORCE','MAINTENANCE_NEXT_OPEN')))
            if at_risk:holdings[r['symbol']]=r
        declared={p['symbol']:p for p in e['held_before']}
        if set(holdings)!=set(declared):raise ValueError('Risk held snapshot differs from real positions')
        expected_equity=before_cash
        for s,r in holdings.items():
            op=tape['bars'][i][s][0];q=float(r['qty'])
            if declared[s]['quantity']!=q or declared[s]['side']!=c['side'] or not np.isclose(declared[s]['mark'],op,atol=1e-10):raise ValueError('Risk uses wrong held quantity/mark')
            expected_equity+=sign*q*op
        if not np.isclose(before_cash,e['cash_before'],atol=1e-6) or not np.isclose(expected_equity,e['equity_before'],atol=1e-6):raise ValueError('Risk equity/cash snapshot not reconstructed')
        ctx=contexts[day];reg=None if pd.isna(ctx.regime) else str(ctx.regime)
        if ctx.source_date>=day or pd.Timestamp(e['regime_source_date'])!=ctx.source_date:raise ValueError('Risk regime not prior-session')
        result=replay.evaluate(day,float(expected_equity),reg)
        for k in ['active','just_tripped','daily_loss_status','regime']:
            if result[k]!=e[k]:raise ValueError(f'Risk status mismatch:{k}')
        if not np.isclose(result['allocation_scale'],e['allocation_scale'],atol=1e-12) or not np.isclose(result['reference_peak'],e['reference_peak'],atol=1e-6):raise ValueError('Risk allocation/peak mismatch')
        selected=[]
        if result['just_tripped'] and profile['force_close_enabled']:
            held=e['held_before']
            ordered=sorted(held,key=lambda p:(-1 if p['side']=='sell' else 1)*p['quantity']*(p['mark']-p['entry_price']))
            selected=[p['symbol'] for p in ordered[:max(1,int(len(held)*profile['force_close_fraction']+.5))]] if held else []
        if selected!=e['forced_symbols']:raise ValueError('Wrong forced-close count/selection')
        last=clock[schedule.at[day,'market_close']-pd.Timedelta(minutes=5)]
        close_equity=float(marks.equity.iloc[last])+(pending if last==n-1 else 0.)
        if not np.isclose(close_equity,e['closing_equity'],atol=1e-6):raise ValueError('Risk closing equity mismatch')
        replay.finish(day,close_equity)
    for d in READ(out/'decisions.json'):
        if d['status']=='NATIVE_OPENED':
            if d.get('max_entry_leverage')!=1 or d['post_entry_gross']>d['post_entry_equity']+1e-7:raise ValueError('1x admission breached')
            if int(d['quantity'])!=int(d['production_approved']):raise ValueError('Production approval not booked')
            if d['scaled_proposal']!=int(d['full_quantity']*.5*d['allocation_scale']):raise ValueError('B4 scale not applied once')
    report=dict(status='PASS_PRODUCTION_RISK_CASH_EXITS',closed_trades=len(trades),marks=n,
        max_absolute_reconstruction_error_usd=max_error,risk_sessions=len(events),
        risk_trips=sum(e['just_tripped'] for e in events),forced_exits=verified_forced,
        degraded_sessions=sum(e['allocation_scale']<1 for e in events),
        daily_loss_observations=sum(e['daily_loss_status'] for e in events),independent_human_review=False)
    atomic_json(out/'audit.json',report);return report
