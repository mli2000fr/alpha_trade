"""Frozen TOP10 PATH_H20 campaign: H5/H10/H15/H20, one/two entries.

Existing SIP bars only. READ ONLY snapshot; offline replay, no fit or orders.
Not a shared-capital portfolio or a certified broker-execution backtest.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from scripts.research.us_concentrated_historical_tapes import atomic_json,digest,verify_hashes
from scripts.research.us_top10_intraday_breakout import qualify_day

SOURCE=Path('artifacts/research/us_h10_h20_frozen_comparison/20261019-v1')
PRICE=Path('artifacts/research/us_h10_price_readiness/20261019-v1/qualification-final-v4/research-prices.parquet')
UNIVERSE=Path('config/univers_batch/univers_filtred_tradable.txt')
READ=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
HORIZONS=[5,10,15,20]
PROFILES={'ONE_FULL':(1,.02),'ONE_HALF_CONTROL':(1,.01),'TWO_SPLIT':(2,.01)}
LOG=logging.getLogger(__name__)


def admit_campaigns(scores,days):
    f=scores.sort_values(['date','rank','symbol']).copy(); blocked={}; flags=[]
    for r in f.itertuples():
        i=days.get_loc(r.date); take=i>=blocked.get(r.symbol,-1)
        flags.append(take)
        if take:blocked[r.symbol]=i+20
    f['admitted']=flags
    f['pair_id']=np.arange(len(f))
    return f.reset_index(drop=True)


def prepare(root):
    if (root/'protocol.json').exists():
        p=READ(root/'protocol.json');verify_hashes(Path('.'),p['sources'])
        verify_hashes(root,READ(root/'prepared.json')['files']);return p
    if root.exists() and any(root.iterdir()):raise ValueError('Fresh empty output required')
    parent=READ(SOURCE/'protocol.json')
    if READ(SOURCE/'final-audit.json')['status']!='PASS_EXPLORATORY_ONLY':raise ValueError('Unqualified Oracle')
    expected=next(v for k,v in parent['sources'].items() if Path(k).name==PRICE.name)
    if digest(PRICE)!=expected:raise ValueError('Changed research prices')
    files=[Path(__file__),Path('scripts/research/us_oracle_campaign_audit.py'),
        Path('tests/test_us_oracle_campaign.py'),Path('scripts/research/us_top10_intraday_breakout.py'),
        Path('scripts/research/us_concentrated_historical_tapes.py'),PRICE,UNIVERSE,
        SOURCE/'protocol.json',SOURCE/'final-audit.json']
    for y in [2024,2025,2026]:
        name=f'{y}-H20-scores.parquet'
        if digest(SOURCE/name)!=READ(SOURCE/f'{y}-done.json')['files'][name]:raise ValueError('Changed scores')
        files.extend([SOURCE/name,SOURCE/f'{y}-done.json'])
    p=dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources={str(f):digest(f) for f in files},
        hypothesis='Bounded second fresh breakout may recover an initial false departure within an Oracle amplitude campaign; not a known profitable professional recipe.',
        oracle='Frozen research PATH_H20 CatBoost chronological OOS ranks at J, same TOP10 for every arm; NOT production LightGBM or H10 model. No fit or rerank.',
        horizons=HORIZONS,profiles=PROFILES,directions=['BOTH','LONG_ONLY'],observation_end='2026-09-30',
        selection='Original rank<=10 before price quality; no replacement or liquid-universe restriction.',
        admission='Earliest original signal J per symbol, then block20NYSE sessions for ALL horizons/profiles before future qualification; new J may be prior J+20. No year reset. Other overlapping signals logged, not independently traded.',
        quality='Primary common cohort needs complete positive raw SIP5m grids J..J+20 and constant raw/daily OHLC scale over ALL21sessions, ratio spread<=1%. Even post-exit gaps reject common outcome; unknown never zero. Survivor/coverage selection reserved.',
        reference='Previous COMPLETE session high/low and close from raw SIP; no adjusted/raw mixing.',
        entry='Two consecutive completed5m closes strictly above previous-session high =>LONG, below previous-session low=>SHORT; close before first outside bar must be at/inside the corresponding boundary. First bar cannot alone signal. For first two bars, prior-session close supplies that preceding close. Next contiguous same-session bar OPEN only; no fill in signal bar.',
        reentry='At most2 executed trades. Following an exit, BOTH new confirmation bars must begin strictly after the exit bar; new crossing of updated previous-session boundary required, same or opposite direction. No automatic stop-and-reverse, no averaging, no immediate retry.',
        campaign_duration='J+1..J+H includes waiting and reentries, never Hsessions per trade. Expire at OPEN of final5m bar of J+H. No entry at expiry open.',
        protections='SL5% of each entry; trailing15% of favorable high/low observed through PRIOR completed bars, updated only at5m boundaries. No TP. Do not use current bar favorable extreme to tighten a stop within that bar. Gap through known stop at actual open.',
        profiles_explained='ONE_FULL: one entry up to2% initial allocated capital planned risk. TWO_SPLIT: at mosttwo entries each<=1%, cumulative loss budget2%. ONE_HALF_CONTROL: one<=1% entry, identical first size to TWO_SPLIT, isolates extra attempt from half sizing.',
        capital=1000.,campaign_risk=.02,sl=.05,trailing=.15,
        sizing='Whole shares only, no leverage, notional<=current positive equity. Risk denominator reserves SL plus conservative two-leg8bps and full remaining short borrow. For reentry, max planned risk=min(1%initialCapital,2%initialCapital-sum prior net losses); gains do NOT replenish budget. qty0 abstains and ends campaign; no cheapest-later-entry search.',
        costs_per_leg=.0008,stress_costs_per_leg=.0025,borrow_annual=.003,
        costs='8bps per entry/exit executed notional, no extra fixed commission; hypothetical spread/slippage/fees, not historical NBBO/account tariff. SHORT .3%annual ACT/365 min1day, no locates/dividend/recall proof. Stress25bps is accounting on SAME fills/quantities, not a resimulation of budget guards.',
        marks='Standalone1000USD collateral ledger per campaign, realized cash plus current signed price PnL. Drawdown from5m closes/fills only, not intratick or shared account drawdown. No annual capital compounding or sum as account profit.',
        controls='ONE_FULL vs TWO_SPLIT same maximum planned campaign budget; ONE_HALF_CONTROL vs TWO_SPLIT identical first trade sizing. LONG_ONLY is a predeclared control, BOTH short side remains hypothetical.',
        analysis='Report each year/horizon/profile without cherry-picking best horizon peryear. H20 BOTH two-vs-one primary; other3H and LONG_ONLY exploratory;8primary/direction-horizon contrasts also show Bonferroni99.375%CI. No virgin holdout:2024intraday absent,2025/26previouslyexamined. No champion/promotion even if isolated positive result.',
        bootstrap='20-signal-session moving blocks over full calendar,1999draws,seed20261020, paired campaign deltas; all same dates/cohort.',
        price_reserves=parent['price_reserves'],identity_events=parent['identity_events'],
        sql_writes=False,downloads=False,fit=False,orders=False,shared_portfolio=False,
        reserves=['Static current survivor universe; prices historically restated, not actual as-known bar receipts',
            '5mOHLC does not prove bid/ask, depth, auction/halts or fills; stops can exceed loss budget on gaps',
            'LONG_ONLY not proof of an original bearish signal failing; it is a different allowed-action policy',
            'Full20quality cohort may disproportionately exclude corporate actions and illiquid names',
            'Same assistant audit, not independent human review; no production schedule changed'])
    root.mkdir(parents=True,exist_ok=True);atomic_json(root/'protocol.json',p)
    scores=pd.concat([pd.read_parquet(SOURCE/f'{y}-H20-scores.parquet',columns=['date','symbol','rank','score'])
        for y in [2024,2025,2026]],ignore_index=True)
    scores=scores[scores['rank'].le(10)].copy()
    if scores.duplicated(['date','symbol']).any() or not scores.groupby('date').size().eq(10).all():raise ValueError('Invalid TOP10')
    schedule=mcal.get_calendar('NYSE').schedule(start_date=scores.date.min(),end_date=p['observation_end'])
    schedule.index.name='date';schedule=schedule.reset_index();days=pd.DatetimeIndex(schedule.date)
    selected=admit_campaigns(scores,days)
    selected.to_parquet(root/'selected.parquet',index=False);schedule.to_parquet(root/'sessions.parquet',index=False)
    atomic_json(root/'prepared.json',dict(files={n:digest(root/n) for n in ['selected.parquet','sessions.parquet']},
        original=len(selected),admitted=int(selected.admitted.sum()),symbols=selected[selected.admitted].symbol.nunique()))
    LOG.info('Prepared %d original / %d non-overlap campaigns',len(selected),selected.admitted.sum())
    return p


def snapshot(root):
    p=prepare(root)
    if (root/'snapshot-ready.json').exists():verify_hashes(root,READ(root/'snapshot-ready.json')['files']);return
    from sqlalchemy import text,bindparam
    from database.connection import get_sqlalchemy_engine
    rows=pd.read_parquet(root/'selected.parquet');schedule=pd.read_parquet(root/'sessions.parquet')
    days=pd.DatetimeIndex(schedule.date);needed={}
    for r in rows[rows.admitted].itertuples():
        i=days.get_loc(r.date)
        if i+20>=len(days):raise ValueError('Immature campaign calendar')
        for day in days[i:i+21]:needed.setdefault((r.symbol,day.year),set()).add(day.date())
    part=root/'snapshot';part.mkdir(exist_ok=False)
    sql=text('''SELECT symbol,bar_timestamp,bar_end_timestamp,trade_date,open,high,low,close,
        volume,is_filled,data_adjustment,session_tag,provider,data_source,market_code,interval_code,
        observed_at,payload_hash,run_id FROM stock_bars_intraday
        WHERE symbol=:symbol AND bar_timestamp>=:start AND bar_timestamp<:end
        AND trade_date IN :dates AND interval_code='5m' AND data_source='alpaca_sip'
        AND provider='alpaca' AND market_code='US_EQ' AND session_tag='regular'
        ORDER BY bar_timestamp''').bindparams(bindparam('dates',expanding=True))
    engine=get_sqlalchemy_engine();files={};counts=[];started=datetime.now(timezone.utc).isoformat()
    tasks=sorted(needed.items())
    with engine.connect() as conn:
        conn.execute(text('SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
        conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
        for n,((symbol,year),wanted) in enumerate(tasks):
            wanted=sorted(wanted)
            f=pd.read_sql_query(sql,conn,params=dict(symbol=symbol,dates=wanted,
                start=pd.Timestamp(wanted[0]).to_pydatetime(),end=(pd.Timestamp(wanted[-1])+pd.Timedelta(days=2)).to_pydatetime()))
            for col in ['bar_timestamp','bar_end_timestamp','observed_at']:f[col]=pd.to_datetime(f[col],utc=True)
            f['trade_date']=pd.to_datetime(f.trade_date)
            name=f'snapshot/{n:04d}-{symbol}-{year}.parquet';f.to_parquet(root/name,index=False);files[name]=digest(root/name)
            counts.append(dict(symbol=symbol,year=year,expected=len(wanted),sessions=f.trade_date.nunique(),rows=len(f)))
            atomic_json(root/'progress.json',dict(status='SNAPSHOTTING',completed=n+1,total=len(tasks),rows=sum(x['rows'] for x in counts)))
            if n%20==0:LOG.info('Snapshot %d/%d %s rows=%d',n+1,len(tasks),symbol,len(f))
        conn.rollback()
    engine.dispose();pd.DataFrame(counts).to_csv(root/'snapshot-coverage.csv',index=False)
    atomic_json(root/'snapshot-ready.json',dict(started_at_utc=started,finished_at_utc=datetime.now(timezone.utc).isoformat(),
        transaction='REPEATABLE READ / READ ONLY / ROLLBACK',files=files,rows=sum(x['rows'] for x in counts)))


def make_path(frames):
    """J first frame is reference only. Entry signals never inspect today's final high/low."""
    paths=[]
    for prev,today in zip(frames[:-1],frames[1:]):
        f=today.copy();f['previous_high']=prev.high.max();f['previous_low']=prev.low.min()
        f['previous_close']=prev.close.iloc[-1];f['session_offset']=len(paths)+1
        paths.append(f)
    return pd.concat(paths,ignore_index=True)


