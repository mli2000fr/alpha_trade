"""Offline descriptive audit of native Winner losses; no new policy or PnL replay."""
from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import hashlib
import json
import logging
import math

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

from common.market_calendar import get_market_calendar
from scripts.research.us_winner_bottom_rank_filter_20261022 import (
    read, digest, verify, save_new, qualify_session, DAILY,
)

PARENT=Path('artifacts/research/us_winner_bottom_rank_filter/20261022-v2')
ROOT=Path('artifacts/research/us_winner_loss_diagnostics/20261023-v1')
DOC=Path('doc/ml/winner_audit_pertes_protocole_20261023.md')
R=.07
# Hypothesized direction only, never picked from the outcomes.
FEATURES={'oracle_rank':-1,'signal_age_sessions':-1,'entry_minutes_from_open':-1,
    'pre_entry_extension_atr14':-1,'opening_gap_pct':1,'confirmation_volume_ratio':1,
    'prior_momentum20_pct':1,'prior_close_vs_ma20_pct':1,'prior_atr14_pct':-1,
    'spy_prior_momentum20_pct':1,'spy_prior_vol20_pct':-1}
LOG=logging.getLogger(__name__)


def campaign_key(day,symbol):
    lineage=f'default|paper|replay-{pd.Timestamp(day).date()}|{symbol}'
    return 'wp-'+hashlib.sha256(lineage.encode()).hexdigest()[:40]


def near(a,b):
    if not math.isclose(float(a),float(b),abs_tol=1e-7,rel_tol=1e-10):
        raise AssertionError(f'Reconciliation: {a} != {b}')


def path_signatures(held, future, *, entry_time, exit_time, entry, exit_price,
                    reason, threshold, fee, complete):
    """future is AFTER the entire exit bar. Never call OHLC highs tradeable peaks."""
    before=held[held.bar_end_timestamp.le(exit_time)]
    ambiguous=held[held.bar_timestamp.eq(exit_time)] if reason=='STOP' else held.iloc[:0]
    highs=[entry,exit_price,*before.high];lows=[entry,exit_price,*before.low]
    mfe_lo=max(highs)/entry-1;mae_lo=1-min(lows)/entry
    mfe_hi=max([*highs,*ambiguous.high])/entry-1
    mae_hi=1-min([*lows,*ambiguous.low])/entry
    first=held[held.bar_timestamp.ge(entry_time)].head(2)
    immediate_observed=len(first)==2 and bool(first.bar_end_timestamp.le(exit_time).all())
    # A close at exit_time is already known, unlike OHLC of the exit bar.
    immediate=bool(first.close.lt(threshold).all()) if immediate_observed else None
    result=dict(mfe_lower_pct=100*mfe_lo,mfe_upper_pct=100*mfe_hi,
        mae_lower_pct=100*mae_lo,mae_upper_pct=100*mae_hi,
        gain_1R_certain=bool(mfe_lo>=R-1e-12),exit_bar_1R_ambiguous=bool(mfe_lo<R-1e-12<=mfe_hi),
        immediate_observed=immediate_observed,immediate_failed_breakout=immediate,
        future_complete=bool(complete),post_stop_close_1R=None,post_stop_break_even=None,
        post_stop_1R_time=None,post_stop_1R_calendar_days=None,
        post_stop_mae_until_1R_pct=None,post_stop_max_close_return_pct=None)
    if complete and 'STOP' in reason:
        reached=future[future.close.ge(entry*(1+R)-1e-10)]
        result['post_stop_close_1R']=bool(len(reached))
        result['post_stop_break_even']=bool(future.close.ge(entry*(1+fee)/(1-fee)).any())
        result['post_stop_max_close_return_pct']=float(100*(future.close.max()/entry-1)) if len(future) else None
        if len(reached):
            stamp=reached.bar_end_timestamp.iloc[0]
            prior=future[future.bar_end_timestamp.le(stamp)]
            result.update(post_stop_1R_time=stamp,
                post_stop_1R_calendar_days=(stamp-exit_time).total_seconds()/86400,
                post_stop_mae_until_1R_pct=100*max(0,1-min(exit_price,float(prior.low.min()))/entry))
    return result


