"""Separate scalar reconstruction of the descriptive Winner loss audit."""
from datetime import date
from pathlib import Path
import math

import numpy as np
import pandas as pd
from common.market_calendar import get_market_calendar
from modelFactory.oracle.security_continuity import (
    DEFAULT_REGISTRY_PATH,load_security_discontinuities,path_crosses_known_discontinuity,
)
from scripts.research.us_winner_bottom_rank_filter_20261022 import read,digest,verify,save_new

ROOT=Path('artifacts/research/us_winner_loss_diagnostics/20261023-v1')


def close(a,b):
    if pd.isna(a) and pd.isna(b):return
    if not math.isclose(float(a),float(b),abs_tol=1e-8,rel_tol=1e-10):raise AssertionError(f'{a} != {b}')


def scalar_excursions(frame,entry_time,exit_time,entry_price,exit_price,reason):
    lower_high=upper_high=max(entry_price,exit_price)
    lower_low=upper_low=min(entry_price,exit_price)
    for b in frame.itertuples():
        if b.bar_timestamp<entry_time or b.bar_timestamp>exit_time:continue
        if b.bar_end_timestamp<=exit_time:
            lower_high=max(lower_high,b.high);lower_low=min(lower_low,b.low)
            upper_high=max(upper_high,b.high);upper_low=min(upper_low,b.low)
        elif b.bar_timestamp==exit_time and reason=='STOP':
            upper_high=max(upper_high,b.high);upper_low=min(upper_low,b.low)
    return [100*(lower_high/entry_price-1),100*(upper_high/entry_price-1),
            100*(1-lower_low/entry_price),100*(1-upper_low/entry_price)]