def fresh_signals(path):
    events=[]
    for _,g in path.groupby('session_offset',sort=False):
        closes=g.close.to_numpy(float);hi=float(g.previous_high.iloc[0]);lo=float(g.previous_low.iloc[0])
        prior=float(g.previous_close.iloc[0]);positions=g.index.to_numpy()
        for k in range(1,len(g)-1):
            before=prior if k==1 else closes[k-2]
            side=1 if before<=hi and closes[k-1]>hi and closes[k]>hi else (
                -1 if before>=lo and closes[k-1]<lo and closes[k]<lo else 0)
            if side and g.bar_timestamp.iloc[k+1]==g.bar_end_timestamp.iloc[k]:
                events.append((int(positions[k+1]),side))
    return events


def exit_trade(a,start,end,side):
    """Discrete5m trailing: known stop checked before updating favorable extrema."""
    entry=float(a[start,0]);peak=entry;stop=entry*(1-side*.05)
    for i in range(start,end+1):
        op,hi,lo,close=a[i]
        if side*(op-stop)<=abs(stop)*1e-12:return i,float(op),'GAP_STOP',float(stop),True
        if i==end:return i,float(op),'EXPIRY',float(stop),False
        if (lo<=stop+abs(stop)*1e-12 if side==1 else hi>=stop-abs(stop)*1e-12):
            return i,float(stop),'STOP',float(stop),False
        peak=max(peak,hi) if side==1 else min(peak,lo)
        stop=max(entry*.95,peak*.85) if side==1 else min(entry*1.05,peak*1.15)
    raise AssertionError('Unreachable')