def loss_category(row):
    if row['pnl']>=0:return 'WIN_OR_FLAT'
    if row['gain_1R_certain']:return 'GAIN_RESTITUTED_1R'
    if row['immediate_failed_breakout'] is True:return 'IMMEDIATE_FAILED_BREAKOUT'
    if row['post_stop_close_1R'] is True:return 'POST_STOP_REBOUND_1R'
    if row['exit_bar_1R_ambiguous']:return 'AMBIGUOUS_EXIT_BAR_1R'
    return 'RESIDUAL_COMPLETE_WINDOW' if row['future_complete'] else 'UNKNOWN_CENSORED_WINDOW'


def entry_features(history, today, previous, spy, *, entry_time, signal_day,
                   oracle_rank, schedule):
    """Whitelist available inputs; filter by completion BEFORE accessing OHLCV."""
    out={name:np.nan for name in FEATURES}
    day=entry_time.tz_convert('America/New_York').date()
    current=today[today.bar_end_timestamp.le(entry_time)].copy()
    past=history.loc[history.index<pd.Timestamp(day)].copy()
    market=spy.loc[spy.index<pd.Timestamp(day)].copy()
    out['oracle_rank']=oracle_rank
    days=[s.session_date for s in schedule if pd.Timestamp(signal_day).date()<=s.session_date<=day]
    out['signal_age_sessions']=len(days)-1
    opening=next(s.open_at_utc for s in schedule if s.session_date==day)
    out['entry_minutes_from_open']=(entry_time-pd.Timestamp(opening)).total_seconds()/60
    if len(current):out['opening_gap_pct']=100*(float(current.open.iloc[0])/float(previous.close.iloc[-1])-1)
    # Require exact official prior-session grids, never skip missing sessions.
    expected=pd.DatetimeIndex([pd.Timestamp(s.session_date) for s in schedule if s.session_date<day])
    grid=past.reindex(expected[-21:])
    if len(grid)==21 and np.isfinite(grid[['open','high','low','close']]).all().all():
        c=grid.close;tr=pd.concat([grid.high-grid.low,(grid.high-c.shift()).abs(),(grid.low-c.shift()).abs()],axis=1).max(axis=1)
        atr=float(tr.iloc[-14:].mean())
        out['prior_momentum20_pct']=100*(c.iloc[-1]/c.iloc[-21]-1)
        out['prior_close_vs_ma20_pct']=100*(c.iloc[-1]/c.iloc[-20:].mean()-1)
        out['prior_atr14_pct']=100*atr/c.iloc[-1]
        if len(current):out['pre_entry_extension_atr14']=(float(current.close.iloc[-1])-float(previous.high.max()))/atr
    if len(current)>=2:
        tail=current.tail(2)
        offsets=(tail.bar_timestamp.dt.tz_convert('America/New_York').dt.hour*60+tail.bar_timestamp.dt.tz_convert('America/New_York').dt.minute).tolist()
        p=previous.copy();slots=p.bar_timestamp.dt.tz_convert('America/New_York').dt.hour*60+p.bar_timestamp.dt.tz_convert('America/New_York').dt.minute
        same=p[slots.isin(offsets)]
        if len(same)==2 and same.volume.sum()>0:out['confirmation_volume_ratio']=float(tail.volume.sum()/same.volume.sum())
    e=expected[-21:];m=market.reindex(e)
    if len(m)==21 and np.isfinite(m).all() and m.gt(0).all():
        out['spy_prior_momentum20_pct']=100*(m.iloc[-1]/m.iloc[0]-1)
        out['spy_prior_vol20_pct']=100*float(m.pct_change(fill_method=None).iloc[1:].std(ddof=1)*np.sqrt(252))
    return out


