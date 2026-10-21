"""Offline independent-formula audit of campaigns, NOT human independence."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.us_oracle_campaign import READ,PRICE


def vector_exit(a,start,end,side):
    p=a[start:end+1];entry=p[0,0]
    extremes=p[:-1,1] if side==1 else p[:-1,2]
    known=np.r_[entry,np.maximum.accumulate(extremes)] if side==1 else np.r_[entry,np.minimum.accumulate(extremes)]
    known=np.maximum(known,entry) if side==1 else np.minimum(known,entry)
    stops=np.maximum(entry*.95,known*.85) if side==1 else np.minimum(entry*1.05,known*1.15)
    gaps=side*(p[:,0]-stops)<=np.abs(stops)*1e-12
    touch=p[:,2]<=stops+abs(stops)*1e-12 if side==1 else p[:,1]>=stops-abs(stops)*1e-12
    touch[-1]=False
    hits=np.flatnonzero(gaps|touch)
    if not len(hits):return end,float(p[-1,0]),'EXPIRY',float(stops[-1]),False
    k=int(hits[0]);return start+k,float(p[k,0] if gaps[k] else stops[k]),'GAP_STOP' if gaps[k] else 'STOP',float(stops[k]),bool(gaps[k])


def event_array(frames):
    events=[];offset=0;parts=[];session_offsets=[]
    for session in range(1,21):
        prev,cur=frames[session-1],frames[session]
        close=cur.close.to_numpy(float);high=float(prev.high.max());low=float(prev.low.min())
        before=np.r_[float(prev.close.iloc[-1]),close[:-2]]
        long=(before<=high)&(close[:-1]>high)&(close[1:]>high)
        short=(before>=low)&(close[:-1]<low)&(close[1:]<low)
        for k in np.flatnonzero(long|short):
            # k is first outside bar, confirmation k+1, execution k+2.
            if k+2<len(cur):events.append((offset+int(k)+2,1 if long[k] else -1))
        parts.append(cur);session_offsets.extend([session]*len(cur));offset+=len(cur)
    return pd.concat(parts,ignore_index=True),np.array(session_offsets),events


def audit(root):
    p=READ(root/'protocol.json');r=READ(root/'report.json')
    verify_hashes(Path('.'),p['sources']);verify_hashes(root,r['files'])
    verify_hashes(root,READ(root/'prepared.json')['files'])
    snap=READ(root/'snapshot-ready.json');verify_hashes(root,snap['files'])
    selected=pd.read_parquet(root/'selected.parquet');cov=pd.read_parquet(root/'coverage.parquet')
    cases=pd.read_parquet(root/'campaigns.parquet');fills=pd.read_parquet(root/'trades.parquet')
    schedule=pd.read_parquet(root/'sessions.parquet');days=pd.DatetimeIndex(schedule.date)
    assert len(cov)==selected.admitted.sum()
    assert not cases.duplicated(['pair_id','horizon','direction','profile']).any()
    assert len(cases)==24*cov.status.eq('OK').sum()
    # Admission is an input-time decision, no future coverage or profile-dependent reset.
    blocked={}
    for row in selected.itertuples():
        i=days.get_loc(row.date);allowed=i>=blocked.get(row.symbol,-1)
        assert bool(row.admitted)==allowed
        if allowed:blocked[row.symbol]=i+20
    raw=pd.concat([f for n in snap['files'] if len(f:=pd.read_parquet(root/n))],ignore_index=True)
    groups=dict(tuple(raw.groupby(['symbol','trade_date'],sort=False)));del raw
    daily=pd.read_parquet(PRICE).set_index(['symbol','date'])
    sched=schedule.set_index('date')
    selected=selected.set_index('pair_id');checked=0;campaign_checks=0
    bycase=dict(tuple(fills.groupby(['pair_id','horizon','direction','profile'],sort=False))) if len(fills) else {}
    for pair_id,g in cases.groupby('pair_id',sort=False):
        row=selected.loc[pair_id];i=days.get_loc(row.date);window=days[i:i+21]
        fs=[groups[row.symbol,d].sort_values('bar_timestamp').reset_index(drop=True) for d in window]
        aggregates=[]
        for day,frame in zip(window,fs):
            opening,closing=sched.loc[day,['market_open','market_close']]
            expected=pd.date_range(opening,closing,freq='5min',inclusive='left')
            assert pd.DatetimeIndex(frame.bar_timestamp).equals(expected)
            assert pd.DatetimeIndex(frame.bar_end_timestamp).equals(expected+pd.Timedelta(minutes=5))
            v=frame[['open','high','low','close','volume']].to_numpy(float)
            assert np.isfinite(v).all() and (v>0).all()
            assert (v[:,1]>=v[:,:4].max(axis=1)).all() and (v[:,2]<=v[:,:4].min(axis=1)).all()
            for column,value in [('provider','alpaca'),('data_source','alpaca_sip'),('market_code','US_EQ'),
                ('interval_code','5m'),('session_tag','regular'),('data_adjustment','raw'),('is_filled',0)]:
                assert frame[column].eq(value).all()
            aggregates.append([v[0,0],v[:,1].max(),v[:,2].min(),v[-1,3]])
        reference=daily.loc[[(row.symbol,d) for d in window],['open','high','low','close']].to_numpy(float)
        ratios=np.array(aggregates)/reference
        assert np.isfinite(ratios).all() and (reference>0).all() and ratios.max()/ratios.min()-1<=.01
        for symbol,reserve in p['price_reserves'].items():
            if symbol==row.symbol:assert window[-1]<pd.Timestamp(reserve['start'])
        path,offset,events=event_array(fs)
        a=path[['open','high','low','close']].to_numpy(float);times=pd.DatetimeIndex(path.bar_timestamp);ends=pd.DatetimeIndex(path.bar_end_timestamp)
        for c in g.itertuples():
            key=(pair_id,c.horizon,c.direction,c.profile)
            ff=bycase.get(key,pd.DataFrame()).sort_values('attempt') if key in bycase else pd.DataFrame()
            limit,risk=p['profiles'][c.profile];end=int(np.flatnonzero(offset==c.horizon)[-1])
            balance=1000.;spent=0.;earliest=0;n=0
            for start,side in events:
                if start<earliest or start>=end or n>=limit:continue
                if c.direction=='LONG_ONLY' and side==-1:continue
                planned=min(1000*risk,max(0.,20-spent))
                if planned<=0 or balance<=0:break
                entry=float(a[start,0]);days_left=max(1,(times[-1].date()-times[start].date()).days)
                reserve=entry*(.05+.0008*2.05+(.003*days_left/365 if side==-1 else 0))
                qty=int(np.floor(min(planned/reserve,balance/entry)))
                if qty<=0:break
                assert n<len(ff)
                t=ff.iloc[n];idx,price,reason,stop,gap=vector_exit(a,start,end,side)
                exit_time=times[idx] if gap or reason=='EXPIRY' else ends[idx]
                dur=max(1,(exit_time.date()-times[start].date()).days)
                borrow=qty*entry*.003*dur/365 if side==-1 else 0.
                gross=side*qty*(price-entry);fees=.0008*qty*(entry+price);net=gross-fees-borrow
                assert t.entry_bar==start and t.exit_bar==idx and t.outcome==reason
                assert t.quantity==qty and t.side==('LONG' if side==1 else 'SHORT')
                assert t.entry_time==times[start] and t.signal_time==path.bar_end_timestamp.iloc[start-1]
                assert t.exit_time==exit_time and np.isclose(t.exit_price,price,atol=1e-10,rtol=0)
                assert np.isclose(t.stop_at_exit,stop,atol=1e-10,rtol=0)
                assert np.isclose(t.net,net,atol=1e-9,rtol=0)
                assert np.isclose(t.stress_net,gross-.0025*qty*(entry+price)-borrow,atol=1e-9,rtol=0)
                assert t.stop_and_cost_reserve<=planned+1e-9 and t.notional<=balance+1e-9
                balance+=net;spent+=max(0.,-net);earliest=idx+3;n+=1;checked+=1
            assert n==len(ff)==c.attempts
            assert np.isclose(balance,c.final_balance,atol=1e-9,rtol=0)
            assert np.isclose((balance-1000)/1000,c.net_pct,atol=1e-12,rtol=0)
            assert c.stress_net<=c.net+1e-9
            assert c.drawdown_5m<=0
            campaign_checks+=1
        # First half-control fill exactly identical to first TWO_SPLIT fill.
        for h in [5,10,15,20]:
            for d in ['BOTH','LONG_ONLY']:
                aa=bycase.get((pair_id,h,d,'ONE_HALF_CONTROL'))
                bb=bycase.get((pair_id,h,d,'TWO_SPLIT'))
                assert (aa is None)==(bb is None)
                if aa is not None:
                    a0=aa.sort_values('attempt').iloc[0];b0=bb.sort_values('attempt').iloc[0]
                    for field in ['entry_bar','exit_bar','quantity','net','planned_risk']:assert a0[field]==b0[field]
    assert checked==len(fills) and campaign_checks==len(cases)
    results=[]
    for y in [2025,2026]:
        z=[v for v in r['comparisons'] if v['year']==y and v['horizon']==20 and v['direction']=='BOTH' and v['control']=='ONE_FULL']
        if not z:results.append(dict(year=y,primary_positive=False,reason='NO_QUALIFIED_CASES'));continue
        x=z[0];ok=x['ci95'] is not None and x['ci95'][0]>0
        results.append(dict(year=y,primary_positive=bool(ok),mean_delta=x['mean_delta'],ci95=x['ci95']))
    result=dict(status='PASS_EXPLORATORY_CAMPAIGN_AUDIT',checked_trades=checked,checked_cases=campaign_checks,
        original_signals=len(selected),admitted=len(cov),qualified_campaigns=int(cov.status.eq('OK').sum()),
        primary_h20=results,report_sha256=digest(root/'report.json'),
        verdict='EXPLORATORY_ONLY_NO_PROMOTION' if all(x['primary_positive'] for x in results) else 'NO_STABLE_PRIMARY_REENTRY_ADVANTAGE',
        note='Same-assistant separate vector exit/signal/ledger implementation, not independent human review. No best-horizon selection on already inspected2025/26; SHORT hypothetical; campaign means are NOT annual portfolio returns.')
    atomic_json(root/'final-audit.json',result);print(result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    audit(parser.parse_args().output)