def simulate_campaign(path,events,horizon,profile,direction,capital=1000.,cost=.0008):
    attempts,risk_fraction=PROFILES[profile]
    end=int(path.index[path.session_offset.eq(horizon)][-1])
    a=path[['open','high','low','close']].to_numpy(float)
    times=pd.DatetimeIndex(path.bar_timestamp);ends=pd.DatetimeIndex(path.bar_end_timestamp)
    balance=capital;spent=0.;earliest=0;trades=[];marks=[capital];mark_times=[times[0]]
    status='NO_SIGNAL'
    for start,side in events:
        if start<earliest or start>=end or len(trades)>=attempts:continue
        if direction=='LONG_ONLY' and side==-1:continue
        planned=min(capital*risk_fraction,max(0.,capital*.02-spent))
        if planned<=0 or balance<=0:status='RISK_BUDGET_EXHAUSTED';break
        # Same conservative20-session borrow reserve for every tested horizon:
        # do not change first share sizing merely because H is shorter.
        entry=float(a[start,0]);days=max(1,(times[-1].date()-times[start].date()).days)
        reserve=entry*(.05+cost*2.05+(.003*days/365 if side==-1 else 0.))
        quantity=int(np.floor(min(planned/reserve,balance/entry)))
        if quantity<=0:status='ABSTAIN_ZERO_WHOLE_SHARES';break
        idx,price,reason,stop,gap=exit_trade(a,start,end,side)
        point=gap or reason=='EXPIRY'
        exit_time=times[idx] if point else ends[idx]
        duration=max(1,(exit_time.date()-times[start].date()).days)
        entry_fee=quantity*entry*cost;exit_fee=quantity*price*cost
        borrow=quantity*entry*.003*duration/365 if side==-1 else 0.
        gross=side*quantity*(price-entry);net=gross-entry_fee-exit_fee-borrow
        stress=gross-.0025*quantity*(entry+price)-borrow
        prior_balance=balance;balance-=entry_fee
        for j in range(start,idx):
            elapsed=max(1,(ends[j].date()-times[start].date()).days)
            accrued=quantity*entry*.003*elapsed/365 if side==-1 else 0.
            marks.append(balance+side*quantity*(a[j,3]-entry)-accrued);mark_times.append(ends[j])
        balance+=gross-exit_fee-borrow;marks.append(balance);mark_times.append(exit_time)
        spent+=max(0.,-net)
        trades.append(dict(attempt=len(trades)+1,side='LONG' if side==1 else 'SHORT',
            entry_bar=start,signal_bar=start-1,exit_bar=idx,entry_time=times[start],signal_time=times[start],
            exit_time=exit_time,exit_bar_start=times[idx],exit_bar_end=ends[idx],
            exit_precision='POINT' if point else '5M_INTERVAL',entry_price=entry,exit_price=price,
            stop_at_exit=stop,outcome=reason,gap_stop=gap,quantity=quantity,
            planned_risk=planned,stop_and_cost_reserve=quantity*reserve,
            notional=entry*quantity,entry_fee=entry_fee,exit_fee=exit_fee,borrow=borrow,
            gross=gross,net=net,stress_net=stress,balance_before=prior_balance,balance_after=balance))
        # Both confirmation bars after exit bar: signal=start-1, first=start-2.
        earliest=idx+3;status='TRADED'
    mark=np.array(marks,float);dd=mark/np.maximum.accumulate(mark)-1
    n=len(trades);net=float(sum(t['net'] for t in trades));stress=float(sum(t['stress_net'] for t in trades))
    if not np.isclose(balance-capital,net,atol=1e-9):raise AssertionError('Ledger imbalance')
    return dict(status=status,attempts=n,first_side=trades[0]['side'] if n else 'NONE',
        net=net,net_pct=net/capital,stress_net=stress,stress_pct=stress/capital,
        gross=sum(t['gross'] for t in trades),fees=sum(t['entry_fee']+t['exit_fee']+t['borrow'] for t in trades),
        final_balance=balance,drawdown_5m=float(dd.min()),worst_planned_loss_used=spent,
        reversed_second=bool(n==2 and trades[0]['side']!=trades[1]['side']),
        changed_second=bool(n==2),marks=len(mark)),trades