def mark_nonoverlap(frame):
    chosen=pd.Series(False,index=frame.index)
    for _,g in frame.sort_values('entry_date').groupby(['year','symbol']):
        next_time=None
        for i,r in g.iterrows():
            if next_time is None or r.entry_date>=next_time:
                chosen.loc[i]=True;next_time=r.theoretical_due_open
    return chosen


def feature_statistics(frame):
    rows=[]
    closed=frame[frame.closed]
    for year,annual in closed.groupby('year'):
        for sample,a in [('ALL',annual),('NONOVERLAP20',annual[annual.nonoverlap20])]:
            for feature,sign in FEATURES.items():
                f=a[np.isfinite(a[feature])];w=f[f.pnl.gt(0)];l=f[f.pnl.lt(0)]
                rows.append(dict(year=int(year),sample=sample,feature=feature,hypothesis_sign=sign,
                    total_closed=len(a),covered=len(f),winners=len(w),losers=len(l),
                    unique_symbols=int(f.symbol.nunique()),unique_entry_days=int(f.entry_day.nunique()),
                    winner_median=float(w[feature].median()) if len(w) else None,
                    loser_median=float(l[feature].median()) if len(l) else None,
                    auc_hypothesis=float(roc_auc_score(f.pnl.gt(0),sign*f[feature])) if min(len(w),len(l))>=5 else None))
    return pd.DataFrame(rows)


