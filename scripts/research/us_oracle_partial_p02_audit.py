"""P02 scalar lot exits and vector cash/risk reconstruction, separate arithmetic.

No native exit resolver, primary partial methods or primary scalar_legs calls.
Same assistant verification, not independent human review. Offline only.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from backtesting.production_risk_replay import ProductionRiskController
from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes


def expected_exits(frame,start,due,quantity,partial,forced=None):
    """Independent full-quantity evolution; each tuple is bar,qty,price,phase."""
    entry=float(frame.open.iloc[start]);peak=entry;left=quantity;half=quantity//2
    target=round(entry*1.10,2);taken=not partial or half==0;result=[]
    for i in range(start,len(frame)):
        row=frame.iloc[i];stop=max(round(entry*(1-.07),2),round(peak*(1-.15),2))
        if row.open<=stop:
            result.append((i,left,float(row.open),'OPEN'));left=0;break
        if not taken and row.open>=target:
            result.append((i,half,target,'OPEN'));left-=half;taken=True
        if row.bar_timestamp>=due or forced is not None and row.bar_timestamp==forced:
            result.append((i,left,float(row.open),'OPEN'));left=0;break
        if row.low<=stop:
            result.append((i,left,stop,'INTRABAR'));left=0;break
        if not taken and row.high>=target:
            result.append((i,half,target,'INTRABAR'));left-=half;taken=True
        peak=max(peak,float(row.high))
    return result,left


def audit_case(out,tape,fee_bps,partial):
    from scripts.research.us_oracle_partial_p02 import READ,parent
    out=Path(out);trades=pd.read_parquet(out/'trades.parquet');marks=pd.read_parquet(out/'marks.parquet')
    opened=READ(out/'open-positions.json');events=READ(out/'production-risk-events.json')
    decisions=READ(out/'decisions.json');maintenance=READ(out/'maintenance.json')
    fee=fee_bps/10000;n=len(marks);days=pd.DatetimeIndex(tape['calendar'].date)
    schedule=tape['calendar'].set_index('date');clock={t:i for i,(t,_,_) in enumerate(tape['timeline'])}
    records=trades.to_dict('records')+opened
    by_campaign=defaultdict(list)
    for r in records:by_campaign[int(r['pair_id'])].append(r)
    native_entries={(d['symbol'],pd.Timestamp(d['time'])):int(d['quantity']) for d in decisions if d['status']=='NATIVE_OPENED'}
    allowed={int(r.pair_id):r for r in tape['candidates'].itertuples()}
    cash_delta=np.zeros(n);value=np.zeros(n);gross=np.zeros(n);natural=np.zeros(n);cache={}
    forced={(s,int(e['bar_number'])) for e in events for s in e['forced_symbols']};found_forced=set()
    spans=defaultdict(list)
    for pid,rows in by_campaign.items():
        sample=rows[0];symbol=sample['symbol'];start=int(sample['entry_bar']);stamp=pd.Timestamp(sample['entry_timestamp'])
        if pid not in allowed or stamp!=allowed[pid].timestamp or pd.Timestamp(sample['expiry'])!=allowed[pid].due_open:
            raise ValueError('Unqualified entry/expiry lineage')
        initial=native_entries.get((symbol,stamp))
        if initial is None or sum(int(r['qty']) for r in rows)!=initial:
            raise ValueError('Duplicated/missing share basis across partial and remainder')
        frame=tape['paths'][pid];matches=np.flatnonzero(frame.bar_timestamp.eq(stamp))
        if len(matches)!=1:raise ValueError('Missing actual entry bar')
        j=int(matches[0]);price=float(frame.open.iloc[j])
        actual=[];force=None;open_quantity=0;finish=start
        for r in rows:
            if r['entry_bar']!=start or r['entry_price']!=price:raise ValueError('Reentry/entry basis changed')
            if 'exit_bar' not in r:open_quantity+=int(r['qty']);finish=n;continue
            finish=max(finish,int(r['exit_bar']))
            if r['exit_reason'] in ('PRODUCTION_BREAKER_FORCE','MAINTENANCE_NEXT_OPEN'):
                force=pd.Timestamp(r['exit_timestamp']);b=int(r['exit_bar'])
                day=pd.Timestamp(force.tz_convert('America/New_York').date())
                if force!=schedule.at[day,'market_open']:raise ValueError('Non-opening forced exit')
                if r['exit_reason']=='PRODUCTION_BREAKER_FORCE':
                    if (symbol,b) not in forced:raise ValueError('Unapproved forced exit')
                    found_forced.add((symbol,b))
                else:
                    di=days.get_loc(day)
                    if not di or not maintenance[di-1]['breach']:raise ValueError('Unjustified maintenance exit')
            actual.append((int(r['exit_bar']),int(r['qty']),float(r['exit_price']),r['exit_phase']))
        expected,left=expected_exits(frame,j,pd.Timestamp(sample['expiry']),initial,partial,force)
        expected=[(clock[frame.bar_timestamp.iloc[k]],q,p,phase) for k,q,p,phase in expected]
        if sorted(actual)!=sorted(expected) or open_quantity!=left:
            raise ValueError(f'Independent partial/stop/horizon reconstruction differs: {pid}')
        for a,b in spans[symbol]:
            if max(a,start)<min(b,finish):raise ValueError('Overlapping separate campaigns for same symbol')
        spans[symbol].append((start,finish))
    if found_forced!=forced:raise ValueError('Missing forced risk exits')
    for r in records:
        symbol=r['symbol'];entry=int(r['entry_bar']);closed='exit_bar' in r;end=int(r['exit_bar']) if closed else n
        if symbol not in cache:cache[symbol]=np.array([bars.get(symbol,(np.nan,)*4)[3] for bars in tape['bars']])
        qty=float(r['qty']);price=float(r['entry_price']);cash_delta[entry]-=qty*price*(1+fee)
        held=cache[symbol][entry:end]
        if not np.isfinite(held).all():raise ValueError('Missing held mark')
        value[entry:end]+=qty*held;gross[entry:end]+=qty*held
        if closed:
            flow=qty*r['exit_price']*(1-fee);pnl=qty*(r['exit_price']-price)-qty*(r['exit_price']+price)*fee
            if not np.isclose(pnl,r['pnl'],atol=1e-7,rtol=0):raise ValueError('Partial/remaining fee basis differs')
            if r['holding_sessions']!=days.get_loc(pd.Timestamp(r['exit_date']))-days.get_loc(pd.Timestamp(r['entry_date']))+1:
                raise ValueError('Holding horizon counted as5min bars')
            cash_delta[end]+=flow
            if r['exit_phase']=='OPEN' and r['exit_reason'] not in ('PRODUCTION_BREAKER_FORCE','MAINTENANCE_NEXT_OPEN'):natural[end]+=flow
        else:
            expected=qty*(r['mark']-price)-qty*price*fee
            if not np.isclose(expected,r['unrealized_pnl_usd'],atol=1e-7):raise ValueError('Open remainder MTM mismatch')
    cash=4000+np.cumsum(cash_delta);interest=0.;charges={pd.Timestamp(e['date']):e['interest'] for e in maintenance}
    for i,(t,day,last) in enumerate(tape['timeline']):
        if last:
            di=days.get_loc(day);boundary=days[di+1] if di+1<len(days) else day+pd.Timedelta(days=1)
            charge=max(-(cash[i]-interest),0.)*.065*(boundary-day).days/360
            if not np.isclose(charge,charges[day],atol=1e-7):raise ValueError('Financing mismatch')
            interest+=charge
        cash[i]-=interest
    error=0.
    for label,a,b in [('cash',marks.cash.to_numpy(),cash),('gross',marks.gross.to_numpy(),gross),('equity',marks.equity.to_numpy(),cash+value)]:
        err=float(np.max(np.abs(a-b)));error=max(error,err)
        if err>1e-6:raise ValueError(f'{label} reconstruction failed: {err}')
    profile=READ(parent.REFERENCE/'production-risk.json')
    regimes={r.date:r for r in pd.read_parquet(parent.REFERENCE/'risk-regimes.parquet').itertuples()}
    replay=ProductionRiskController(profile['guard_fields'])
    if len(events)!=len(days):raise ValueError('B4 not evaluated daily')
    for day,e in zip(days,events):
        i=int(e['bar_number']);t=tape['timeline'][i][0]
        if pd.Timestamp(e['date'])!=day or t!=schedule.at[day,'market_open']:raise ValueError('Risk clock differs')
        before=(cash[i-1] if i else 4000.)+natural[i];holdings={}
        for r in records:
            if int(r['entry_bar'])>=i:continue
            end=int(r.get('exit_bar',n))
            if end>i or end==i and (r['exit_phase']=='INTRABAR' or r['exit_reason'] in ('PRODUCTION_BREAKER_FORCE','MAINTENANCE_NEXT_OPEN')):
                h=holdings.setdefault(r['symbol'],dict(quantity=0,entry_price=r['entry_price']))
                h['quantity']+=r['qty']
        declared={p['symbol']:p for p in e['held_before']};equity=before
        if set(holdings)!=set(declared):raise ValueError('B4 held symbols differ after partial fills')
        for s,h in holdings.items():
            op=tape['bars'][i][s][0];equity+=h['quantity']*op
            if declared[s]['quantity']!=h['quantity'] or declared[s]['side']!='buy' or not np.isclose(declared[s]['mark'],op):
                raise ValueError('B4 uses wrong remaining quantity/mark')
        if not np.isclose(before,e['cash_before'],atol=1e-6) or not np.isclose(equity,e['equity_before'],atol=1e-6):
            raise ValueError('B4 opening partial cash/equity differs')
        ctx=regimes[day];reg=None if pd.isna(ctx.regime) else str(ctx.regime)
        if ctx.source_date>=day or pd.Timestamp(e['regime_source_date'])!=ctx.source_date:raise ValueError('Noncausal regime')
        event=replay.evaluate(day,float(equity),reg)
        for k in ['active','just_tripped','daily_loss_status','regime']:
            if event[k]!=e[k]:raise ValueError('B4 state differs')
        for k in ['allocation_scale','reference_peak']:
            if not np.isclose(event[k],e[k],atol=1e-6,rtol=0):raise ValueError('B4 scale/peak differs')
        selected=[]
        if event['just_tripped'] and profile['force_close_enabled']:
            order=sorted(holdings,key=lambda s:holdings[s]['quantity']*(tape['bars'][i][s][0]-holdings[s]['entry_price']))
            selected=order[:max(1,int(len(order)*profile['force_close_fraction']+.5))] if order else []
        if selected!=e['forced_symbols']:raise ValueError('Wrong remaining-position risk liquidation')
        close_i=clock[schedule.at[day,'market_close']-pd.Timedelta(minutes=5)]
        eq=float(marks.equity.iloc[close_i])
        if not np.isclose(eq,e['closing_equity'],atol=1e-6):raise ValueError('B4 closing equity differs')
        replay.finish(day,eq)
    for d in decisions:
        if d['status']=='NATIVE_OPENED':
            if d.get('max_entry_leverage')!=1 or d['post_entry_gross']>d['post_entry_equity']+1e-7:raise ValueError('Admission1x exceeded')
            if int(d['quantity'])!=int(d['production_approved']):raise ValueError('Risk quantity not booked')
            if d['scaled_proposal']!=int(d['full_quantity']*.5*d['allocation_scale']):raise ValueError('B4 scale not applied once')
    report=dict(status='PASS_PARTIAL_SHARE_CASH_EXITS_B4',campaigns=len(by_campaign),exit_legs=len(trades),
        partial_exits=int(trades.exit_reason.eq('PARTIAL_TP10').sum()) if len(trades) else 0,
        marks=n,max_absolute_reconstruction_error_usd=error,risk_sessions=len(events),
        risk_trips=sum(e['just_tripped'] for e in events),forced_exits=len(found_forced),
        independent_human_review=False)
    atomic_json(out/'audit.json',report);return report


def final_review(root):
    from scripts.research.us_oracle_partial_p02 import READ,parent
    root=Path(root);r=READ(root/'report.json');verify_hashes(root,r['files'])
    verify_hashes(Path('.'),READ(root/'protocol.json')['sources'])
    if len(r['results'])!=8 or not all(x['audit']['status']=='PASS_PARTIAL_SHARE_CASH_EXITS_B4' for x in r['results']):
        raise ValueError('Eight audited cases required')
    groups,_,schedule=parent.load_groups();days=pd.DatetimeIndex(schedule.date)
    signals=pd.read_parquet(root/'signals.parquet');units=pd.read_parquet(root/'unit-results.parquet').set_index('pair_id')
    verified=0
    for s in signals.itertuples():
        i=days.get_loc(s.date);frame=pd.concat([groups[s.symbol,d] for d in days[i:i+21]])
        frame=frame[frame.bar_timestamp.between(s.timestamp,s.due_open)].reset_index(drop=True)
        for arm,partial in [('WINNER',False),('P02',True)]:
            events,left=expected_exits(frame,0,s.due_open,2,partial)
            if left:raise ValueError('Immature unit reconstruction')
            for fee in (8,25):
                v=100*sum(q*((px-s.price)-(fee/10000)*(px+s.price)) for _,q,px,_ in events)/(2*s.price)
                if not np.isclose(v,units.loc[s.pair_id,f'{arm}_{fee}'],atol=1e-9,rtol=0):raise ValueError('Unit arithmetic differs')
                verified+=1
    a=dict(status='PASS_P02_BASELINE_PARTIAL_CASH_RISK_AND_UNIT_REVIEW',portfolio_cases=8,
        baseline_cases_exactly_reproduced=4,unit_cost_results_verified=verified,
        report_sha256=digest(root/'report.json'),reviewer_source_sha256=digest(__file__),
        independent_human_review=False,production_promoted=False)
    atomic_json(root/'final-audit.json',a);print(a);return a


if __name__=='__main__':
    import argparse
    from scripts.research.us_oracle_partial_p02 import OUTPUT
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output-dir',type=Path,default=OUTPUT)
    final_review(p.parse_args().output_dir)