def run(root=ROOT):
    protocol=read(root/'protocol.json');verify(protocol['sources'])
    report=read(root/'report.json');verify({str(root/k):v for k,v in report['files'].items()})
    parent=Path(protocol['parent']);snap=read(parent/'snapshot.json')
    days=[s for s in get_market_calendar('US_EQ',allow_us_weekday_fallback=False).sessions(date(2024,12,1),date(2026,12,31)) if s.is_open]
    dates=[s.session_date for s in days];index={x:i for i,x in enumerate(dates)}
    frames={};qualified={}
    for item in snap['receipts']:
        f=pd.read_parquet(parent/item['file']);frames[item['symbol']]=f
        for d,g in f.groupby('trade_date',sort=False):
            day=pd.Timestamp(d).date()
            if day not in index:continue
            s=days[index[day]]
            stamps=pd.DatetimeIndex(g.bar_timestamp)
            expected=pd.date_range(s.open_at_utc,s.close_at_utc,freq='5min',inclusive='left')
            nums=g[['open','high','low','close','volume']].to_numpy(float)
            valid=len(g)==len(expected) and stamps.equals(expected)
            valid=valid and bool(np.isfinite(nums).all() and (nums>0).all())
            valid=valid and bool(g.high.ge(g[['open','close']].max(axis=1)).all() and g.low.le(g[['open','close']].min(axis=1)).all())
            valid=valid and bool((g.bar_end_timestamp-g.bar_timestamp).eq(pd.Timedelta(minutes=5)).all() and g.payload_hash.notna().all())
            qualified[item['symbol'],day]=valid
    actions=pd.read_parquet(parent/'actions.parquet');registry=load_security_discontinuities()
    trades=pd.read_parquet(root/'trade-diagnostics.parquet');inventory=pd.read_parquet(root/'entry-inventory.parquet')
    prefix=read(root/'prefix-checks.json')
    if prefix['count']!=173 or not all(x['prefix_exact'] for x in prefix['checks']):raise AssertionError('Missing prefix controls')
    if len(inventory)!=179 or inventory.closed.sum()!=173:raise AssertionError('Population')
    categories=[];bounds=[];id_breaks=[];n=0
    for r in trades.itertuples():
        f=frames[r.symbol];e=float(r.entry_price);x=r.exit_date
        excursions=scalar_excursions(f,r.entry_date,x,e,r.exit_price,r.exit_reason)
        for a,b in zip(excursions,[r.mfe_lower_pct,r.mfe_upper_pct,r.mae_lower_pct,r.mae_upper_pct]):close(a,b)
        certainty=excursions[0]>=7-1e-10;ambiguity=excursions[0]<7-1e-10<=excursions[1]
        if certainty!=r.gain_1R_certain or ambiguity!=r.exit_bar_1R_ambiguous:raise AssertionError('Excursion classification')
        day=r.entry_date.tz_convert('America/New_York').date();j=index[day]
        window=dates[j:j+20];end=days[j+20].open_at_utc
        if pd.Timestamp(end)!=r.theoretical_due_open:raise AssertionError('Held-session horizon')
        cutoff=date(2025,12,31) if r.year==2025 else date(2026,9,30)
        action=actions[actions.symbol.eq(r.symbol)&pd.to_datetime(actions.ex_date).between(pd.Timestamp(day),pd.Timestamp(window[-1]))]
        complete=window[-1]<=cutoff and all(qualified.get((r.symbol,d),False) for d in window) and action.empty
        if complete!=r.future_complete:raise AssertionError('Future qualification')
        if path_crosses_known_discontinuity(r.symbol,pd.Timestamp(day)-pd.Timedelta(days=40),pd.Timestamp(window[-1]),registry):
            id_breaks.append(r.campaign_id)
        prior=f[pd.to_datetime(f.trade_date).eq(pd.Timestamp(dates[j-1]))]
        first=f[f.bar_timestamp.ge(r.entry_date)].head(2)
        observed=len(first)==2 and all(t<=x for t in first.bar_end_timestamp)
        failed=bool(all(c<prior.high.max() for c in first.close)) if observed else None
        if observed!=r.immediate_observed or (observed and failed!=r.immediate_failed_breakout):raise AssertionError('Immediate closes')
        after=f[f.bar_timestamp.ge(x+pd.Timedelta(minutes=5))&f.bar_timestamp.lt(end)]
        reached=False;break_even=False;lo=r.exit_price;first_hit=None
        if complete and 'STOP' in r.exit_reason:
            for b in after.itertuples():
                if b.close>=e*1.0008/.9992:break_even=True
                if first_hit is None:
                    lo=min(lo,b.low)
                    if b.close>=e*1.07-1e-10:first_hit=b.bar_end_timestamp
            reached=first_hit is not None
            if reached!=r.post_stop_close_1R or break_even!=r.post_stop_break_even:raise AssertionError('Post-stop closes')
            if reached:
                if first_hit!=r.post_stop_1R_time:raise AssertionError('First rebound time')
                close((first_hit-x).total_seconds()/86400,r.post_stop_1R_calendar_days)
                close(100*max(0,1-lo/e),r.post_stop_mae_until_1R_pct)
                exitbar=f[f.bar_timestamp.eq(x)]
                lo_upper=min(lo,float(exitbar.low.iloc[0]))
                bounds.append(dict(year=r.year,campaign_id=r.campaign_id,symbol=r.symbol,
                    mae_after_stop_until_rebound_lower_pct=100*max(0,1-lo/e),
                    mae_after_stop_until_rebound_upper_pct=100*max(0,1-lo_upper/e),
                    rebound_calendar_days=r.post_stop_1R_calendar_days))
        elif pd.notna(r.post_stop_close_1R):raise AssertionError('Unknown post-stop result imputed')
        if r.pnl>=0:category='WIN_OR_FLAT'
        elif certainty:category='GAIN_RESTITUTED_1R'
        elif failed:category='IMMEDIATE_FAILED_BREAKOUT'
        elif reached:category='POST_STOP_REBOUND_1R'
        elif ambiguity:category='AMBIGUOUS_EXIT_BAR_1R'
        elif complete:category='RESIDUAL_COMPLETE_WINDOW'
        else:category='UNKNOWN_CENSORED_WINDOW'
        if category!=r.diagnostic:raise AssertionError('Loss partition')
        categories.append(category);n+=1
    if id_breaks:raise AssertionError('Known identity breaks reserved: '+str(id_breaks))
    stats=pd.read_csv(root/'feature-separation.csv')
    from sklearn.metrics import roc_auc_score
    probe=pd.read_parquet(root/'pre-entry-observables.parquet').merge(trades[['campaign_id','pnl']],on='campaign_id',validate='one_to_one')
    for row in stats.itertuples():
        g=probe[probe.year.eq(row.year)]
        if row.sample=='NONOVERLAP20':g=g[g.nonoverlap20]
        g=g[np.isfinite(g[row.feature])]
        if len(g)!=row.covered or g.pnl.gt(0).sum()!=row.winners or g.pnl.lt(0).sum()!=row.losers:raise AssertionError('Feature population')
        if min(row.winners,row.losers)>=5:close(roc_auc_score(g.pnl.gt(0),row.hypothesis_sign*g[row.feature]),row.auc_hypothesis)
        elif pd.notna(row.auc_hypothesis):raise AssertionError('Underpowered AUC was published')
    pd.DataFrame(bounds).to_csv(root/'poststop-adverse-bounds.csv',index=False)
    result=dict(status='PASS_SCALAR_EXCURSIONS_POSTSTOP_CENSORING_CATEGORIES_AND_AUC',
        trades=n,prefix_checks=173,poststop_rebounds=len(bounds),statistic_cells=len(stats),
        known_identity_breaks=0,corporate_action_inventory_count=len(actions),
        corporate_action_inventory_not_exhaustive=True,open_censored=6,
        report_sha256=digest(root/'report.json'),auditor_sha256=digest(__file__),
        identity_registry_sha256=digest(DEFAULT_REGISTRY_PATH),
        poststop_bounds_sha256=digest(root/'poststop-adverse-bounds.csv'),independent_human_review=False)
    save_new(root/'final-audit.json',result)
    print(result)


if __name__=='__main__':run()