def interval(f,days,value,alpha=.05):
    if f.empty or f.date.nunique()<20:return None
    g=f.groupby('date')[value].agg(['sum','count']).reindex(days,fill_value=0)
    a=g['sum'].to_numpy(float);n=g['count'].to_numpy(float);length=len(days);block=min(20,length)
    rng=np.random.default_rng(20261020);values=[]
    for _ in range(1999):
        starts=rng.integers(0,length-block+1,size=int(np.ceil(length/block)))
        ix=(starts[:,None]+np.arange(block)).ravel()[:length]
        if n[ix].sum():values.append(a[ix].sum()/n[ix].sum())
    return [float(x) for x in np.quantile(values,[alpha/2,1-alpha/2])]


def summarize(campaigns,schedule):
    summaries=[];comparisons=[]
    if campaigns.empty:return summaries,comparisons
    for (year,h,d,profile),f in campaigns.groupby(['year','horizon','direction','profile']):
        days=pd.DatetimeIndex(schedule.loc[schedule.date.dt.year.eq(year),'date'])
        active=f[f.attempts.gt(0)]
        summaries.append(dict(year=int(year),horizon=int(h),direction=d,profile=profile,n=len(f),dates=f.date.nunique(),
            symbols=f.symbol.nunique(),active=len(active),trades=int(f.attempts.sum()),
            net_pct=float(f.net_pct.mean()),stress_pct=float(f.stress_pct.mean()),
            active_net_pct=float(active.net_pct.mean()) if len(active) else None,
            gross_mean=float(f.gross.mean()),fees_mean=float(f.fees.mean()),
            winners=int(f.net.gt(1e-10).sum()),losers=int(f.net.lt(-1e-10).sum()),flat=int(f.net.abs().le(1e-10).sum()),
            active_win_rate=float(active.net.gt(0).mean()) if len(active) else None,
            ci95=interval(f,days,'net_pct'),stress_ci95=interval(f,days,'stress_pct'),
            worst_campaign=float(f.net_pct.min()),worst_drawdown_5m=float(f.drawdown_5m.min()),
            second_attempts=int(f.changed_second.sum()),opposite_second=int(f.reversed_second.sum()),
            status_counts={str(k):int(v) for k,v in f.status.value_counts().items()}))
    key=['pair_id','year','date','symbol','horizon','direction']
    base=campaigns[campaigns.profile.eq('TWO_SPLIT')]
    for control in ['ONE_FULL','ONE_HALF_CONTROL']:
        other=campaigns[campaigns.profile.eq(control)][key+['net_pct','stress_pct']]
        f=base.merge(other,on=key,suffixes=('','_control'),validate='one_to_one')
        f['delta']=f.net_pct-f.net_pct_control;f['stress_delta']=f.stress_pct-f.stress_pct_control
        for (year,h,d),g in f.groupby(['year','horizon','direction']):
            days=pd.DatetimeIndex(schedule.loc[schedule.date.dt.year.eq(year),'date'])
            comparisons.append(dict(year=int(year),horizon=int(h),direction=d,control=control,n=len(g),
                mean_delta=float(g.delta.mean()),ci95=interval(g,days,'delta'),
                ci_bonferroni8=interval(g,days,'delta',alpha=.05/8),
                stress_delta=float(g.stress_delta.mean()),stress_ci95=interval(g,days,'stress_delta')))
    return summaries,comparisons