def run(root=ROOT):
    if root.exists():raise FileExistsError('Fresh immutable output required')
    protocol=read(PARENT/'protocol.json');verify(protocol['sources'])
    source=read(PARENT/'report.json');audit=read(PARENT/'final-audit.json')
    if audit['report_sha256']!=digest(PARENT/'report.json') or audit['accounts']!=6:raise ValueError('Native cash audit absent')
    verify({str(PARENT/k):v for k,v in source['files'].items()})
    snap=read(PARENT/'snapshot.json');verify({str(PARENT/k):v for k,v in snap['files'].items()})
    inputs=[DOC,Path(__file__),Path('tests/test_us_winner_loss_diagnostics_20261023.py'),
        PARENT/'protocol.json',PARENT/'report.json',PARENT/'final-audit.json',PARENT/'snapshot.json',DAILY,
        Path('scripts/research/us_winner_bottom_rank_filter_20261022.py')]
    for year in (2025,2026):
        case=read(PARENT/f'{year}-WINNER_ONLY/report.json')
        verify({str(PARENT/f'{year}-WINNER_ONLY'/k):v for k,v in case['files'].items()})
        inputs.extend([PARENT/f'{year}-WINNER_ONLY'/k for k in ['report.json',*case['files']]])
    sources={str(x):digest(x) for x in inputs}
    sources.update({str(PARENT/k):v for k,v in snap['files'].items()})
    root.mkdir(parents=True)
    save_new(root/'protocol.json',dict(created_at_utc=datetime.now(timezone.utc).isoformat(),sources=sources,
        parent=str(PARENT),features_orientations=FEATURES,R=R,future_label_only=True,
        poststop_target='5m CLOSE +1R after the complete exit bar, original20 holding sessions',
        primary_partition=['GAIN_RESTITUTED_1R','IMMEDIATE_FAILED_BREAKOUT','POST_STOP_REBOUND_1R',
            'AMBIGUOUS_EXIT_BAR_1R','RESIDUAL_COMPLETE_WINDOW','UNKNOWN_CENSORED_WINDOW'],
        source_clock='STOP logged at bar START: bounds, not fictional ordering',
        model_fits=0,economic_replays=0,SQL_reads=0,SQL_writes=False,provider_calls=0,orders=False,
        PIT_certified=False,independent_holdout=False))
    calendar=get_market_calendar('US_EQ',allow_us_weekday_fallback=False)
    schedule=[s for s in calendar.sessions(date(2024,12,1),date(2026,12,31)) if s.is_open]
    dates=[s.session_date for s in schedule];byday={s.session_date:s for s in schedule}
    # Keep only complete sessions, qualified by the same sealed raw contract.
    groups={};histories={}
    for n,item in enumerate(snap['receipts']):
        frame=pd.read_parquet(PARENT/item['file'])
        rows=[]
        for day,g in frame.groupby('trade_date',sort=True):
            d=pd.Timestamp(day).date();s=byday.get(d)
            if s is None:continue
            if qualify_session(g,s):
                groups[item['symbol'],d]=g.sort_values('bar_timestamp').reset_index(drop=True)
                rows.append(dict(date=pd.Timestamp(d),open=g.open.iloc[0],high=g.high.max(),low=g.low.min(),close=g.close.iloc[-1]))
        histories[item['symbol']]=pd.DataFrame(rows).set_index('date') if rows else pd.DataFrame(columns=['open','high','low','close'])
        if n%25==0:LOG.info('Qualified SIP snapshots %s/%s',n+1,len(snap['receipts']))
    spy=pd.read_parquet(DAILY,filters=[('symbol','==','SPY')])
    good=np.isfinite(spy.close)&spy.close.gt(0)&spy.is_filled.eq(0)&spy.data_adjustment.eq('split')
    spy=spy.set_index('date').close.where(good.to_numpy()).sort_index()
    if not spy.index.is_unique:raise ValueError('Duplicate SPY')
    signals=pd.read_parquet(PARENT/'qualified-signals.parquet')
    signals['campaign_id']=[campaign_key(d,s) for d,s in zip(signals.date,signals.symbol)]
    actions=pd.read_parquet(PARENT/'actions.parquet');actions['ex_date']=pd.to_datetime(actions.ex_date)
    results=[];checks=[]
    for year,expected in [(2025,(53,9,44)),(2026,(120,38,82))]:
        folder=PARENT/f'{year}-WINNER_ONLY';trades=pd.read_parquet(folder/'trades.parquet')
        if (len(trades),int(trades.pnl.gt(0).sum()),int(trades.pnl.lt(0).sum()))!=expected:raise ValueError('Population drift')
        events=pd.read_csv(folder/'events.csv',low_memory=False);buys=events[events.event.eq('BUY_FILL')].copy()
        buys['time']=pd.to_datetime(buys.time,utc=True)
        annual=signals[signals.year.eq(year)].set_index('campaign_id')
        if not annual.index.is_unique:raise ValueError('Duplicate campaign lineage')
        closedkeys=set()
        for trade in trades.itertuples():
            signal=annual.loc[trade.campaign_id]
            if not signal.common_eligible:raise AssertionError('Unqualified actual campaign')
            key=(trade.symbol,trade.entry_date)
            if key in closedkeys:raise AssertionError('Unexpected partial/reinforced trade')
            closedkeys.add(key)
            match=buys[buys.symbol.eq(trade.symbol)&buys.time.eq(trade.entry_date)]
            if len(match)!=1:raise AssertionError('Entry fill mismatch')
            near(match.quantity.iloc[0],trade.quantity);near(match.price.iloc[0],trade.entry_price)
            near(trade.pnl,trade.quantity*(trade.exit_price-trade.entry_price)-trade.entry_fees-trade.exit_fees+trade.dividends)
        entries=[]
        for b in buys.itertuples():
            matches=trades[trades.symbol.eq(b.symbol)&trades.entry_date.eq(b.time)]
            if len(matches):
                trade=matches.iloc[0].to_dict();trade['closed']=True;entries.append(trade)
            else:
                # Identify only the true remaining lineage, not an arbitrary latest signal.
                pending=annual[(annual.symbol==b.symbol)&annual.common_eligible&annual.date.lt(pd.Timestamp(b.time.tz_convert('America/New_York').date()))]
                entries.append(dict(symbol=b.symbol,quantity=b.quantity,entry_date=b.time,entry_price=b.price,
                    entry_fees=b.costs,closed=False,pnl=np.nan,campaign_id=None,pending_lineages=len(pending)))
        open_entries=[x for x in entries if not x['closed']]
        expected_open=read(folder/'report.json')['open_positions']
        if {x['symbol']:x['quantity'] for x in open_entries}!={x['symbol']:x['qty'] for x in expected_open}:
            raise AssertionError('Open inventory differs from actual account')
        for row in entries:
            entry_time=pd.Timestamp(row['entry_date']);symbol=row['symbol'];day=entry_time.tz_convert('America/New_York').date()
            j=dates.index(day);previous=groups[symbol,dates[j-1]];today=groups[symbol,day]
            due=pd.Timestamp(schedule[j+20].open_at_utc);holding=dates[j:j+20]
            row.update(year=year,entry_day=pd.Timestamp(day),theoretical_due_open=due)
            if not row['closed']:
                row['diagnostic']='OPEN_NO_REALIZED_LABEL';results.append(row);continue
            signal=annual.loc[row['campaign_id']]
            row.update(signal_date=signal.date,oracle_rank=int(signal.oracle_rank))
            cutoff=date(year,12,31) if year==2025 else date(2026,9,30)
            complete=holding[-1]<=cutoff and all((symbol,d) in groups for d in holding)
            known_actions=actions[actions.symbol.eq(symbol)&actions.ex_date.between(pd.Timestamp(day),pd.Timestamp(holding[-1]))]
            if len(known_actions):complete=False
            exit_time=pd.Timestamp(row['exit_date'])
            actual_days=[d for d in dates[j:] if d<=exit_time.tz_convert('America/New_York').date()]
            if not all((symbol,d) in groups for d in actual_days):raise AssertionError('Missing held bar')
            actual=pd.concat([groups[symbol,d] for d in actual_days],ignore_index=True)
            held=actual[actual.bar_timestamp.ge(entry_time)&actual.bar_timestamp.le(exit_time)]
            if len(held)==0 or held.bar_timestamp.iloc[0]!=entry_time:raise AssertionError('Entry bar absent')
            # No high/low from the EXIT bar in the post-stop measurement.
            future=(pd.concat([groups[symbol,d] for d in holding],ignore_index=True) if complete else held.iloc[:0])
            future=future[future.bar_timestamp.ge(exit_time+pd.Timedelta(minutes=5))]
            fee=row['entry_fees']/(row['quantity']*row['entry_price'])
            near(fee,.0008)
            sig=path_signatures(held,future,entry_time=entry_time,exit_time=exit_time,
                entry=row['entry_price'],exit_price=row['exit_price'],reason=row['exit_reason'],
                threshold=float(previous.high.max()),fee=fee,complete=complete)
            row.update(sig);row['diagnostic']=loss_category(row)
            row['forward_status']='COMPLETE' if complete else 'CENSORED_OR_MISSING_OR_ACTION'
            row['holding_sessions']=len(actual_days)
            feat=entry_features(histories[symbol],today,previous,spy,entry_time=entry_time,
                signal_day=signal.date,oracle_rank=int(signal.oracle_rank),schedule=schedule)
            prefix=entry_features(histories[symbol].loc[:pd.Timestamp(dates[j-1])],today[today.bar_end_timestamp.le(entry_time)],
                previous,spy.loc[:pd.Timestamp(dates[j-1])],entry_time=entry_time,
                signal_day=signal.date,oracle_rank=int(signal.oracle_rank),schedule=schedule)
            for k in FEATURES:
                if not (pd.isna(feat[k]) and pd.isna(prefix[k])):near(feat[k],prefix[k])
            checks.append(dict(year=year,campaign_id=row['campaign_id'],prefix_exact=True))
            row.update(feat);results.append(row)
    allrows=pd.DataFrame(results);allrows['nonoverlap20']=mark_nonoverlap(allrows)
    allrows.to_parquet(root/'entry-inventory.parquet',index=False)
    closed=allrows[allrows.closed].copy();closed.to_parquet(root/'trade-diagnostics.parquet',index=False)
    # Future labels and pre-entry probes are deliberately delivered separately.
    feature_cols=['year','campaign_id','symbol','entry_date','entry_day','nonoverlap20',*FEATURES]
    closed[feature_cols].to_parquet(root/'pre-entry-observables.parquet',index=False)
    closed[~closed.nonoverlap20].to_csv(root/'excluded-overlapping-windows.csv',index=False)
    stats=feature_statistics(allrows);stats.to_csv(root/'feature-separation.csv',index=False)
    losses=closed[closed.pnl.lt(0)]
    category=losses.groupby(['year','diagnostic']).agg(trades=('symbol','size'),net_loss_usd=('pnl','sum'),
        symbols=('symbol','nunique')).reset_index()
    category['share_losses_pct']=100*category.trades/category.year.map(losses.groupby('year').size())
    category.to_csv(root/'loss-categories.csv',index=False)
    for label,key in [('symbol','symbol'),('month','entry_month')]:
        if key=='entry_month':closed[key]=closed.entry_date.dt.tz_convert('America/New_York').dt.strftime('%Y-%m')
        grouped=closed.groupby(['year',key]).agg(trades=('symbol','size'),winners=('pnl',lambda x:int(x.gt(0).sum())),
            losers=('pnl',lambda x:int(x.lt(0).sum())),net_realized_usd=('pnl','sum'),
            gross_losses_usd=('pnl',lambda x:float(x[x.lt(0)].sum())),gross_gains_usd=('pnl',lambda x:float(x[x.gt(0)].sum()))).reset_index()
        grouped.to_csv(root/f'concentration-{label}.csv',index=False)
    summaries=[]
    for year,g in closed.groupby('year'):
        l=g[g.pnl.lt(0)];w=g[g.pnl.gt(0)]
        known=l[l.future_complete]
        immediate=l[l.immediate_observed]
        summaries.append(dict(year=int(year),closed=len(g),winners=len(w),losers=len(l),
            open_positions=int((allrows.year.eq(year)&~allrows.closed).sum()),
            loss_symbols=int(l.symbol.nunique()),loss_entry_days=int(l.entry_day.nunique()),
            losing_stop_reasons=l.exit_reason.value_counts().to_dict(),
            gain_restituted_1R=int(l.gain_1R_certain.sum()),
            immediate_observed=len(immediate),immediate_failed=int(immediate.immediate_failed_breakout.sum()),
            future_qualified_losses=len(known),post_stop_close_1R=int(known.post_stop_close_1R.fillna(False).sum()),
            ambiguous_exit_1R=int(l.exit_bar_1R_ambiguous.sum()),
            residual_or_unknown=int(l.diagnostic.isin(['RESIDUAL_COMPLETE_WINDOW','UNKNOWN_CENSORED_WINDOW']).sum()),
            gross_winning_pnl=float(w.pnl.sum()),gross_losing_pnl=float(l.pnl.sum()),
            nonoverlap20_closed=int(g.nonoverlap20.sum()),
            top5_winners_share_pct=100*float(w.pnl.nlargest(5).sum()/w.pnl.sum()),
            top5_losses_share_pct=100*float(l.pnl.nsmallest(5).sum()/l.pnl.sum())))
    if len(closed)!=173 or len(losses)!=126 or int(category.trades.sum())!=126:raise AssertionError('Loss partition drift')
    verify(sources)
    save_new(root/'prefix-checks.json',dict(checks=checks,count=len(checks),passed=True))
    save_new(root/'report.json',dict(status='COMPLETED_DESCRIPTIVE_AUDIT',summaries=summaries,
        population_buys=len(allrows),closed_trades=len(closed),open_censored=int((~allrows.closed).sum()),
        categories=category.to_dict('records'),prefix_checks=len(checks),features=list(FEATURES),
        sources_verified=True,SQL_reads=0,SQL_writes=False,provider_calls=0,economic_replays=0,
        trained_models=0,new_filter=False,independent_holdout=False,
        files={x.name:digest(x) for x in root.iterdir() if x.is_file()}))
    LOG.info('Completed descriptive audit: %s',summaries)


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
    import requests
    def forbidden(*args,**kwargs):raise RuntimeError('Offline audit; HTTP forbidden')
    requests.Session.request=forbidden
    run()