def replay(root):
    p=prepare(root)
    if (root/'report.json').exists():raise ValueError('Immutable completed result')
    snap=READ(root/'snapshot-ready.json');verify_hashes(root,snap['files'])
    selected=pd.read_parquet(root/'selected.parquet');schedule=pd.read_parquet(root/'sessions.parquet')
    sched=schedule.set_index('date');days=pd.DatetimeIndex(schedule.date)
    raw=pd.concat([f for n in snap['files'] if len(f:=pd.read_parquet(root/n))],ignore_index=True)
    groups=dict(tuple(raw.groupby(['symbol','trade_date'],sort=False)));del raw
    prices=pd.read_parquet(PRICE).set_index(['symbol','date'])
    qualified={};reasons={};agg={}
    for key,f in groups.items():
        symbol,day=key;op,cl=sched.loc[day,['market_open','market_close']]
        q,reason=qualify_day(f,op,cl);reasons[key]=reason
        if q is not None:
            qualified[key]=q;agg[key]=[q.open.iloc[0],q.high.max(),q.low.min(),q.close.iloc[-1]]
    groups.clear()
    coverage=[];campaigns=[];trades=[]
    admitted=selected[selected.admitted]
    for k,row in enumerate(admitted.itertuples()):
        i=days.get_loc(row.date);window=days[i:i+21];base=dict(pair_id=row.pair_id,date=row.date,symbol=row.symbol,rank=row.rank,year=row.date.year)
        reason='OK';spread=None
        for day in window:
            if (row.symbol,day) not in qualified:reason=reasons.get((row.symbol,day),'MISSING_SESSION');break
        for symbol,r in p['price_reserves'].items():
            if symbol==row.symbol and window[-1]>=pd.Timestamp(r['start']):reason='RESERVED_PRICE_BASIS'
        for ev in p['identity_events'].get(row.symbol,[]):
            if window[0]<=pd.Timestamp(ev['last_predecessor_date']) and window[-1]>=pd.Timestamp(ev['first_successor_date']):reason='IDENTITY_DISCONTINUITY'
        if reason=='OK':
            keys=[(row.symbol,d) for d in window]
            if not all(key in prices.index for key in keys):reason='MISSING_DAILY_CROSSCHECK'
            else:
                reference=prices.loc[keys,['open','high','low','close']].to_numpy(float)
                ratio=np.array([agg[key] for key in keys])/reference
                spread=float(ratio.max()/ratio.min()-1)
                if not np.isfinite(ratio).all() or (reference<=0).any() or spread>.01:reason='PRICE_BASIS_OR_DAILY_DISAGREEMENT'
        coverage.append(dict(**base,status=reason,ratio_spread=spread,last_day=window[-1]))
        if reason!='OK':continue
        path=make_path([qualified[row.symbol,d] for d in window]);events=fresh_signals(path)
        for h in HORIZONS:
            for direction in ['BOTH','LONG_ONLY']:
                for profile in PROFILES:
                    summary,fills=simulate_campaign(path,events,h,profile,direction)
                    case=dict(**base,horizon=h,direction=direction,profile=profile)
                    campaigns.append(dict(**case,**summary))
                    trades.extend([dict(**case,**t) for t in fills])
        if k%25==0:
            LOG.info('Replay %d/%d qualified=%d cases=%d',k+1,len(admitted),sum(x['status']=='OK' for x in coverage),len(campaigns))
            atomic_json(root/'progress.json',dict(status='REPLAYING',completed=k+1,total=len(admitted),cases=len(campaigns)))
    cov=pd.DataFrame(coverage);out=pd.DataFrame(campaigns);fills=pd.DataFrame(trades)
    cov.to_parquet(root/'coverage.parquet',index=False);out.to_parquet(root/'campaigns.parquet',index=False);fills.to_parquet(root/'trades.parquet',index=False)
    summaries,comparisons=summarize(out,schedule[schedule.date.between(selected.date.min(),selected.date.max())])
    pd.DataFrame(summaries).to_csv(root/'summary.csv',index=False);pd.DataFrame(comparisons).to_csv(root/'comparisons.csv',index=False)
    coverage_year=[]
    for y,f in selected.groupby(selected.date.dt.year):
        g=cov[cov.year.eq(y)]
        coverage_year.append(dict(year=int(y),original=len(f),admitted=int(f.admitted.sum()),qualified=int(g.status.eq('OK').sum()),
            reasons={str(a):int(b) for a,b in g.status.value_counts().items()}))
    report=dict(status='EXPLORATORY_COMMON_COHORT' if len(out) else 'BLOCKED_NO_QUALIFIED_CAMPAIGNS',
        created_at_utc=datetime.now(timezone.utc).isoformat(),coverage=coverage_year,
        snapshot_rows=snap['rows'],summaries=summaries,comparisons=comparisons,trade_rows=len(fills),campaign_cases=len(out),
        verdict='NO_PROMOTION_PENDING_AUDIT',
        files={n:digest(root/n) for n in ['coverage.parquet','campaigns.parquet','trades.parquet','summary.csv','comparisons.csv']})
    atomic_json(root/'report.json',report);atomic_json(root/'progress.json',dict(status='COMPLETED',cases=len(out),trades=len(fills)))
    LOG.info('Completed %d campaign cases / %d fills',len(out),len(fills))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=['prepare','snapshot','replay'],required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    {'prepare':prepare,'snapshot':snapshot,'replay':replay}[args.phase](args.output)


if __name__=='__main__':main()
